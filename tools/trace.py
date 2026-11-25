"""D2: show exactly what the model saw for one request, from its trace alone.

    python -m tools.trace <trace_id> [--file /data/traces/traces.jsonl]

Prints the retrieval (chunk ids, doc ids/versions, scores, filters, guardrail actions), then
REBUILDS the prompt from the stored chunk texts with the API's own build_messages and checks
that its sha256 equals the prompt_hash the API recorded. Exit 0 = rebuilt prompt matches,
1 = trace not found, 3 = hash mismatch (the prompt code changed since the trace was written).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
DEFAULT = os.environ.get("TRACE_FILE", "/data/traces/traces.jsonl")


def prompt_hash(messages: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False)
                          .encode()).hexdigest()


def find(path: Path, trace_id: str) -> dict | None:
    hit = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if trace_id in line:
                row = json.loads(line)
                if row.get("trace_id") == trace_id or row["trace_id"].startswith(trace_id):
                    hit = row   # the last match wins
    return hit


def rebuild(trace: dict) -> list[dict[str, str]]:
    from app.schemas import Passage
    from app.services.prompt import build_messages
    passages = [Passage(chunk_id=c["chunk_id"], text=c["text"], source=c["source"],
                        section=c["section"], page=c["page"], score=c["score"])
                for c in trace["context"]]
    return build_messages(trace["query"], passages)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("trace_id")
    p.add_argument("--file", type=Path, default=Path(DEFAULT))
    p.add_argument("--json", action="store_true", help="print the whole trace record")
    args = p.parse_args()
    trace = find(args.file, args.trace_id)
    if trace is None:
        print(f"trace {args.trace_id} not found in {args.file}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(trace, indent=2, ensure_ascii=False))
    print(f"trace {trace['trace_id']}  at {trace['ts']}")
    print(f"query      : {trace['query']}")
    print(f"collection : {trace['collection']}  embed {trace['embedding']}")
    print(f"filters    : {trace['filters']}   floor {trace['relevance_floor']}")
    print(f"llm        : {trace['llm']}")
    print(f"outcome    : answered={trace['response']['answered_from_context']} "
          f"cached={trace['cached']} fallback={trace['fallback']}  latency {trace['latency_ms']}")
    for g in trace["guardrails"]:
        print(f"guardrail  : {g}")
    print("\nretrieved (rank, score, chunk, doc@version, source / section / page):")
    for r in trace["retrieved"]:
        print(f"  {r['rank']}. {r['score']:.4f} {r['chunk_id'][:12]} {r['doc_id']}@{r['doc_version']}"
              f"  {r['source']} / {r['section']} / p.{r['page']}"
              f"{'  [boosted]' if r.get('boosted') else ''}"
              f"{'  [DROPPED by guardrail]' if r.get('dropped') else ''}")
    if not trace.get("prompt"):
        print("\nno prompt: the model was not called (abstained below the floor, cache hit, "
              "or retrieval failed)")
        return 0
    messages = rebuild(trace)
    rebuilt = prompt_hash(messages)
    print("\n===== PROMPT (rebuilt from the trace's context) =====")
    for m in messages:
        print(f"--- {m['role']} ---\n{m['content']}")
    print("=====")
    same = rebuilt == trace["prompt_hash"] and messages == trace["prompt"]
    print(f"prompt_hash recorded {trace['prompt_hash'][:16]}  rebuilt {rebuilt[:16]}  -> "
          f"{'MATCH' if same else 'MISMATCH'}")
    return 0 if same else 3


if __name__ == "__main__":
    sys.exit(main())
