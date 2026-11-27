"""Shared pieces of the offline test suite (Part B): config, golden set, API imports.

The suite imports the API's own retriever and answer service, so it measures exactly what
the service does (same prefixes, filters, exact-term boost, relevance floor, citation check).
Settings come from the same environment variables as the API (the ConfigMap in the cluster).
"""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "eval"
sys.path.insert(0, str(ROOT / "api"))

# Defaults for a local run against the docker Chroma on :8001 and host Ollama.
LOCAL_DEFAULTS = {
    "RETRIEVER": "chroma", "LLM_PROVIDER": "hosted", "CHROMA_HOST": "localhost",
    "CHROMA_PORT": "8001", "OLLAMA_URL": "http://localhost:11434", "TOP_K": "5",
    "RELEVANCE_FLOOR": "0.65", "TEMPERATURE": "0.2", "LLM_MODEL": "gemini-flash-lite-latest",
    "HOSTED_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def load_env() -> None:
    """Fill unset variables from LOCAL_DEFAULTS and the gitignored .env (keys never printed)."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"'))
    for key, value in LOCAL_DEFAULTS.items():
        os.environ.setdefault(key, value)
    # chromadb's client parses a .env in the working directory (and needs python-dotenv for
    # it); run from eval/ so it never sees the repo's .env.
    os.chdir(EVAL)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    os.environ["LLM_SEED"] = str(seed)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def load_golden(path: Path | None = None) -> list[dict[str, Any]]:
    return read_jsonl(path or EVAL / "golden.jsonl")


def settings(collection: str | None = None) -> Any:
    load_env()
    if collection:
        os.environ["CHROMA_COLLECTION"] = collection
    from app.config import get_settings
    return get_settings()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q / 100 * (len(ordered) - 1))))
    return ordered[index]


def norm_section(section: str) -> str:
    return " ".join(section.lower().split())


def is_relevant(passage: Any, relevant: list[dict[str, Any]]) -> bool:
    """A retrieved chunk is relevant if it comes from a listed file and either sits under the
    listed section or starts on the listed page."""
    for item in relevant:
        if passage.source != item["file"]:
            continue
        if norm_section(passage.section) == norm_section(item["section"]):
            return True
        if item.get("page") and passage.page == item["page"]:
            return True
    return False
