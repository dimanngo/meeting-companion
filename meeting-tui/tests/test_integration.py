"""Integration test: full pipeline from audio file → transcript → chat."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from meeting_tui.audio.vad import VADProcessor, SpeechSegment
from meeting_tui.chat.manager import ChatManager
from meeting_tui.config import AppConfig, VADConfig, TranscriptionConfig, PersistenceConfig
from meeting_tui.persistence.json_writer import JSONWriter
from meeting_tui.persistence.transcript_writer import TranscriptWriter
from meeting_tui.transcription.cleaner import TranscriptCleaner
from meeting_tui.transcription.engine import TranscriptionEngine, TranscriptionResult


class TestFullPipeline:
    """Integration test: simulate audio → VAD → transcription → cleanup → save → chat."""

    @pytest.mark.asyncio
    async def test_pipeline_end_to_end(self):
        """Simulate a full meeting pipeline with mocked audio/models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # --- Setup mock components ---

            # Mock VAD: simulate 3 speech segments
            segments = [
                SpeechSegment(
                    audio=np.random.randn(16000).astype(np.float32),
                    start_time=10.0,
                    end_time=12.0,
                ),
                SpeechSegment(
                    audio=np.random.randn(16000).astype(np.float32),
                    start_time=25.0,
                    end_time=28.0,
                ),
                SpeechSegment(
                    audio=np.random.randn(8000).astype(np.float32),
                    start_time=45.0,
                    end_time=46.5,
                ),
            ]

            # Mock transcription engine
            engine = TranscriptionEngine.__new__(TranscriptionEngine)
            engine.config = TranscriptionConfig()
            engine._model = None
            transcription_results = [
                TranscriptionResult(
                    text="Uh, we need to finalize the budget",
                    start_time=10.0, end_time=12.0,
                    language="en", confidence=-0.25,
                ),
                TranscriptionResult(
                    text="I think, um, marketing should get more",
                    start_time=25.0, end_time=28.0,
                    language="en", confidence=-0.30,
                ),
                TranscriptionResult(
                    text="Let's, you know, decide by Friday",
                    start_time=45.0, end_time=46.5,
                    language="en", confidence=-0.20,
                ),
            ]

            async def mock_transcribe(audio, start_time=0.0, end_time=0.0):
                for r in transcription_results:
                    if abs(r.start_time - start_time) < 0.1:
                        return r
                return TranscriptionResult(text="", start_time=start_time, end_time=end_time)

            engine.transcribe = mock_transcribe

            # Mock LLM
            mock_llm = AsyncMock()
            cleanup_results = [
                "We need to finalize the budget.",
                "I think marketing should get more.",
                "Let's decide by Friday.",
            ]
            mock_llm.complete.side_effect = cleanup_results

            cleaner = TranscriptCleaner(mock_llm)

            # Persistence
            writer = TranscriptWriter(tmpdir, title="test-meeting")
            json_writer = JSONWriter(tmpdir, title="test-meeting")

            # Chat manager with a separate mock
            chat_llm = AsyncMock()
            chat_llm.complete.return_value = (
                "Based on the discussion at 00:00:10, the team needs to finalize "
                "the budget. At 00:00:25, it was suggested that marketing should "
                "get more allocation. The deadline is Friday."
            )
            chat_manager = ChatManager(chat_llm)

            # --- Run pipeline ---

            for i, segment in enumerate(segments):
                result = await engine.transcribe(
                    segment.audio, segment.start_time, segment.end_time
                )

                minutes, seconds = divmod(int(segment.start_time), 60)
                hours, minutes = divmod(minutes, 60)
                timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                clean_text = await cleaner.clean(result.text)

                writer.append(timestamp, clean_text)
                json_writer.add_segment(
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    timestamp=timestamp,
                    raw_text=result.text,
                    clean_text=clean_text,
                    confidence=result.confidence,
                    language=result.language,
                )

                chat_manager.add_transcript_segment(timestamp, clean_text)

            writer.finalize()

            # --- Verify transcript output ---

            md_content = writer.filepath.read_text()
            assert "We need to finalize the budget." in md_content
            assert "marketing should get more" in md_content
            assert "decide by Friday" in md_content
            assert "Transcript ended" in md_content

            # --- Verify JSONL output ---

            lines = json_writer.filepath.read_text().strip().splitlines()
            assert len(lines) == 3
            seg0 = json.loads(lines[0])
            assert seg0["raw_text"] == "Uh, we need to finalize the budget"
            assert seg0["clean_text"] == "We need to finalize the budget."
            assert seg0["language"] == "en"

            # --- Verify chat ---

            response = await chat_manager.send_message("What was discussed about the budget?")
            assert "budget" in response.lower()
            assert len(chat_manager.history) == 2

    @pytest.mark.asyncio
    async def test_persistence_creates_files(self):
        """Verify that both .md and .json files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = TranscriptWriter(tmpdir, title="test")
            json_writer = JSONWriter(tmpdir, title="test")

            writer.append("00:00:01", "Hello world")
            json_writer.add_segment(
                start_time=1.0, end_time=2.0, timestamp="00:00:01",
                raw_text="hello world", clean_text="Hello world",
                confidence=-0.3, language="en",
            )

            assert writer.filepath.exists()
            assert json_writer.filepath.exists()

            md_content = writer.filepath.read_text()
            assert "Hello world" in md_content

            lines = json_writer.filepath.read_text().strip().splitlines()
            assert len(lines) == 1
            json_data = json.loads(lines[0])
            assert json_data["clean_text"] == "Hello world"
