"""Google Gemini API LLM backend."""

from __future__ import annotations

from typing import AsyncIterator

from meeting_tui.llm.base import ChatMessage, LLMBackend


class GeminiBackend(LLMBackend):
    """Google Gemini API LLM backend using google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        thinking_level: str = "low",
    ):
        from google import genai

        self.model = model
        self.thinking_level = thinking_level
        self._client = genai.Client(api_key=api_key)

    async def complete(self, messages: list[ChatMessage], context: str = "") -> str:
        from google.genai import types

        contents = self._build_contents(messages, context)
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=self._thinking_budget(),
            ),
        )
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        return response.text or ""

    async def stream(
        self, messages: list[ChatMessage], context: str = ""
    ) -> AsyncIterator[str]:
        from google.genai import types

        contents = self._build_contents(messages, context)
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=self._thinking_budget(),
            ),
        )
        stream = await self._client.aio.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config,
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    def _thinking_budget(self) -> int:
        """Map thinking level string to token budget."""
        budgets = {"minimal": 128, "low": 1024, "medium": 4096, "high": 16384}
        return budgets.get(self.thinking_level, 1024)

    @staticmethod
    def _build_contents(messages: list[ChatMessage], context: str) -> list:
        """Build contents for the Gemini API."""
        from google.genai import types

        contents = []
        if context:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"Context:\n{context}")],
                )
            )
        for message in messages:
            role = "model" if message.role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=message.content)],
                )
            )
        return contents

    async def close(self) -> None:
        pass  # google-genai client doesn't need explicit cleanup
