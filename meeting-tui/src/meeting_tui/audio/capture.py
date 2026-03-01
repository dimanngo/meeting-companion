"""Microphone audio capture using sounddevice in a background thread."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from meeting_tui.config import AudioConfig


logger = logging.getLogger(__name__)


class AudioCapture:
    """Captures microphone audio and feeds chunks to an asyncio queue."""

    _MAX_QUEUE_CHUNKS = 200

    def __init__(
        self, config: AudioConfig, loop: asyncio.AbstractEventLoop | None = None
    ):
        self.config = config
        self._loop = loop
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(
            maxsize=self._MAX_QUEUE_CHUNKS
        )
        self._stream: sd.InputStream | None = None
        self._running = False
        self._dropped_chunks = 0
        self._last_drop_log_monotonic = 0.0

    @property
    def queue(self) -> asyncio.Queue[np.ndarray]:
        return self._queue

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Called from the PortAudio thread for each audio block."""
        if status:
            logger.warning("Audio callback status: %s", status)
        chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy().flatten()
        loop = self._loop or asyncio.get_event_loop()
        try:
            loop.call_soon_threadsafe(self._enqueue_chunk, chunk)
        except RuntimeError:
            logger.debug("Event loop unavailable while enqueueing audio chunk")

    def _enqueue_chunk(self, chunk: np.ndarray) -> None:
        """Enqueue an audio chunk, dropping the oldest one if queue is full."""
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._dropped_chunks += 1
            now = time.monotonic()
            if now - self._last_drop_log_monotonic >= 1.0:
                logger.warning(
                    "Audio queue full; dropped %d chunk(s) in the last %.1f s",
                    self._dropped_chunks,
                    now - self._last_drop_log_monotonic
                    if self._last_drop_log_monotonic
                    else 1.0,
                )
                self._dropped_chunks = 0
                self._last_drop_log_monotonic = now

        try:
            self._queue.put_nowait(chunk)
        except asyncio.QueueFull:
            logger.warning("Audio queue still full; dropping incoming chunk")

    def start(self) -> None:
        """Start capturing audio from the microphone."""
        if self._running:
            return
        self._running = True
        block_size = int(self.config.sample_rate * self.config.block_duration_ms / 1000)
        self._stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype="float32",
            blocksize=block_size,
            device=self.config.device,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop capturing audio."""
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices."""
        devices = sd.query_devices()
        result = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                result.append(
                    {
                        "index": i,
                        "name": dev["name"],
                        "channels": dev["max_input_channels"],
                    }
                )
        return result
