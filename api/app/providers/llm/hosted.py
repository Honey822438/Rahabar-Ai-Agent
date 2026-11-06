"""Hosted free-tier provider: Gemini first, Groq only if its key exists (section 3.5).

Both speak the OpenAI chat format. Keys arrive from a Kubernetes Secret created on the command
line, and never appear in a committed file or a log line.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from ...config import Settings
from ...schemas import Answer, Passage
from ...services.prompt import build_messages
from ...services.telemetry import record_generation

log = logging.getLogger("rahbar.hosted")

# Worth trying the next model: rate limits, outages, a model that no longer exists.
FAILOVER_STATUS = {404, 408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class _Target:
    label: str
    base_url: str
    model: str
    api_key: str
    extra: dict[str, Any]


class HostedProvider:
    name = "hosted"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.targets = [_Target("gemini", settings.hosted_base_url, settings.llm_model,
                                settings.llm_api_key, {})]
        if settings.groq_api_key:
            self.targets += [
                _Target("groq", settings.groq_base_url, model.strip(), settings.groq_api_key,
                        {"tool_choice": "none"})
                for model in settings.groq_models.split(",") if model.strip()
            ]

    def _call(self, target: _Target, messages: list[dict[str, str]]) -> httpx.Response:
        return httpx.post(
            target.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {target.api_key}"},
            json={
                "model": target.model,
                "messages": messages,
                "temperature": self.settings.temperature,
                "response_format": {"type": "json_object"},
                **target.extra,
            },
            timeout=self.settings.llm_timeout_seconds,
        )

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        """Raises on failure; the answer service retries once and then falls back."""
        messages = build_messages(question, passages)
        failure: Exception = RuntimeError("no hosted provider is configured")
        for target in self.targets:
            try:
                response = self._call(target, messages)
            except httpx.HTTPError as exc:
                failure = exc
                log.warning("provider unreachable", extra={"target": target.label,
                                                           "model": target.model,
                                                           "error": type(exc).__name__})
                continue
            if response.status_code in FAILOVER_STATUS:
                failure = RuntimeError(f"{target.label} returned {response.status_code}")
                log.warning("provider failed", extra={"target": target.label,
                                                      "model": target.model,
                                                      "status": response.status_code})
                continue
            if response.is_error:
                # The status only: the error body can echo request details.
                log.error("provider rejected the request", extra={"target": target.label,
                                                                  "model": target.model,
                                                                  "status": response.status_code})
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage") or {}
            record_generation(target.model, usage.get("prompt_tokens", 0),
                              usage.get("completion_tokens", 0))
            return Answer.model_validate_json(content)
        raise failure
