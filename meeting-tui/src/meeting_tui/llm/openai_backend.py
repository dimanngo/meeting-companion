"""OpenAI API LLM backend."""

from __future__ import annotations

from typing import AsyncIterator, cast

from openai import AsyncOpenAI
from openai._streaming import AsyncStream
from openai.types.chat import ChatCompletionChunk

from meeting_tui.llm.base import ChatMessage, LLMBackend


class OpenAIBackend(LLMBackend):
    """OpenAI API LLM backend."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def complete(self, messages: list[ChatMessage], context: str = "") -> str:
        payload = self._build_messages(messages, context)
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=payload,  # type: ignore[arg-type]
        )
        return response.choices[0].message.content or ""

    async def stream(
        self, messages: list[ChatMessage], context: str = ""
    ) -> AsyncIterator[str]:
        payload = self._build_messages(messages, context)
        stream = cast(
            AsyncStream[ChatCompletionChunk],
            await self._client.chat.completions.create(
                model=self.model,
                messages=payload,  # type: ignore[arg-type]
                stream=True,
            ),
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def _build_messages(
        messages: list[ChatMessage], context: str
    ) -> list[dict[str, str]]:
        payload: list[dict[str, str]] = []
        if context:
            payload.append({"role": "system", "content": context})
        for message in messages:
            payload.append({"role": message.role, "content": message.content})
        return payload

    async def close(self) -> None:
        await self._client.close()
