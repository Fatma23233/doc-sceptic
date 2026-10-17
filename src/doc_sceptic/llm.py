from __future__ import annotations

import time
from typing import Any

import requests

from .config import Settings


class LLMClient:
    def __init__(self, s: Settings | None = None):
        self.s = s or Settings()

    @staticmethod
    def _extract_chat_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""

        message = choices[0].get("message") or {}
        content = message.get("content")

        if content is None:
            return ""

        if isinstance(content, str):
            return content.strip()

        # Defensive support for APIs returning structured content parts.
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(part for part in parts if part.strip()).strip()

        return str(content).strip()

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float | None:
        value = response.headers.get("retry-after")
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    def _post_chat_completion(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
        max_attempts: int = 3,
    ) -> str:
        last_empty_payload: dict[str, Any] | None = None

        for attempt in range(1, max_attempts + 1):
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )

            # Respect temporary provider rate limits/server errors.
            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt >= max_attempts:
                    response.raise_for_status()

                retry_after = self._retry_after_seconds(response)
                wait_seconds = (
                    retry_after + 1.0
                    if retry_after is not None
                    else min(5.0 * (2 ** (attempt - 1)), 30.0)
                )
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            data = response.json()
            content = self._extract_chat_content(data)

            if content:
                return content

            last_empty_payload = data

            # A successful HTTP response with empty assistant text is retried.
            if attempt < max_attempts:
                time.sleep(1.5 * attempt)

        finish_reason = None
        if last_empty_payload:
            choices = last_empty_payload.get("choices") or []
            if choices:
                finish_reason = choices[0].get("finish_reason")

        raise RuntimeError(
            "Le fournisseur LLM a retourné une réponse vide après "
            f"{max_attempts} tentative(s). finish_reason={finish_reason!r}."
        )

    def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
    ) -> str:
        provider = self.s.llm_provider

        if provider == "mock":
            return "Mode mock actif."

        if provider in {"groq", "openai"}:
            base_url = (
                self.s.groq_base_url
                if provider == "groq"
                else self.s.openai_base_url
            )

            payload: dict[str, Any] = {
                "model": self.s.llm_model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }

            # Give the model an explicit completion budget when supported by the
            # OpenAI-compatible chat endpoint. This is especially useful for
            # longer grounded answers.
            payload["max_completion_tokens"] = 4096
            if provider == "groq" and (
                self.s.llm_model.startswith("openai/gpt-oss-")
                or self.s.llm_model == "qwen/qwen3.8-27b"
            ):
                payload["reasoning_effort"] = "low"
                
            return self._post_chat_completion(
                url=base_url.rstrip("/") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.s.llm_api_key}",
                    "Content-Type": "application/json",
                },
                payload=payload,
                timeout=120,
                max_attempts=3,
            )

        if provider == "ollama":
            response = requests.post(
                self.s.ollama_base_url.rstrip("/") + "/api/chat",
                json={
                    "model": self.s.llm_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=180,
            )
            response.raise_for_status()
            content = (response.json().get("message") or {}).get("content")
            if not content or not str(content).strip():
                raise RuntimeError("Ollama a retourné une réponse vide.")
            return str(content).strip()

        raise ValueError(f"Fournisseur LLM non supporté : {provider}")
