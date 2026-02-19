"""Abstract LLM backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""

    @abstractmethod
    async def complete(self, prompt: str, context: str = "") -> str:
        """Generate a completion for the given prompt.

        Args:
            prompt: The user prompt / instruction.
            context: Optional system context (e.g., transcript).

        Returns:
            The generated text.
        """
        ...

    @abstractmethod
    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        """Stream a completion token-by-token.

        Args:
            prompt: The user prompt / instruction.
            context: Optional system context (e.g., transcript).

        Yields:
            Individual tokens/chunks of the response.
        """
        ...
        # Make this a generator
        if False:
            yield ""
