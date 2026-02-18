"""Voice Activity Detection using Silero VAD via ONNX Runtime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from meeting_tui.config import VADConfig


@dataclass
class SpeechSegment:
    """A detected speech segment with its audio data."""
    audio: np.ndarray
    start_time: float  # seconds from recording start
    end_time: float


class VADProcessor:
    """Silero VAD wrapper that groups audio into speech segments."""

    def __init__(self, config: VADConfig, sample_rate: int = 16000):
        self.config = config
        self.sample_rate = sample_rate
        self._model = None
        self._state = None
        self._sr_tensor = None

        # State machine for segment detection
        self._in_speech = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._current_segment: list[np.ndarray] = []
        self._segment_start_time: float = 0.0
        self._elapsed_samples: int = 0

    def _load_model(self) -> None:
        """Load the Silero VAD ONNX model."""
        import torch
        self._model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            onnx=True,
        )
        (
            self._get_speech_timestamps,
            _,
            self._read_audio,
            *_,
        ) = utils

    def _get_confidence(self, chunk: np.ndarray) -> float:
        """Get speech confidence for a single audio frame."""
        import torch

        if self._model is None:
            self._load_model()

        tensor = torch.from_numpy(chunk).float()
        confidence = self._model(tensor, self.sample_rate)
        if isinstance(confidence, torch.Tensor):
            return confidence.item()
        return float(confidence)

    async def process_chunk(self, chunk: np.ndarray) -> SpeechSegment | None:
        """Process an audio chunk through VAD, returning a segment when speech ends.

        Uses a state machine: speech starts after min_speech_frames consecutive
        frames above threshold, ends after min_silence_frames below threshold.
        """
        confidence = await asyncio.get_event_loop().run_in_executor(
            None, self._get_confidence, chunk
        )

        current_time = self._elapsed_samples / self.sample_rate
        self._elapsed_samples += len(chunk)

        if not self._in_speech:
            if confidence >= self.config.threshold:
                self._speech_frames += 1
                self._current_segment.append(chunk)
                if self._speech_frames >= self.config.min_speech_frames:
                    self._in_speech = True
                    self._segment_start_time = current_time - (
                        self._speech_frames * self.config.frame_duration_ms / 1000
                    )
            else:
                self._speech_frames = 0
                self._current_segment.clear()
        else:
            self._current_segment.append(chunk)
            if confidence < self.config.threshold:
                self._silence_frames += 1
                if self._silence_frames >= self.config.min_silence_frames:
                    # Speech ended — emit segment
                    segment = SpeechSegment(
                        audio=np.concatenate(self._current_segment),
                        start_time=self._segment_start_time,
                        end_time=current_time,
                    )
                    self._reset_state()
                    return segment
            else:
                self._silence_frames = 0

        return None

    def _reset_state(self) -> None:
        """Reset the state machine."""
        self._in_speech = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._current_segment.clear()

    def flush(self) -> SpeechSegment | None:
        """Flush any remaining speech segment (call on stop)."""
        if self._in_speech and self._current_segment:
            current_time = self._elapsed_samples / self.sample_rate
            segment = SpeechSegment(
                audio=np.concatenate(self._current_segment),
                start_time=self._segment_start_time,
                end_time=current_time,
            )
            self._reset_state()
            return segment
        self._reset_state()
        return None
