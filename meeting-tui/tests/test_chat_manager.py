"""Unit tests for chat manager — context assembly and truncation logic."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from meeting_tui.chat.manager import ChatManager, ChatMessage


class TestChatManager:
    """Tests for ChatManager context building, truncation, and history."""

    def _make_manager(self, max_tokens=100_000):
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "AI response"

        async def mock_stream(prompt, context=""):
            for word in ["AI", " ", "response"]:
                yield word

        mock_llm.stream = mock_stream
        return ChatManager(mock_llm, max_transcript_tokens=max_tokens), mock_llm

    def test_add_transcript_segment(self):
        mgr, _ = self._make_manager()
        mgr.add_transcript_segment("00:01:00", "Hello world")
        mgr.add_transcript_segment("00:02:00", "How are you")
        assert len(mgr._transcript_segments) == 2

    def test_build_transcript_context_no_truncation(self):
        mgr, _ = self._make_manager(max_tokens=100_000)
        mgr.add_transcript_segment("00:01:00", "Hello world")
        mgr.add_transcript_segment("00:02:00", "How are you")

        ctx = mgr._build_transcript_context()
        assert "[00:01:00] Hello world" in ctx
        assert "[00:02:00] How are you" in ctx

    def test_build_transcript_context_with_truncation(self):
        mgr, _ = self._make_manager(max_tokens=10)  # Very small budget (~40 chars)
        for i in range(100):
            mgr.add_transcript_segment(f"00:{i:02d}:00", f"Segment number {i} with some text")

        ctx = mgr._build_transcript_context()
        assert "[...earlier transcript truncated...]" in ctx
        # Earlier segments should be missing
        assert "[00:00:00]" not in ctx

    def test_build_context_includes_system_prompt(self):
        mgr, _ = self._make_manager()
        mgr.add_transcript_segment("00:01:00", "Test transcript")

        ctx = mgr._build_context()
        assert "meeting assistant" in ctx.lower()
        assert "Test transcript" in ctx

    def test_build_chat_prompt_with_history(self):
        mgr, _ = self._make_manager()
        mgr._history.append(ChatMessage(role="user", content="What happened?"))
        mgr._history.append(ChatMessage(role="assistant", content="Nothing yet."))

        prompt = mgr._build_chat_prompt("Tell me more")
        assert "User: What happened?" in prompt
        assert "Assistant: Nothing yet." in prompt
        assert "User: Tell me more" in prompt

    def test_build_chat_prompt_empty_history(self):
        mgr, _ = self._make_manager()
        prompt = mgr._build_chat_prompt("Hello")
        assert prompt == "User: Hello"

    @pytest.mark.asyncio
    async def test_send_message(self):
        mgr, mock_llm = self._make_manager()
        mgr.add_transcript_segment("00:01:00", "Budget discussion")

        response = await mgr.send_message("What about budget?")
        assert response == "AI response"
        assert len(mgr.history) == 2
        assert mgr.history[0].role == "user"
        assert mgr.history[0].content == "What about budget?"
        assert mgr.history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_stream_message(self):
        mgr, _ = self._make_manager()
        mgr.add_transcript_segment("00:01:00", "Test")

        tokens = []
        async for token in mgr.stream_message("Hello"):
            tokens.append(token)

        assert "".join(tokens) == "AI response"
        assert len(mgr.history) == 2
        assert mgr.history[1].content == "AI response"

    def test_clear_history(self):
        mgr, _ = self._make_manager()
        mgr._history.append(ChatMessage(role="user", content="test"))
        mgr.add_transcript_segment("00:01:00", "transcript")

        mgr.clear_history()
        assert len(mgr.history) == 0
        # Transcript should be preserved
        assert len(mgr._transcript_segments) == 1

    @pytest.mark.asyncio
    async def test_send_message_passes_context(self):
        mgr, mock_llm = self._make_manager()
        mgr.add_transcript_segment("00:01:00", "Important meeting content")

        await mgr.send_message("Question?")

        mock_llm.complete.assert_called_once()
        call_kwargs = mock_llm.complete.call_args
        context = call_kwargs[1].get("context", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else "")
        assert "Important meeting content" in context

    def test_history_returns_copy(self):
        mgr, _ = self._make_manager()
        mgr._history.append(ChatMessage(role="user", content="test"))
        history = mgr.history
        history.clear()
        assert len(mgr._history) == 1  # Original not affected
