"""Google Gemini API LLM backend."""

from __future__ import annotations

from typing import AsyncIterator

from meeting_tui.llm.base import LLMBackend


class GeminiBackend(LLMBackend):
    """Google Gemini API LLM backend using google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-preview",
        thinking_level: str = "low",
    ):
        from google import genai

        self.model = model
        self.thinking_level = thinking_level
        self._client = genai.Client(api_key=api_key)

    async def complete(self, prompt: str, context: str = "") -> str:
        from google.genai import types

        contents = self._build_contents(prompt, context)
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

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        from google.genai import types

        contents = self._build_contents(prompt, context)
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=self._thinking_budget(),
            ),
        )
        async for chunk in self._client.aio.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    def _thinking_budget(self) -> int:
        """Map thinking level string to token budget."""
        budgets = {"minimal": 128, "low": 1024, "medium": 4096, "high": 16384}
        return budgets.get(self.thinking_level, 1024)

    @staticmethod
    def _build_contents(prompt: str, context: str) -> list:
        """Build contents for the Gemini API."""
        from google.genai import types

        contents = []
        if context:
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=f"Context:\n{context}")],
            ))
            contents.append(types.Content(
                role="model",
                parts=[types.Part(text="I'll use this context to help answer your questions.")],
            ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ))
        return contents

    async def close(self) -> None:
        pass  # google-genai client doesn't need explicit cleanup
