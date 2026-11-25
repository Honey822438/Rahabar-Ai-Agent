"""D3: monitoring summary over a time window of traces.

    python -m tools.metrics_summary [--file F] [--since 2026-11-25T10:00] [--until ...] [--last 60]

--last N = the last N minutes. Reports: requests, top-1 similarity distribution (min, p10, p50,
p90, max + a histogram), abstention rate, cache hit rate, fallback rate, p50/p95 latency per
stage (embed, cache, retrieve, guardrail, generate, total), injection attempts flagged (query
and retrieved-chunk rails), tokens. --json prints the same as JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT = os.environ.get("TRACE_FILE", "/data/traces/traces.jsonl")


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, max(0, round(q / 100 * (len(s) - 1))))]


def parse(ts: str) -> datetime:
    ts = ts.rstrip("Z")
    fmt = "%Y-%m-%dT%H:%M:%S" if len(ts) > 16 else "%Y-%m-%dT%H:%M"
    return datetime.strptime(ts[:19], fmt).replace(tzinfo=timezone.utc)


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    top1 = [r["top1_score"] for r in rows if r.get("top1_score") is not None]
    bins = [0.0, 0.5, 0.6, 0.65, 0.7, 0.8, 1.01]
    hist = {f"{lo:.2f}-{min(hi, 1):.2f}": sum(lo <= s < hi for s in top1)
            for lo, hi in zip(bins, bins[1:])}
    stages = sorted({k for r in rows for k in r.get("latency_ms", {})})
    rails: dict[str, int] = {}
    for r in rows:
        for g in r.get("guardrails", []):
            rails[f"{g['rail']}:{g['action']}"] = rails.get(f"{g['rail']}:{g['action']}", 0) + 1
    flagged = sum(any(g["rail"].endswith("injection") for g in r.get("guardrails", []))
                  for r in rows)
    lookups = [r for r in rows if r.get("cache_lookup")]
    return {
        "requests": n,
        "window": [rows[0]["ts"], rows[-1]["ts"]] if rows else None,
        "top1_similarity": {"min": pct(top1, 0), "p10": pct(top1, 10), "p50": pct(top1, 50),
                            "p90": pct(top1, 90), "max": pct(top1, 100), "histogram": hist},
        "abstention_rate": round(sum(r["abstained"] for r in rows) / n, 4) if n else None,
        "cache_hit_rate": round(sum(r["cached"] for r in lookups) / len(lookups), 4)
        if lookups else None,
        "fallback_rate": round(sum(r["fallback"] for r in rows) / n, 4) if n else None,
        "latency_ms": {s: {"p50": pct([r["latency_ms"][s] for r in rows if s in r["latency_ms"]], 50),
                           "p95": pct([r["latency_ms"][s] for r in rows if s in r["latency_ms"]], 95)}
                       for s in stages},
        "injection_attempts_flagged": flagged,
        "guardrail_actions": rails,
        "tokens": {"in": sum(r["llm"].get("tokens_in") or 0 for r in rows),
                   "out": sum(r["llm"].get("tokens_out") or 0 for r in rows)},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--file", type=Path, default=Path(DEFAULT))
    p.add_argument("--since")
    p.add_argument("--until")
    p.add_argument("--last", type=float, help="minutes back from now")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    since = parse(args.since) if args.since else None
    until = parse(args.until) if args.until else None
    if args.last:
        since = datetime.now(timezone.utc) - timedelta(minutes=args.last)
    rows = []
    for line in args.file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        t = parse(r["ts"])
        if (since and t < since) or (until and t > until):
            continue
        rows.append(r)
    s = summarise(rows)
    if args.json:
        print(json.dumps(s, indent=2))
        return 0
    print(f"traces {args.file}  window {s['window']}  requests {s['requests']}")
    if not rows:
        return 0
    t = s["top1_similarity"]
    print(f"top-1 similarity  min {t['min']:.3f}  p10 {t['p10']:.3f}  p50 {t['p50']:.3f}  "
          f"p90 {t['p90']:.3f}  max {t['max']:.3f}")
    for b, c in t["histogram"].items():
        print(f"   {b}  {'#' * c} {c}")
    print(f"abstention rate   {s['abstention_rate']:.1%}")
    print(f"cache hit rate    {s['cache_hit_rate'] if s['cache_hit_rate'] is None else format(s['cache_hit_rate'], '.1%')}")
    print(f"fallback rate     {s['fallback_rate']:.1%}")
    print(f"injection flagged {s['injection_attempts_flagged']} requests   {s['guardrail_actions']}")
    print(f"tokens            in {s['tokens']['in']}  out {s['tokens']['out']}")
    print("latency ms        " + "  ".join(f"{k}: p50 {v['p50']} p95 {v['p95']}"
                                           for k, v in s["latency_ms"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
