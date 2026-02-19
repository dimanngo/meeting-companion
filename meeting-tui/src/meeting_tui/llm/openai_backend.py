"""OpenAI API LLM backend."""

from __future__ import annotations

from typing import AsyncIterator

from openai import AsyncOpenAI

from meeting_tui.llm.base import LLMBackend


class OpenAIBackend(LLMBackend):
    """OpenAI API LLM backend."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def complete(self, prompt: str, context: str = "") -> str:
        messages = self._build_messages(prompt, context)
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        messages = self._build_messages(prompt, context)
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def _build_messages(prompt: str, context: str) -> list[dict]:
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def close(self) -> None:
        await self._client.close()
