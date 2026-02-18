"""Unit tests for LLM backends (mock HTTP responses)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- Ollama Backend tests ---


class TestOllamaBackend:
    """Tests for OllamaBackend with mocked httpx."""

    @pytest.mark.asyncio
    async def test_complete(self):
        from meeting_tui.llm.ollama_backend import OllamaBackend

        backend = OllamaBackend(base_url="http://localhost:11434", model="mistral")

        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Hello from Ollama"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await backend.complete("Say hello", context="Be friendly")

        assert result == "Hello from Ollama"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        body = call_kwargs[1]["json"]
        assert body["model"] == "mistral"
        assert body["stream"] is False
        assert len(body["messages"]) == 2  # system + user

    @pytest.mark.asyncio
    async def test_complete_no_context(self):
        from meeting_tui.llm.ollama_backend import OllamaBackend

        backend = OllamaBackend()
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Hi"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(backend._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await backend.complete("Hello")

        assert result == "Hi"

    def test_build_messages_with_context(self):
        from meeting_tui.llm.ollama_backend import OllamaBackend

        messages = OllamaBackend._build_messages("Hello", "System context")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_build_messages_without_context(self):
        from meeting_tui.llm.ollama_backend import OllamaBackend

        messages = OllamaBackend._build_messages("Hello", "")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"


# --- OpenAI Backend tests ---


class TestOpenAIBackend:
    """Tests for OpenAIBackend with mocked openai SDK."""

    @pytest.mark.asyncio
    async def test_complete(self):
        from meeting_tui.llm.openai_backend import OpenAIBackend

        with patch("meeting_tui.llm.openai_backend.AsyncOpenAI") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            mock_choice = MagicMock()
            mock_choice.message.content = "Hello from OpenAI"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            backend = OpenAIBackend(api_key="test-key", model="gpt-4o-mini")
            result = await backend.complete("Say hello")

        assert result == "Hello from OpenAI"

    @pytest.mark.asyncio
    async def test_complete_empty_response(self):
        from meeting_tui.llm.openai_backend import OpenAIBackend

        with patch("meeting_tui.llm.openai_backend.AsyncOpenAI") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            mock_choice = MagicMock()
            mock_choice.message.content = None
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            backend = OpenAIBackend(api_key="test-key")
            result = await backend.complete("Hello")

        assert result == ""

    def test_build_messages_with_context(self):
        from meeting_tui.llm.openai_backend import OpenAIBackend

        messages = OpenAIBackend._build_messages("Hello", "Context")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"

    def test_build_messages_without_context(self):
        from meeting_tui.llm.openai_backend import OpenAIBackend

        messages = OpenAIBackend._build_messages("Hello", "")
        assert len(messages) == 1


# --- Gemini Backend tests ---


class TestGeminiBackend:
    """Tests for GeminiBackend with mocked google-genai SDK."""

    def test_thinking_budget_levels(self):
        from meeting_tui.llm.gemini_backend import GeminiBackend

        with patch("meeting_tui.llm.gemini_backend.genai", create=True):
            with patch("google.genai.Client"):
                backend = GeminiBackend.__new__(GeminiBackend)
                backend.thinking_level = "minimal"
                assert backend._thinking_budget() == 128

                backend.thinking_level = "low"
                assert backend._thinking_budget() == 1024

                backend.thinking_level = "medium"
                assert backend._thinking_budget() == 4096

                backend.thinking_level = "high"
                assert backend._thinking_budget() == 16384

                backend.thinking_level = "unknown"
                assert backend._thinking_budget() == 1024  # default

    @pytest.mark.asyncio
    async def test_complete(self):
        from meeting_tui.llm.gemini_backend import GeminiBackend

        with patch("google.genai.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_response = MagicMock()
            mock_response.text = "Hello from Gemini"
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            backend = GeminiBackend(api_key="test-key", model="gemini-2.5-flash-preview")
            result = await backend.complete("Hello")

        assert result == "Hello from Gemini"

    @pytest.mark.asyncio
    async def test_complete_empty_response(self):
        from meeting_tui.llm.gemini_backend import GeminiBackend

        with patch("google.genai.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_response = MagicMock()
            mock_response.text = None
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            backend = GeminiBackend(api_key="test-key")
            result = await backend.complete("Hello")

        assert result == ""
