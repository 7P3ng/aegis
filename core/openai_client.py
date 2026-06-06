"""Real OpenAI client (chat completions over httpx). Reads OPENAI_API_KEY from env only.

Used as a cross-model *target* (e.g. gpt-4o-mini) so Aegis can compare injection/canary
robustness across providers. Fails loud if the key is absent — a public repo never hardcodes
keys, and a silent fallback would corrupt the cross-model cost/ASR numbers.
"""
from __future__ import annotations

import os
from time import perf_counter

import httpx

from core.pricing import PRICING, cost
from core.types import ModelError, ModelResponse, RateLimitError

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, timeout: float = 120.0) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export it before running a cross-model gpt target."
            )
        self._key = key
        self._base = (base_url or os.environ.get("OPENAI_BASE_URL")
                      or "https://api.openai.com/v1").rstrip("/")
        self._model = model or os.environ.get("OPENAI_MODEL") or _DEFAULT_MODEL
        self._timeout = timeout

    def complete(self, *, model, system, messages, max_tokens,
                 temperature=0.0, salt="") -> ModelResponse:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
        }
        t0 = perf_counter()
        try:
            r = httpx.post(
                f"{self._base}/chat/completions",
                headers={"Authorization": f"Bearer {self._key}",
                         "Content-Type": "application/json"},
                json=payload, timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ModelError(f"openai transport error: {exc}") from exc
        latency = (perf_counter() - t0) * 1000.0
        if r.status_code == 429:
            raise RateLimitError(f"openai 429: {r.text[:200]}")
        if r.status_code >= 400:
            raise ModelError(f"openai {r.status_code}: {r.text[:300]}")
        data = r.json()
        choice = data["choices"][0]
        text = choice["message"]["content"] or ""
        usage = data.get("usage", {})
        in_tok = int(usage.get("prompt_tokens", 0))
        out_tok = int(usage.get("completion_tokens", 0))
        priced = self._model if self._model in PRICING else _DEFAULT_MODEL
        return ModelResponse(
            text=text, model=priced, input_tokens=in_tok, output_tokens=out_tok,
            cost_usd=cost(priced, in_tok, out_tok), latency_ms=latency,
            stop_reason=choice.get("finish_reason", "stop"),
        )
