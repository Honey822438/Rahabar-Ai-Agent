"""Compare two suite result files metric by metric (B4 stochasticity, C1 baseline vs candidate).

    python eval/compare.py eval/results/A.json eval/results/B.json [--out eval/results/x.md]

Prints every numeric metric of the module, component, noise and end-to-end levels with the
difference B - A, plus which questions changed outcome (retrieval hit, answered, expect found).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

LEVELS = ("module", "component", "noise", "e2e")


def flat(result: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for level in LEVELS:
        block = result.get(level) or {}
        values = block.get("summary", block) if level != "noise" else block.get("delta", {})
        prefix = "noise delta " if level == "noise" else ""
        for key, value in values.items():
            if isinstance(value, bool):
                out[f"{level}.{prefix}{key}"] = float(value)
            elif isinstance(value, (int, float)):
                out[f"{level}.{prefix}{key}"] = float(value)
    return out


def question_changes(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    changes = []
    comp_a = {r["id"]: r for r in (a.get("component") or {}).get("per_question", [])}
    comp_b = {r["id"]: r for r in (b.get("component") or {}).get("per_question", [])}
    for qid in sorted(comp_a.keys() & comp_b.keys()):
        ra, rb = comp_a[qid]["first_relevant_rank"], comp_b[qid]["first_relevant_rank"]
        if ra != rb:
            changes.append(f"{qid}: first relevant rank {ra} -> {rb}")
    e_a = {r["id"]: r for r in (a.get("e2e") or {}).get("per_question", [])}
    e_b = {r["id"]: r for r in (b.get("e2e") or {}).get("per_question", [])}
    for qid in sorted(e_a.keys() & e_b.keys()):
        for key in ("answered", "expect_found", "fallback"):
            if e_a[qid].get(key) != e_b[qid].get(key):
                changes.append(f"{qid}: {key} {e_a[qid].get(key)} -> {e_b[qid].get(key)}")
        if e_a[qid].get("answer") != e_b[qid].get("answer") and e_a[qid]["answered"] \
                and e_b[qid]["answered"]:
            changes.append(f"{qid}: answer wording differs")
    return changes


def compare(a: dict[str, Any], b: dict[str, Any]) -> str:
    fa, fb = flat(a), flat(b)
    width = max(len(k) for k in fa | fb)
    lines = [f"A = {a['label']} ({a['timestamp']}, {a['config']['collection']})",
             f"B = {b['label']} ({b['timestamp']}, {b['config']['collection']})", "",
             f"| {'metric':<{width}} | {'A':>10} | {'B':>10} | {'B - A':>9} |",
             f"|{'-' * (width + 2)}|{'-' * 12}|{'-' * 12}|{'-' * 11}|"]
    for key in sorted(fa.keys() | fb.keys(), key=lambda k: (LEVELS.index(k.split('.')[0]), k)):
        va, vb = fa.get(key), fb.get(key)
        diff = f"{vb - va:+.4f}" if va is not None and vb is not None else "-"
        lines.append(f"| {key:<{width}} | {'' if va is None else f'{va:.4f}':>10} | "
                     f"{'' if vb is None else f'{vb:.4f}':>10} | {diff:>9} |")
    changes = question_changes(a, b)
    lines += ["", f"Per-question changes ({len(changes)}):"] + [f"- {c}" for c in changes]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two suite result files.")
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    text = compare(json.loads(args.a.read_text()), json.loads(args.b.read_text()))
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
