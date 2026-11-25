"""B3 end-to-end level (answers), RAGOps Table 1.

Each golden question goes through the API's own answer_question (retrieval, relevance floor,
LLM, citation enforcement), with no cache. Per question we record the answer and latency, then:

  abstention correctness  unanswerable → answered_from_context false (must be 100%);
                          answerable/hard → answered (the false-abstention rate is reported)
  citation validity       every citation (source, section, page) matches a chunk retrieved
                          for that request; also the share citing a golden-relevant chunk
  correctness             the golden `expect` string appears in the answer
  faithfulness            an LLM judge (Gemini, temperature 0) reads only the retrieved
                          evidence + the answer and says whether every claim is supported
  latency                 p50 / p95 of the whole answer_question call

Judge agreement: eval/labels/faithfulness.jsonl holds hand labels for answers of a labelled
run (eval/labels/to_label.jsonl); agreement % = labels equal to the judge's verdicts.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from typing import Any

import httpx

from .common import EVAL, is_relevant, percentile, read_jsonl

JUDGE_PROMPT = """You are grading a question-answering system for faithfulness.
Given EVIDENCE passages and an ANSWER, decide whether every factual claim in the ANSWER is
supported by the EVIDENCE. Ignore style. Outside knowledge does not count as support.
Reply with JSON only: {"faithful": true|false, "score": <0.0-1.0 share of supported claims>,
"unsupported": ["<claim>", ...]}"""


RETRY_STATUS = (429, 500, 502, 503, 504)
BACKOFF_SECONDS = 15


class Pacer:
    """Keeps hosted-LLM calls under the free tier's requests-per-minute limit."""

    def __init__(self, rpm: float) -> None:
        self.gap = 60.0 / rpm if rpm > 0 else 0.0
        self.last = 0.0

    def wait(self) -> None:
        delay = self.last + self.gap - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()


def judge_targets(settings: Any) -> list[tuple[str, str, str]]:
    """(base_url, model, key): Gemini first, then each Groq model if GROQ_API_KEY is set."""
    targets = [(settings.hosted_base_url, os.environ.get("JUDGE_MODEL", settings.llm_model),
                settings.llm_api_key)]
    if settings.groq_api_key:
        targets += [(settings.groq_base_url, m.strip(), settings.groq_api_key)
                    for m in settings.groq_models.split(",") if m.strip()]
    return targets


def judge(settings: Any, evidence: list[dict[str, Any]], answer: str, pacer: Pacer,
          attempts: int = 4) -> dict[str, Any] | None:
    """The judge's verdict, or None if every hosted model stayed unavailable (not counted)."""
    text = "\n\n".join(f"[{i}] ({e['source']} / {e['section']} / p.{e['page']})\n{e['text']}"
                       for i, e in enumerate(evidence, 1))
    messages = [{"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": f"EVIDENCE:\n{text}\n\nANSWER:\n{answer}"}]
    for base_url, model, key in judge_targets(settings):
        body = {"model": model, "temperature": 0.0, "response_format": {"type": "json_object"},
                "messages": messages}
        for attempt in range(attempts):
            pacer.wait()
            try:
                response = httpx.post(base_url.rstrip("/") + "/chat/completions",
                                      headers={"Authorization": f"Bearer {key}"},
                                      json=body, timeout=60)
            except httpx.HTTPError:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
                continue
            if response.status_code in RETRY_STATUS:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
                continue
            response.raise_for_status()
            verdict = json.loads(response.json()["choices"][0]["message"]["content"])
            return {"faithful": bool(verdict.get("faithful")),
                    "score": float(verdict.get("score", 0.0)),
                    "unsupported": list(verdict.get("unsupported", [])), "judge_model": model}
    return None


def run_question(settings: Any, retriever: Any, provider: Any, question: dict[str, Any],
                 pacer: Pacer, use_judge: bool) -> dict[str, Any]:
    from app.services.answer import FALLBACK, answer_question

    for attempt in range(3):     # a canned fallback = the hosted model was unavailable: retry
        pacer.wait()
        started = time.perf_counter()
        response = answer_question(question["question"], retriever, provider, settings,
                                   cache=None)
        seconds = time.perf_counter() - started
        fallback = response.answer == FALLBACK.answer
        if not fallback:
            break
        time.sleep(BACKOFF_SECONDS * 2 * (attempt + 1))
    for wait in (5, 30, 0):      # the local Ollama can time out under load: retry, then raise
        try:
            passages = retriever.retrieve(question["question"], k=settings.top_k)  # same call
            break
        except httpx.HTTPError:
            if not wait:
                raise
            time.sleep(wait)
    # Only what the answer used: the injection rail (D4) may have dropped a retrieved chunk.
    used = {r.chunk_id for r in response.retrieved}
    passages = [p for p in passages if p.chunk_id in used]
    by_key = {(p.source, p.section, p.page): p for p in passages}
    retrieved_keys = {(r.source, r.section, r.page) for r in response.retrieved}
    cites = [(c.source, c.section, c.page) for c in response.citations]
    should_answer = not question["must_abstain"]
    row: dict[str, Any] = {
        "id": question["id"], "type": question["type"], "question": question["question"],
        "answer": response.answer, "answered": response.answered_from_context,
        "abstention_correct": response.answered_from_context == should_answer,
        "citations": [list(c) for c in cites],
        "citations_valid": all(c in retrieved_keys for c in cites),
        "cites_relevant": any(is_relevant(by_key[c], question["relevant"])
                              for c in cites if c in by_key) if question["relevant"] else None,
        "expect_found": (question["expect"].lower() in response.answer.lower()
                         if should_answer and question["expect"] else None),
        "seconds": round(seconds, 3), "provider": response.provider, "fallback": fallback,
        "attempts": attempt + 1,
        "top_score": round(max((r.score for r in response.retrieved), default=0.0), 4),
    }
    if use_judge and response.answered_from_context:
        evidence = [{"source": p.source, "section": p.section, "page": p.page, "text": p.text}
                    for p in passages]
        row["evidence"] = evidence
        row["judge"] = judge(settings, evidence, response.answer, pacer)
    return row


