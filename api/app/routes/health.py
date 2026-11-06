"""Liveness and readiness (section 4.3). They answer different questions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from ..config import Settings
from ..retrieval.base import Retriever

log = logging.getLogger("rahbar.health")

router = APIRouter()


def embed_pin_conflict(retriever: Retriever, settings: Settings) -> str | None:
    """Section 4.4: describe a mismatch between the index and this process, and log it."""
    indexed_model = retriever.index_metadata().get("embed_model")
    if indexed_model == settings.embed_model:
        return None
    conflict = (f"embed_model mismatch: index built with {indexed_model!r}, "
                f"EMBED_MODEL is {settings.embed_model!r}")
    log.error("refusing readiness: embedding model conflict",
              extra={"indexed_model": indexed_model, "embed_model": settings.embed_model})
    return conflict


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Is the process alive? Must never touch Chroma, Redis or the LLM."""
    return {"status": "alive"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, object]:
    """Can it take traffic? 503, naming what failed, unless every dependency is usable."""
    state = request.app.state
    checks: dict[str, str] = {}
    try:
        count = state.retriever.count()
        checks["chroma"] = "ok"
        checks["collection"] = "ok" if count > 0 else "collection is empty"
        checks["embed_pin"] = embed_pin_conflict(state.retriever, state.settings) or "ok"
    except Exception as exc:
        checks["chroma"] = f"unreachable or no collection: {type(exc).__name__}"
    if state.cache is not None:
        try:
            state.cache.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"unreachable: {type(exc).__name__}"
    if any(value != "ok" for value in checks.values()):
        response.status_code = 503
        return {"status": "not ready", "checks": checks}
    return {"status": "ready", "checks": checks}
