"""Ollama provider: ollama-host or ollama-incluster, the secondary mode (section 3.5)."""

from __future__ import annotations

import httpx

from ...config import Settings
from ...schemas import Answer, Passage
from ...services.prompt import build_messages


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        """Raises on failure; the answer service retries once and then falls back."""
        response = httpx.post(
            f"{self.settings.ollama_url}/api/chat",
            json={
                "model": self.settings.llm_model,
                "messages": build_messages(question, passages),
                "format": Answer.model_json_schema(),
                "stream": False,
                "options": {"temperature": self.settings.temperature},
            },
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return Answer.model_validate_json(response.json()["message"]["content"])
