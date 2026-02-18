"""Ollama LLM backend — local inference via Ollama HTTP API."""

from __future__ import annotations

from typing import AsyncIterator

import httpx

from meeting_tui.llm.base import LLMBackend


class OllamaBackend(LLMBackend):
    """Ollama local LLM backend using HTTP API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    async def complete(self, prompt: str, context: str = "") -> str:
        messages = self._build_messages(prompt, context)
        response = await self._client.post(
            "/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        messages = self._build_messages(prompt, context)
        async with self._client.stream(
            "POST",
            "/api/chat",
            json={"model": self.model, "messages": messages, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    import json

                    data = json.loads(line)
                    if content := data.get("message", {}).get("content", ""):
                        yield content

    @staticmethod
    def _build_messages(prompt: str, context: str) -> list[dict]:
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def close(self) -> None:
        await self._client.aclose()
