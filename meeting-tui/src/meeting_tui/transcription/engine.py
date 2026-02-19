"""Speech-to-text transcription engine using faster-whisper."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from meeting_tui.config import TranscriptionConfig


@dataclass
class TranscriptionResult:
    """Result of transcribing an audio segment."""
    text: str
    start_time: float
    end_time: float
    language: str | None = None
    confidence: float = 0.0


class TranscriptionEngine:
    """Transcription engine using faster-whisper (CTranslate2)."""

    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self._model = None

    def _load_model(self) -> None:
        """Load the faster-whisper model (lazy initialization)."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.config.model_size,
            compute_type=self.config.compute_type,
        )

    async def transcribe(
        self, audio: np.ndarray, start_time: float = 0.0, end_time: float = 0.0
    ) -> TranscriptionResult:
        """Transcribe an audio segment. Runs in executor to avoid blocking."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self._transcribe_sync, audio, start_time, end_time
        )

    def _transcribe_sync(
        self, audio: np.ndarray, start_time: float, end_time: float
    ) -> TranscriptionResult:
        """Synchronous transcription."""
        if self._model is None:
            self._load_model()

        segments, info = self._model.transcribe(
            audio,
            beam_size=self.config.beam_size,
            language=self.config.language,
            vad_filter=False,  # We handle VAD ourselves
        )

        text_parts = []
        total_confidence = 0.0
        segment_count = 0
        for segment in segments:
            text_parts.append(segment.text.strip())
            total_confidence += segment.avg_log_prob
            segment_count += 1

        text = " ".join(text_parts)
        avg_confidence = (total_confidence / segment_count) if segment_count > 0 else 0.0

        return TranscriptionResult(
            text=text,
            start_time=start_time,
            end_time=end_time,
            language=info.language if info else None,
            confidence=avg_confidence,
        )