def agreement() -> dict[str, Any] | None:
    """Hand labels (eval/labels/faithfulness_hand.jsonl, label faithful/unfaithful) against
    the judge's verdicts on the same answers (eval/labels/judge_verdicts.jsonl)."""
    hand_path = EVAL / "labels" / "faithfulness_hand.jsonl"
    judge_path = EVAL / "labels" / "judge_verdicts.jsonl"
    if not hand_path.exists() or not judge_path.exists():
        return None
    verdicts = {r["id"]: r["judge_faithful"] for r in read_jsonl(judge_path)}
    pairs = [(r["label"] == "faithful", verdicts[r["id"]]) for r in read_jsonl(hand_path)
             if r.get("label") in ("faithful", "unfaithful") and r["id"] in verdicts]
    if not pairs:
        return {"labelled": 0, "agreement": None}
    return {"labelled": len(pairs),
            "agreement": round(sum(h == j for h, j in pairs) / len(pairs), 4)}


def evaluate(settings: Any, golden: list[dict[str, Any]], use_judge: bool = True,
             rpm: float = 10.0) -> dict[str, Any]:
    from app.providers.llm import get_provider
    from app.retrieval.chroma import ChromaRetriever

    retriever, provider, pacer = ChromaRetriever(settings), get_provider(settings), Pacer(rpm)
    all_rows = [run_question(settings, retriever, provider, q, pacer, use_judge) for q in golden]
    # A fallback is an outage, not an answer or an abstention: reported, not scored.
    rows = [r for r in all_rows if not r["fallback"]]
    must_abstain = [r for r in rows if r["type"] == "unanswerable"]
    should_answer = [r for r in rows if r["type"] != "unanswerable"]
    judged = [r["judge"] for r in rows if r.get("judge")]
    times = [r["seconds"] for r in rows]
    expect = [r["expect_found"] for r in rows if r["expect_found"] is not None]
    relevant = [r["cites_relevant"] for r in rows if r["cites_relevant"] is not None and r["answered"]]
    summary = {
        "questions": len(all_rows),
        "scored": len(rows),
        "fallbacks_after_retries": len(all_rows) - len(rows),
        "abstention_correct_unanswerable": round(statistics.mean(r["abstention_correct"]
                                                                 for r in must_abstain), 4),
        "false_abstention_rate": round(statistics.mean(not r["answered"] for r in should_answer), 4),
        "abstention_accuracy": round(statistics.mean(r["abstention_correct"] for r in rows), 4),
        "citation_validity": round(statistics.mean(r["citations_valid"] for r in rows), 4),
        "cites_relevant_chunk": round(statistics.mean(relevant), 4) if relevant else None,
        "answer_correct_expect": round(statistics.mean(expect), 4) if expect else None,
        "faithfulness": round(statistics.mean(j["faithful"] for j in judged), 4) if judged else None,
        "faithfulness_score_mean": round(statistics.mean(j["score"] for j in judged), 4)
        if judged else None,
        "judged": len(judged),
        "judge_unavailable": sum("judge" in r and r["judge"] is None for r in rows),
        "latency_p50_s": round(percentile(times, 50), 3),
        "latency_p95_s": round(percentile(times, 95), 3),
        "judge_agreement": agreement(),
    }
    return {"collection": settings.collection, "model": settings.llm_model,
            "summary": summary, "per_question": all_rows}


def write_label_sheet(result: dict[str, Any], n: int = 10) -> None:
    """eval/labels/faithfulness_hand.jsonl: answered questions with their retrieved context and
    an empty `label` for a human. The judge's verdicts go to a separate file, so the labeller
    does not see them. Existing labels are kept for answers that did not change."""
    rows = [r for r in result["per_question"] if r.get("judge") and not r["fallback"]][:n]
    labels_dir = EVAL / "labels"
    labels_dir.mkdir(exist_ok=True)
    hand_path = labels_dir / "faithfulness_hand.jsonl"
    old = {r["id"]: r for r in read_jsonl(hand_path)} if hand_path.exists() else {}
    with hand_path.open("w", encoding="utf-8") as hand, \
            (labels_dir / "judge_verdicts.jsonl").open("w", encoding="utf-8") as verdicts:
        for r in rows:
            rid = f"f-{r['id']}"
            keep = old.get(rid, {})
            label = keep.get("label", "") if keep.get("answer") == r["answer"] else ""
            hand.write(json.dumps({
                "id": rid, "question_id": r["id"], "question": r["question"],
                "context": r["evidence"], "answer": r["answer"], "label": label,
                "notes": keep.get("notes", "") if label else "",
                "run": result.get("run", "")}, ensure_ascii=False) + "\n")
            verdicts.write(json.dumps({"id": rid, "judge_faithful": r["judge"]["faithful"],
                                       "judge_score": r["judge"]["score"],
                                       "judge_model": r["judge"]["judge_model"]}) + "\n")
