"""One trace record per query (A3 D1), to stdout and to TRACE_FILE (a JSON line each).

A trace holds everything needed to explain an answer later without re-running it: the query,
the embedding model + version, collection and index generation, filters, every retrieved
chunk (ids, doc ids/versions, scores, text, boost/drop marks), the full prompt and its sha256,
model + parameters + tokens, the response and citations, guardrail actions, per-stage latency
and cache hit/miss. `python -m tools.trace <id>` rebuilds the prompt from it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("rahbar.trace")
_lock = threading.Lock()


def prompt_hash(messages: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False)
                          .encode()).hexdigest()


def emit(record: dict[str, Any], trace_file: str) -> None:
    """stdout (the pod log) always; the file when configured. Never fails the request."""
    log.info("trace", extra={"trace": record})
    if not trace_file:
        return
    try:
        path = Path(trace_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with _lock, path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError as exc:
        log.warning("trace file not writable", extra={"error": type(exc).__name__,
                                                      "trace_file": trace_file})
