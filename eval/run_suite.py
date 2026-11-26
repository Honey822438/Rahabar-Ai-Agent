"""B5: the whole offline test suite in one command (RAGOps 4.2.5, three levels).

    python eval/run_suite.py                         # module + component (+noise) + end-to-end
    python eval/run_suite.py --collection rahbar_c600 --label candidate
    python eval/run_suite.py --no-e2e                # no LLM calls (fast, free)

Writes eval/results/<timestamp>-<label>.json (every metric + per-question detail) and prints a
summary table. Seeds are fixed (--seed, default 42); see eval/suite/common.py.
Settings come from the environment (the API's ConfigMap keys); local defaults point at the
docker Chroma on :8001 and host Ollama.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from suite import common, component, e2e, module_level  # noqa: E402


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, cwd=common.ROOT, check=True).stdout.strip()
    except Exception:
        return "unknown"


def summary_table(result: dict[str, Any]) -> str:
    rows: list[tuple[str, str, Any]] = []
    for level in ("module", "component", "noise", "e2e"):
        block = result.get(level)
        if not block:
            continue
        values = block.get("summary", block)
        if level == "noise":
            values = {f"delta {k}": v for k, v in block["delta"].items()}
            values["questions with noise in top5"] = block["questions_with_noise_in_top5"]
        for key, value in values.items():
            if isinstance(value, (int, float, str, bool)) or value is None:
                rows.append((level, key, value))
            elif isinstance(value, dict):
                rows.append((level, key, json.dumps(value)))
    width = max(len(k) for _, k, _ in rows)
    lines = [f"{'level':<10} {'metric':<{width}}  value", "-" * (width + 30)]
    lines += [f"{lvl:<10} {key:<{width}}  {val}" for lvl, key, val in rows]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RAHBAR offline test suite.")
    parser.add_argument("--collection", help="Chroma collection (default: CHROMA_COLLECTION)")
    parser.add_argument("--label", default="baseline", help="name for this run")
    parser.add_argument("--golden", type=Path, default=common.EVAL / "golden.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-e2e", action="store_true", help="skip the LLM level")
    parser.add_argument("--no-judge", action="store_true", help="skip the faithfulness judge")
    parser.add_argument("--no-noise", action="store_true", help="skip the noise test")
    parser.add_argument("--rpm", type=float, default=8.0,
                        help="max hosted-LLM calls/minute (a pause between calls)")
    parser.add_argument("--temperature", default="0",
                        help="LLM temperature for the eval run (0: least run-to-run variation)")
    parser.add_argument("--out-dir", type=Path, default=common.EVAL / "results")
    parser.add_argument("--label-sheet", action="store_true",
                        help="write eval/labels/faithfulness_hand.jsonl for hand labels")
    parser.add_argument("--print", dest="print_file", type=Path, metavar="RESULT_JSON",
                        help="only print the summary table of an earlier result file")
    args = parser.parse_args()
    if args.print_file:
        result = json.loads(args.print_file.read_text(encoding="utf-8"))
        print(f"{result.get('label')} ({result.get('timestamp')}), "
              f"{result.get('golden_questions')} questions\n")
        print(summary_table(result))
        return 0

    common.seed_everything(args.seed)
    os.environ["TEMPERATURE"] = args.temperature
    settings = common.settings(args.collection)
    golden = common.load_golden(args.golden)
    started = time.time()
    result: dict[str, Any] = {
        "label": args.label, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": git_sha(), "seed": args.seed, "golden": str(args.golden.name),
        "golden_questions": len(golden),
        "config": {"collection": settings.collection, "embed_model": settings.embed_model,
                   "top_k": settings.top_k, "relevance_floor": settings.relevance_floor,
                   "llm_model": settings.llm_model, "temperature": settings.temperature},
    }
    print(f"[suite] {args.label}: collection={settings.collection}, {len(golden)} questions",
          flush=True)
    result["module"] = module_level.run(settings)
    print("[suite] module level done", flush=True)
    comp = component.evaluate(settings, golden)
    result["component"] = comp
    if not args.no_noise:
        result["noise"] = component.noise_test(settings, golden, comp)
    print("[suite] component level done", flush=True)
    if not args.no_e2e:
        result["e2e"] = e2e.evaluate(settings, golden, use_judge=not args.no_judge, rpm=args.rpm)
        if args.label_sheet:
            e2e.write_label_sheet({**result["e2e"], "run": result["timestamp"]})
        print("[suite] end-to-end level done", flush=True)
    result["seconds"] = round(time.time() - started, 1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = args.out_dir / f"{stamp}-{args.label}.json"
    table = summary_table(result)
    result["summary_table"] = table
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    shown = out.relative_to(common.ROOT) if out.is_relative_to(common.ROOT) else out
    print("\n" + table + f"\n\nwritten {shown}")   # /data/results in the eval Job
    return 0


if __name__ == "__main__":
    sys.exit(main())
