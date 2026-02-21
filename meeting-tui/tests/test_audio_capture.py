"""Unit tests for audio capture (mock sounddevice) and VAD chunking logic."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from meeting_tui.audio.vad import SpeechSegment, VADProcessor
from meeting_tui.config import AudioConfig, VADConfig


# --- AudioCapture tests ---


class TestAudioCapture:
    """Tests for AudioCapture with mocked sounddevice."""

    @patch("meeting_tui.audio.capture.sd")
    def test_start_creates_stream(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig(device=0, sample_rate=16000, channels=1, block_duration_ms=30)
        loop = asyncio.new_event_loop()
        capture = AudioCapture(config, loop=loop)

        capture.start()

        mock_sd.InputStream.assert_called_once()
        call_kwargs = mock_sd.InputStream.call_args[1]
        assert call_kwargs["samplerate"] == 16000
        assert call_kwargs["channels"] == 1
        assert call_kwargs["dtype"] == "float32"
        assert call_kwargs["device"] == 0
        mock_sd.InputStream.return_value.start.assert_called_once()

        capture.stop()
        loop.close()

    @patch("meeting_tui.audio.capture.sd")
    def test_start_idempotent(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig()
        capture = AudioCapture(config)
        capture.start()
        capture.start()  # Second call should be no-op
        assert mock_sd.InputStream.call_count == 1
        capture.stop()

    @patch("meeting_tui.audio.capture.sd")
    def test_stop_closes_stream(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig()
        capture = AudioCapture(config)
        capture.start()
        stream = mock_sd.InputStream.return_value
        capture.stop()

        stream.stop.assert_called_once()
        stream.close.assert_called_once()

    @patch("meeting_tui.audio.capture.sd")
    def test_stop_when_not_started(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig()
        capture = AudioCapture(config)
        capture.stop()  # Should not raise

    @patch("meeting_tui.audio.capture.sd")
    def test_callback_enqueues_mono(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig()
        loop = asyncio.new_event_loop()
        capture = AudioCapture(config, loop=loop)

        # Simulate a mono audio callback — call_soon_threadsafe schedules on the loop
        indata = np.random.randn(480).astype(np.float32)
        capture._audio_callback(indata, 480, None, MagicMock(spec=bool, __bool__=lambda s: False))

        # Run the loop briefly to process the scheduled put_nowait
        loop.run_until_complete(asyncio.sleep(0.01))
        assert not capture.queue.empty()
        loop.close()

    @patch("meeting_tui.audio.capture.sd")
    def test_callback_enqueues_stereo(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig(channels=2)
        loop = asyncio.new_event_loop()
        capture = AudioCapture(config, loop=loop)

        # Simulate a stereo audio callback — should extract channel 0
        indata = np.random.randn(480, 2).astype(np.float32)
        capture._audio_callback(indata, 480, None, MagicMock(spec=bool, __bool__=lambda s: False))

        loop.run_until_complete(asyncio.sleep(0.01))
        assert not capture.queue.empty()
        loop.close()

    @patch("meeting_tui.audio.capture.sd")
    def test_list_devices(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        mock_sd.query_devices.return_value = [
            {"name": "Mic 1", "max_input_channels": 1, "max_output_channels": 0},
            {"name": "Speaker", "max_input_channels": 0, "max_output_channels": 2},
            {"name": "Mic 2", "max_input_channels": 2, "max_output_channels": 0},
        ]
        devices = AudioCapture.list_devices()
        assert len(devices) == 2
        assert devices[0]["name"] == "Mic 1"
        assert devices[1]["name"] == "Mic 2"

    @patch("meeting_tui.audio.capture.sd")
    def test_block_size_calculation(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig(sample_rate=16000, block_duration_ms=32)
        capture = AudioCapture(config)
        capture.start()

        call_kwargs = mock_sd.InputStream.call_args[1]
        assert call_kwargs["blocksize"] == 512  # 16000 * 32 / 1000
        capture.stop()

    def test_queue_is_bounded(self):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig()
        capture = AudioCapture(config)

        assert capture.queue.maxsize == 200

    @patch("meeting_tui.audio.capture.sd")
    def test_callback_drops_oldest_when_queue_full(self, mock_sd):
        from meeting_tui.audio.capture import AudioCapture

        config = AudioConfig()
        loop = asyncio.new_event_loop()
        capture = AudioCapture(config, loop=loop)
        capture._queue = asyncio.Queue(maxsize=1)

        old_chunk = np.array([1.0, 1.0], dtype=np.float32)
        new_chunk = np.array([2.0, 2.0], dtype=np.float32)
        capture.queue.put_nowait(old_chunk)

        capture._audio_callback(new_chunk, 2, None, MagicMock(spec=bool, __bool__=lambda s: False))
        loop.run_until_complete(asyncio.sleep(0.01))

        assert capture.queue.qsize() == 1
        queued = capture.queue.get_nowait()
        assert np.array_equal(queued, new_chunk)
        loop.close()


# --- VAD Processor tests ---


class TestVADProcessor:
    """Tests for VAD state machine logic (with mocked model)."""

    def _make_vad(self, threshold=0.5, min_speech=3, min_silence=3):
        config = VADConfig(
            threshold=threshold,
            min_speech_frames=min_speech,
            min_silence_frames=min_silence,
            frame_duration_ms=30,
        )
        vad = VADProcessor(config, sample_rate=16000)
        return vad

    def _chunk(self, n=480):
        return np.random.randn(n).astype(np.float32)

    @pytest.mark.asyncio
    async def test_no_speech_returns_none(self):
        vad = self._make_vad(min_speech=3, min_silence=3)
        # Mock confidence always below threshold
        with patch.object(vad, "_get_confidence", return_value=0.1):
            for _ in range(20):
                result = await vad.process_chunk(self._chunk())
                assert result is None

    @pytest.mark.asyncio
    async def test_speech_then_silence_produces_segment(self):
        vad = self._make_vad(min_speech=2, min_silence=2)
        confidences = (
            [0.8] * 5  # speech
            + [0.1] * 5  # silence → should emit after 2 silence frames
        )
        idx = 0

        def mock_confidence(chunk):
            nonlocal idx
            c = confidences[min(idx, len(confidences) - 1)]
            idx += 1
            return c

        results = []
        with patch.object(vad, "_get_confidence", side_effect=mock_confidence):
            for _ in range(len(confidences)):
                result = await vad.process_chunk(self._chunk())
                if result is not None:
                    results.append(result)

        assert len(results) == 1
        assert isinstance(results[0], SpeechSegment)
        assert results[0].audio.shape[0] > 0

    @pytest.mark.asyncio
    async def test_speech_not_enough_frames(self):
        """Speech frames below min_speech_frames should not trigger speech state."""
        vad = self._make_vad(min_speech=5, min_silence=2)
        # Only 3 speech frames, then silence — should not produce segment
        confidences = [0.8] * 3 + [0.1] * 10

        idx = 0

        def mock_confidence(chunk):
            nonlocal idx
            c = confidences[min(idx, len(confidences) - 1)]
            idx += 1
            return c

        results = []
        with patch.object(vad, "_get_confidence", side_effect=mock_confidence):
            for _ in range(len(confidences)):
                result = await vad.process_chunk(self._chunk())
                if result is not None:
                    results.append(result)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_flush_returns_remaining_speech(self):
        vad = self._make_vad(min_speech=2, min_silence=10)
        # Start speech but never enough silence to end
        with patch.object(vad, "_get_confidence", return_value=0.9):
            for _ in range(5):
                await vad.process_chunk(self._chunk())

        segment = vad.flush()
        assert segment is not None
        assert isinstance(segment, SpeechSegment)

    @pytest.mark.asyncio
    async def test_flush_returns_none_when_no_speech(self):
        vad = self._make_vad()
        with patch.object(vad, "_get_confidence", return_value=0.1):
            for _ in range(5):
                await vad.process_chunk(self._chunk())

        assert vad.flush() is None

    @pytest.mark.asyncio
    async def test_segment_timestamps(self):
        vad = self._make_vad(min_speech=2, min_silence=2)
        chunk_size = 480  # 30ms at 16kHz
        confidences = [0.8] * 4 + [0.1] * 4

        idx = 0

        def mock_confidence(chunk):
            nonlocal idx
            c = confidences[min(idx, len(confidences) - 1)]
            idx += 1
            return c

        results = []
        with patch.object(vad, "_get_confidence", side_effect=mock_confidence):
            for _ in range(len(confidences)):
                result = await vad.process_chunk(self._chunk(chunk_size))
                if result is not None:
                    results.append(result)

        assert len(results) == 1
        # start_time may be slightly negative due to lookback for pre-speech frames
        assert results[0].start_time >= -0.5
        assert results[0].end_time > results[0].start_time

    @pytest.mark.asyncio
    async def test_multiple_segments(self):
        vad = self._make_vad(min_speech=2, min_silence=2)
        # Two speech-silence cycles
        confidences = (
            [0.8] * 4 + [0.1] * 4 +  # segment 1
            [0.8] * 4 + [0.1] * 4     # segment 2
        )
        idx = 0

        def mock_confidence(chunk):
            nonlocal idx
            c = confidences[min(idx, len(confidences) - 1)]
            idx += 1
            return c

        results = []
        with patch.object(vad, "_get_confidence", side_effect=mock_confidence):
            for _ in range(len(confidences)):
                result = await vad.process_chunk(self._chunk())
                if result is not None:
                    results.append(result)

        assert len(results) == 2
