"""Abstract LLM backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class ChatMessage:
    """Structured chat message passed to LLM backends."""

    role: str
    content: str


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""

    @abstractmethod
    async def complete(self, messages: list[ChatMessage], context: str = "") -> str:
        """Generate a completion for the given structured chat history.

        Args:
            messages: Structured chat history including user/assistant turns.
            context: Optional system context (e.g., transcript).

        Returns:
            The generated text.
        """
        ...

    @abstractmethod
    async def stream(self, messages: list[ChatMessage], context: str = "") -> AsyncIterator[str]:
        """Stream a completion token-by-token.

        Args:
            messages: Structured chat history including user/assistant turns.
            context: Optional system context (e.g., transcript).

        Yields:
            Individual tokens/chunks of the response.
        """
        ...
        # Make this a generator
        if False:
            yield ""

    async def close(self) -> None:
        """Release any resources held by the backend.

        Subclasses may override to close HTTP clients, etc.
        """
