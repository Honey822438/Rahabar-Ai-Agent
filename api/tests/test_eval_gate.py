"""The CI gate's arithmetic, on hand-written rows. No API is called."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "eval" / "run_eval.py"
_spec = importlib.util.spec_from_file_location("run_eval", _path)
assert _spec and _spec.loader
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

A = {"source": "a.pdf", "section": "Attendance", "page": 1}
B = {"source": "b.pdf", "section": "Fees", "page": 2}


def row(kind: str, relevant: list, retrieved: list, citations: list, answered: bool = True,
        must_abstain: bool = False) -> dict:
    return {"id": kind, "type": kind, "must_abstain": must_abstain, "relevant": relevant,
            "expect": None, "seconds": 0.1,
            "response": {"answer": "x", "retrieved": retrieved, "citations": citations,
                         "answered_from_context": answered}}


def test_recall_respects_k_and_counts_each_relevant_pair() -> None:
    retrieved = [B, A]
    assert run_eval.recall_at_k([A], retrieved, 1) == 0.0
    assert run_eval.recall_at_k([A], retrieved, 2) == 1.0
    assert run_eval.recall_at_k([A, {"source": "c.pdf", "section": "X"}], retrieved, 2) == 0.5


def test_recall_is_none_without_relevant_passages() -> None:
    assert run_eval.recall_at_k([], [A], 5) is None


def test_recall_matches_a_heading_with_extra_text() -> None:
    wanted = {"source": "a.pdf", "section": "attendance"}
    found = {"source": "a.pdf", "section": "1. Attendance Requirements"}
    assert run_eval.recall_at_k([wanted], [found], 1) == 1.0


def test_citation_validity_catches_a_fabricated_citation() -> None:
    fake = {"source": "fake.pdf", "section": "None", "page": 9}
    response = {"retrieved": [A], "citations": [A, fake]}
    assert run_eval.citation_validity(response) == 0.5
    assert run_eval.citation_validity({"retrieved": [A], "citations": []}) is None


def good_results() -> dict:
    return run_eval.summarise([
        row("ordinary", [A], [A], [A]),
        row("abstain", [], [B], [], answered=False, must_abstain=True),
    ])


def test_summary_reports_by_type() -> None:
    results = good_results()
    assert results["recall_at_5_by_type"] == {"ordinary": 1.0}
    assert results["abstention_correctness"] == 1.0 and results["citation_validity"] == 1.0


def test_gate_passes_good_results() -> None:
    assert run_eval.gate(good_results(), {"recall_at_5": 1.0}) == []


def test_gate_fails_on_a_recall_drop_of_more_than_five_points() -> None:
    assert run_eval.gate(good_results(), {"recall_at_5": 1.06})
    assert run_eval.gate(good_results(), {"recall_at_5": 1.05}) == []


def test_gate_fails_when_a_must_abstain_question_is_answered() -> None:
    results = run_eval.summarise([row("abstain", [], [A], [A], must_abstain=True)])
    assert "answered from context" in run_eval.gate(results, None)[0]


def test_gate_fails_on_invalid_citations() -> None:
    fake = {"source": "fake.pdf", "section": "None", "page": 9}
    results = run_eval.summarise([row("ordinary", [A], [A], [fake])])
    assert "citation validity" in run_eval.gate(results, None)[0]


def test_recall_counts_one_alternative_as_the_whole_passage() -> None:
    other = {"source": "c.pdf", "section": "X"}
    relevant = [{**other, "alternatives": [A]}]
    assert run_eval.recall_at_k(relevant, [A], 5) == 1.0
    assert run_eval.recall_at_k(relevant, [other], 5) == 1.0
    assert run_eval.recall_at_k(relevant, [{"source": "z.pdf", "section": "Y"}], 5) == 0.0
