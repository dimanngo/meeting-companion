"""Unit tests for transcription engine (mock model) and cleaner (mock LLM)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from meeting_tui.config import TranscriptionConfig
from meeting_tui.transcription.engine import TranscriptionEngine, TranscriptionResult


# --- TranscriptionEngine tests ---


@dataclass
class FakeSegment:
    text: str
    avg_log_prob: float = -0.3


@dataclass
class FakeInfo:
    language: str = "en"


class TestTranscriptionEngine:
    """Tests for TranscriptionEngine with mocked faster-whisper model."""

    def _make_engine(self, model_size="base"):
        config = TranscriptionConfig(model_size=model_size, compute_type="int8", beam_size=5)
        return TranscriptionEngine(config)

    @pytest.mark.asyncio
    async def test_transcribe_returns_result(self):
        engine = self._make_engine()

        fake_segments = [FakeSegment(text="Hello world"), FakeSegment(text="How are you")]
        fake_info = FakeInfo(language="en")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter(fake_segments), fake_info)
        engine._model = mock_model

        audio = np.random.randn(16000).astype(np.float32)
        result = await engine.transcribe(audio, start_time=1.0, end_time=2.0)

        assert isinstance(result, TranscriptionResult)
        assert "Hello world" in result.text
        assert "How are you" in result.text
        assert result.start_time == 1.0
        assert result.end_time == 2.0
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_empty_segments(self):
        engine = self._make_engine()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([]), FakeInfo())
        engine._model = mock_model

        audio = np.random.randn(16000).astype(np.float32)
        result = await engine.transcribe(audio)

        assert result.text == ""
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_transcribe_confidence_averaging(self):
        engine = self._make_engine()

        fake_segments = [
            FakeSegment(text="A", avg_log_prob=-0.2),
            FakeSegment(text="B", avg_log_prob=-0.4),
        ]
        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter(fake_segments), FakeInfo())
        engine._model = mock_model

        audio = np.random.randn(16000).astype(np.float32)
        result = await engine.transcribe(audio)

        assert abs(result.confidence - (-0.3)) < 1e-6

    @pytest.mark.asyncio
    async def test_transcribe_passes_config(self):
        engine = self._make_engine()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([]), FakeInfo())
        engine._model = mock_model

        audio = np.random.randn(16000).astype(np.float32)
        await engine.transcribe(audio)

        mock_model.transcribe.assert_called_once()
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["beam_size"] == 5
        assert call_kwargs["vad_filter"] is False

    def test_lazy_model_loading(self):
        engine = self._make_engine()
        assert engine._model is None


# --- TranscriptCleaner tests ---


class TestTranscriptCleaner:
    """Tests for TranscriptCleaner with mocked LLM backend."""

    @pytest.mark.asyncio
    async def test_clean_calls_llm(self):
        from meeting_tui.transcription.cleaner import TranscriptCleaner

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "We need to finalize the budget."
        cleaner = TranscriptCleaner(mock_llm)

        result = await cleaner.clean("Uh, we, we need to like finalize the budget.")

        assert result == "We need to finalize the budget."
        mock_llm.complete.assert_called_once()
        prompt = mock_llm.complete.call_args[0][0][0].content
        assert "finalize the budget" in prompt

    @pytest.mark.asyncio
    async def test_clean_empty_returns_empty(self):
        from meeting_tui.transcription.cleaner import TranscriptCleaner

        mock_llm = AsyncMock()
        cleaner = TranscriptCleaner(mock_llm)

        result = await cleaner.clean("")
        assert result == ""
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_whitespace_returns_whitespace(self):
        from meeting_tui.transcription.cleaner import TranscriptCleaner

        mock_llm = AsyncMock()
        cleaner = TranscriptCleaner(mock_llm)

        result = await cleaner.clean("   ")
        assert result == "   "
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_strips_result(self):
        from meeting_tui.transcription.cleaner import TranscriptCleaner

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "  Clean text with spaces.  \n"
        cleaner = TranscriptCleaner(mock_llm)

        result = await cleaner.clean("raw text")
        assert result == "Clean text with spaces."
