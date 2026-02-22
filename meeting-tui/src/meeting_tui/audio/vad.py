"""Voice Activity Detection using Silero VAD via ONNX Runtime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import onnxruntime
    from meeting_tui.config import VADConfig


@dataclass
class SpeechSegment:
    """A detected speech segment with its audio data."""
    audio: np.ndarray
    start_time: float  # seconds from recording start
    end_time: float


class VADProcessor:
    """Silero VAD wrapper that groups audio into speech segments."""

    # For 16 kHz the ONNX model expects 512-sample input frames
    # and a 64-sample context window prepended to each frame.
    _CONTEXT_SIZE = 64

    # Supported frame sizes per sample rate (from Silero VAD docs).
    _VALID_FRAME_SIZES: dict[int, set[int]] = {
        8000: {256, 512, 768},
        16000: {512, 1024, 1536},
    }

    def __init__(self, config: VADConfig, sample_rate: int = 16000):
        self.config = config
        self.sample_rate = sample_rate
        self._session: onnxruntime.InferenceSession | None = None
        self._onnx_state: np.ndarray | None = None
        self._context: np.ndarray | None = None

        # State machine for segment detection
        self._in_speech = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._current_segment: list[np.ndarray] = []
        self._segment_start_time: float = 0.0
        self._elapsed_samples: int = 0
        self._frame_size_validated = False

    def load_model(self) -> None:
        """Load the Silero VAD ONNX model from the silero_vad package."""
        if self._session is not None:
            return

        import onnxruntime
        from importlib.resources import files as pkg_files

        model_path = str(pkg_files("silero_vad.data").joinpath("silero_vad.onnx"))

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self._session = onnxruntime.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
            sess_options=opts,
        )
        self._onnx_state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._CONTEXT_SIZE), dtype=np.float32)

    def _load_model(self) -> None:
        """Backward-compatible alias for legacy callers."""
        self.load_model()

    def _get_confidence(self, chunk: np.ndarray) -> float:
        """Get speech confidence for a single audio frame via ONNX Runtime."""
        if self._session is None:
            self.load_model()

        audio = chunk.astype(np.float32).reshape(1, -1)
        # Prepend the rolling context window
        input_data = np.concatenate([self._context, audio], axis=1)

        ort_inputs = {
            "input": input_data,
            "state": self._onnx_state,
            "sr": np.array(self.sample_rate, dtype=np.int64),
        }
        out, self._onnx_state = self._session.run(None, ort_inputs)

        # Update context with the last _CONTEXT_SIZE samples
        self._context = input_data[:, -self._CONTEXT_SIZE:]

        return float(out.squeeze())

    async def process_chunk(self, chunk: np.ndarray) -> SpeechSegment | None:
        """Process an audio chunk through VAD, returning a segment when speech ends.

        Uses a state machine: speech starts after min_speech_frames consecutive
        frames above threshold, ends after min_silence_frames below threshold.
        """
        if not self._frame_size_validated:
            self._frame_size_validated = True
            valid = self._VALID_FRAME_SIZES.get(self.sample_rate, set())
            if valid and len(chunk) not in valid:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "Audio chunk size %d is NOT a supported Silero VAD frame size "
                    "for %d Hz (supported: %s). Speech detection will be unreliable! "
                    "Set audio.block_duration_ms so that sample_rate * block_duration_ms / 1000 "
                    "equals a supported size (e.g. 32 ms for 512 samples at 16 kHz).",
                    len(chunk), self.sample_rate, sorted(valid),
                )

        confidence = await asyncio.get_running_loop().run_in_executor(
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
        """Reset the segment detection state machine."""
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
