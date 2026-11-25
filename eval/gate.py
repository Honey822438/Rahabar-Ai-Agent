"""C2 release gate: compare a candidate suite run with the baseline using config/gate.yaml.

    python eval/gate.py eval/results/<candidate>.json [--baseline B.json] [--config config/gate.yaml]

Prints one row per rule (PASS/FAIL) and writes eval/results/gate-<label>.md.
Exit code: 0 = pass, 1 = at least one rule failed, 2 = a metric is missing (also a fail).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def metric(result: dict[str, Any], name: str) -> float | None:
    level, key = name.split(".", 1)
    block = result.get(level) or {}
    value = block.get("summary", block).get(key)
    return None if value is None or isinstance(value, (dict, list, str)) else float(value)


def check(rule: dict[str, Any], base: float | None, cand: float | None) -> tuple[bool, str]:
    kind, limit = rule["kind"], float(rule["value"])
    if cand is None or (kind.startswith("max_") and kind != "max" and base is None):
        return False, "metric missing"
    if kind == "min":
        return cand >= limit, f">= {limit}"
    if kind == "max":
        return cand <= limit, f"<= {limit}"
    if kind == "max_drop":
        return base - cand <= limit + 1e-9, f"drop <= {limit} (>= {base - limit:.4f})"
    if kind == "max_rise":
        return cand - base <= limit + 1e-9, f"rise <= {limit} (<= {base + limit:.4f})"
    raise ValueError(f"unknown rule kind {kind}")


def main() -> int:
    p = argparse.ArgumentParser(description="RAHBAR release gate")
    p.add_argument("candidate", type=Path)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--config", type=Path,
                   default=Path(os.environ.get("GATE_CONFIG", ROOT / "config" / "gate.yaml")))
    p.add_argument("--out-dir", type=Path, default=ROOT / "eval" / "results")
    args = p.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    base_path = args.baseline or ROOT / config["baseline"]
    base = json.loads(base_path.read_text(encoding="utf-8"))
    cand = json.loads(args.candidate.read_text(encoding="utf-8"))

    rows, failed, missing = [], 0, 0
    for rule in config["rules"]:
        b, c = metric(base, rule["metric"]), metric(cand, rule["metric"])
        ok, bar = check(rule, b, c)
        failed += not ok
        missing += c is None
        rows.append(f"| {rule['metric']} | {b if b is not None else '-'} | "
                    f"{c if c is not None else '-'} | {bar} | {'PASS' if ok else '**FAIL**'} |")
    verdict = "PASS" if not failed else "FAIL"
    report = "\n".join([
        f"# Release gate: {cand['label']} ({cand['config']['collection']}) -> {verdict}", "",
        f"baseline `{base_path.name}` ({base['config']['collection']}), candidate "
        f"`{args.candidate.name}`, rules `{args.config.name}`", "",
        "| metric | baseline | candidate | rule | result |", "|---|---|---|---|---|", *rows, "",
        f"{len(rows) - failed}/{len(rows)} rules passed -> **{verdict}**", ""])
    print(report)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"gate-{cand['label']}.md").write_text(report, encoding="utf-8")
    return 2 if missing else (1 if failed else 0)


if __name__ == "__main__":
    sys.exit(main())
