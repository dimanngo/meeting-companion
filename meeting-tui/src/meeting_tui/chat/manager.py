"""Chat context manager — maintains conversation history and builds prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, TYPE_CHECKING

if TYPE_CHECKING:
    from meeting_tui.llm.base import LLMBackend


SYSTEM_PROMPT = """\
You are a helpful meeting assistant. You have access to the live meeting transcript below.
Answer questions about the meeting based on the transcript. Be concise and specific.
Reference timestamps when relevant. If something wasn't discussed in the transcript, say so.

MEETING TRANSCRIPT:
{transcript}"""


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str


class ChatManager:
    """Manages chat context, history, and prompt assembly."""

    def __init__(self, llm: LLMBackend, max_transcript_tokens: int = 100_000):
        self._llm = llm
        self._history: list[ChatMessage] = []
        self._transcript_segments: list[str] = []
        self._max_transcript_tokens = max_transcript_tokens

    @property
    def history(self) -> list[ChatMessage]:
        return self._history.copy()

    def add_transcript_segment(self, timestamp: str, text: str) -> None:
        """Add a new transcript segment to the context."""
        self._transcript_segments.append(f"[{timestamp}] {text}")

    def _build_transcript_context(self) -> str:
        """Build the transcript context string, truncating if needed."""
        full_transcript = "\n".join(self._transcript_segments)

        # Rough token estimate: ~4 chars per token
        estimated_tokens = len(full_transcript) // 4
        if estimated_tokens <= self._max_transcript_tokens:
            return full_transcript

        # Truncate from the beginning, keeping most recent content
        target_chars = self._max_transcript_tokens * 4
        truncated = full_transcript[-target_chars:]
        return f"[...earlier transcript truncated...]\n{truncated}"

    def _build_context(self) -> str:
        """Build the full system context including transcript."""
        transcript = self._build_transcript_context()
        return SYSTEM_PROMPT.format(transcript=transcript)

    def _build_chat_prompt(self, user_message: str) -> str:
        """Build prompt including chat history."""
        parts = []
        for msg in self._history:
            prefix = "User" if msg.role == "user" else "Assistant"
            parts.append(f"{prefix}: {msg.content}")
        parts.append(f"User: {user_message}")
        return "\n\n".join(parts)

    async def send_message(self, user_message: str) -> str:
        """Send a message and get a complete response."""
        context = self._build_context()
        prompt = self._build_chat_prompt(user_message)
        self._history.append(ChatMessage(role="user", content=user_message))
        response = await self._llm.complete(prompt, context=context)

        self._history.append(ChatMessage(role="assistant", content=response))
        return response

    async def stream_message(self, user_message: str) -> AsyncIterator[str]:
        """Send a message and stream the response token-by-token."""
        context = self._build_context()
        prompt = self._build_chat_prompt(user_message)
        self._history.append(ChatMessage(role="user", content=user_message))

        full_response = []
        async for token in self._llm.stream(prompt, context=context):
            full_response.append(token)
            yield token

        self._history.append(
            ChatMessage(role="assistant", content="".join(full_response))
        )

    def clear_history(self) -> None:
        """Clear chat history (transcript context is preserved)."""
        self._history.clear()
