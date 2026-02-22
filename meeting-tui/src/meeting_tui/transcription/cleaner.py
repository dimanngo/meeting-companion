"""LLM-based transcript cleanup — fixes grammar, removes filler words, formats text."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meeting_tui.llm.base import LLMBackend

from meeting_tui.llm.base import ChatMessage

CLEANUP_PROMPT = """\
You are a transcript cleanup assistant. Clean up the following raw meeting transcript segment.

Rules:
- Fix grammar and punctuation
- Remove filler words (um, uh, like, you know, etc.)
- Keep the original meaning and speaker intent
- Do not add information that wasn't in the original
- Do not summarize — keep the full content
- Return ONLY the cleaned text, no explanations

Raw transcript:
{text}

Cleaned transcript:"""


class TranscriptCleaner:
    """Cleans raw transcription text using an LLM backend."""

    def __init__(self, llm: LLMBackend):
        self._llm = llm

    async def clean(self, raw_text: str) -> str:
        """Clean a raw transcript segment using the LLM."""
        if not raw_text.strip():
            return raw_text

        prompt = CLEANUP_PROMPT.format(text=raw_text)
        result = await self._llm.complete([ChatMessage(role="user", content=prompt)])
        return result.strip()
