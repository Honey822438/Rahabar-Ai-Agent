"""Check the hand-edited eval inputs, so a bad edit fails the PR instead of the pipeline.

    python scripts/validate_inputs.py          # exit 0 = all valid, 1 = errors listed

Checks eval/golden.jsonl, eval/live_queries.jsonl, eval/pairs/*.jsonl, eval/labels/*.jsonl:
valid JSON per line, required fields with the right types and values, unique ids, no
duplicate questions, and the minimum counts the assignment asks for.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"

GOLDEN = {"id": str, "question": str, "type": str, "source": str, "reviewed": bool,
          "relevant": list, "expect": str, "must_abstain": bool}
RELEVANT = {"doc_id": str, "file": str, "section": str}
LIVE = {"id": str, "query": str, "in_domain": bool, "topic": str}
PAIR = {"id": str, "a": str, "b": str}
LABEL = {"id": str, "question_id": str, "faithful": bool}


def read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{n}: not valid JSON ({exc.msg})")
            continue
        if not isinstance(row, dict):
            errors.append(f"{path.name}:{n}: each line must be a JSON object")
            continue
        row["_line"] = n
        rows.append(row)
    return rows


def check_fields(path: Path, rows: list[dict[str, Any]], schema: dict[str, type],
                 errors: list[str]) -> None:
    for row in rows:
        where = f"{path.name}:{row['_line']}"
        for key, kind in schema.items():
            if key not in row:
                errors.append(f"{where}: missing field '{key}'")
            elif not isinstance(row[key], kind):
                errors.append(f"{where}: '{key}' must be {kind.__name__}, "
                              f"got {type(row[key]).__name__}")
            elif kind is str and key != "expect" and not row[key].strip():
                errors.append(f"{where}: '{key}' is empty")


def check_unique(path: Path, rows: list[dict[str, Any]], key: str, errors: list[str]) -> None:
    seen = Counter(str(r.get(key, "")).strip().lower() for r in rows)
    errors += [f"{path.name}: duplicate {key} '{v}'" for v, n in seen.items() if n > 1 and v]


def validate_golden(path: Path, errors: list[str]) -> None:
    rows = read_jsonl(path, errors)
    check_fields(path, rows, GOLDEN, errors)
    check_unique(path, rows, "id", errors)
    check_unique(path, rows, "question", errors)
    for row in rows:
        where = f"{path.name}:{row['_line']}"
        if row.get("type") not in ("answerable", "unanswerable", "hard"):
            errors.append(f"{where}: type must be answerable / unanswerable / hard")
        if row.get("source") not in ("human", "synthetic"):
            errors.append(f"{where}: source must be human / synthetic")
        unanswerable = row.get("type") == "unanswerable"
        if unanswerable != bool(row.get("must_abstain")):
            errors.append(f"{where}: must_abstain must be true exactly for unanswerable")
        if unanswerable and row.get("relevant"):
            errors.append(f"{where}: an unanswerable question lists no relevant chunks")
        if not unanswerable and not row.get("relevant"):
            errors.append(f"{where}: needs at least one relevant {{doc_id, file, page, section}}")
        if not unanswerable and not str(row.get("expect", "")).strip():
            errors.append(f"{where}: needs a non-empty expect")
        for item in row.get("relevant") or []:
            if not isinstance(item, dict):
                errors.append(f"{where}: each relevant item must be an object")
                continue
            for key, kind in RELEVANT.items():
                if not isinstance(item.get(key), kind) or not item[key]:
                    errors.append(f"{where}: relevant item needs '{key}'")
            if not isinstance(item.get("page"), (int, type(None))):
                errors.append(f"{where}: relevant page must be an integer or null")
    counts = Counter(r.get("type") for r in rows)
    human = sum(r.get("source") == "human" for r in rows)
    synthetic = sum(r.get("source") == "synthetic" for r in rows)
    for label, have, need in (("questions", len(rows), 25), ("answerable", counts["answerable"], 15),
                              ("unanswerable", counts["unanswerable"], 5),
                              ("hard", counts["hard"], 5), ("human", human, 8),
                              ("synthetic", synthetic, 8)):
        if have < need:
            errors.append(f"{path.name}: {have} {label}, need >= {need}")


def validate_simple(path: Path, schema: dict[str, type], unique: list[str],
                    errors: list[str]) -> list[dict[str, Any]]:
    rows = read_jsonl(path, errors)
    check_fields(path, rows, schema, errors)
    for key in unique:
        check_unique(path, rows, key, errors)
    return rows


def validate(eval_dir: Path = EVAL) -> list[str]:
    errors: list[str] = []
    golden = eval_dir / "golden.jsonl"
    if golden.exists():
        validate_golden(golden, errors)
    else:
        errors.append("eval/golden.jsonl is missing")
    live_path = eval_dir / "live_queries.jsonl"
    if live_path.exists():
        live = validate_simple(live_path, LIVE, ["id", "query"], errors)
        if len(live) < 40:
            errors.append(f"live_queries.jsonl: {len(live)} queries, need >= 40")
        if sum(r.get("in_domain") is False for r in live) < 12:
            errors.append("live_queries.jsonl: need >= 12 off-topic (in_domain: false) queries")
    else:
        errors.append("eval/live_queries.jsonl is missing")
    for name in ("paraphrase", "unrelated"):
        path = eval_dir / "pairs" / f"{name}.jsonl"
        if not path.exists():
            errors.append(f"eval/pairs/{name}.jsonl is missing")
            continue
        rows = validate_simple(path, PAIR, ["id"], errors)
        if len(rows) < 15:
            errors.append(f"{path.name}: {len(rows)} pairs, need >= 15")
    for path in sorted((eval_dir / "labels").glob("*.jsonl")):
        validate_simple(path, LABEL, ["id"], errors)
    return errors


def main() -> int:
    errors = validate()
    for error in errors:
        print(f"ERROR {error}")
    print("inputs valid" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
