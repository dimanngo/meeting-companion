"""Textual App — main application class with layout and pipeline wiring."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Footer, Header

from meeting_tui.audio.capture import AudioCapture
from meeting_tui.audio.vad import SpeechSegment, VADProcessor
from meeting_tui.chat.manager import ChatManager
from meeting_tui.config import AppConfig
from meeting_tui.llm.base import LLMBackend
from meeting_tui.persistence.json_writer import JSONWriter
from meeting_tui.persistence.transcript_writer import TranscriptWriter
from meeting_tui.transcription.cleaner import TranscriptCleaner
from meeting_tui.transcription.engine import TranscriptionEngine
from meeting_tui.widgets.chat_pane import ChatPane, ChatSubmitted
from meeting_tui.widgets.status_bar import StatusBar
from meeting_tui.widgets.transcript_pane import TranscriptPane

log = logging.getLogger(__name__)

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY = 1.0  # seconds, doubles on each retry
SEGMENT_QUEUE_MAXSIZE = 128
CLEANUP_QUEUE_MAXSIZE = 256
PANEL_MIN_WIDTH_PCT = 25
PANEL_MAX_WIDTH_PCT = 75
PANEL_STEP_PCT = 5


@dataclass
class CleanupEntry:
    """Payload queued for delayed cleanup/persistence stage."""

    start_time: float
    end_time: float
    timestamp: str
    raw_text: str
    speaker_prefix: str
    confidence: float
    language: str | None


def create_llm_backend(config: AppConfig) -> LLMBackend:
    """Create the appropriate LLM backend based on configuration."""
    backend = config.llm.backend
    if backend == "ollama":
        from meeting_tui.llm.ollama_backend import OllamaBackend
        return OllamaBackend(
            base_url=config.llm.ollama_base_url,
            model=config.llm.ollama_model,
        )
    elif backend == "openai":
        from meeting_tui.llm.openai_backend import OpenAIBackend
        return OpenAIBackend(
            api_key=config.llm.openai_api_key,
            model=config.llm.openai_model,
        )
    elif backend == "gemini":
        from meeting_tui.llm.gemini_backend import GeminiBackend
        return GeminiBackend(
            api_key=config.llm.gemini_api_key,
            model=config.llm.gemini_model,
            thinking_level=config.llm.gemini_thinking_level,
        )
    else:
        raise ValueError(f"Unknown LLM backend: {backend}")


class MeetingApp(App):
    """Meeting companion TUI application."""

    TITLE = "Meeting TUI"
    CSS = """
    Screen {
        layout: vertical;
    }
    #main-content {
        height: 1fr;
    }
    TranscriptPane {
        width: 1fr;
    }
    ChatPane {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+r", "toggle_recording", "Record", show=True),
        Binding("ctrl+e", "export", "Export", show=True),
        Binding("ctrl+l", "switch_focus", "Switch Focus", show=True),
        Binding("ctrl+t", "copy_transcript", "Copy Transcript", show=True),
        Binding("ctrl+y", "copy_chat", "Copy Chat", show=True),
        Binding("ctrl+shift+left", "resize_left", "Widen Left", show=True, priority=True),
        Binding("ctrl+shift+right", "resize_right", "Widen Right", show=True, priority=True),
        Binding("alt+shift+left", "resize_left", show=False, priority=True),
        Binding("alt+shift+right", "resize_right", show=False, priority=True),
        Binding("ctrl+s", "label_speaker", "Speaker Label", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]
    
    # Disable command palette (reduces keybinding conflicts)
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        config: AppConfig,
        *,
        vad: VADProcessor | None = None,
        engine: TranscriptionEngine | None = None,
    ):
        super().__init__()
        self.config = config
        self._recording = False
        self._loading = False  # True while models are loading
        self._models_ready = vad is not None and engine is not None
        self._recording_start: datetime | None = None
        self._word_count = 0
        self._segment_count = 0
        self._current_speaker: str | None = None

        # Pipeline components (may be pre-loaded)
        self._audio_capture: AudioCapture | None = None
        self._vad: VADProcessor | None = vad
        self._engine: TranscriptionEngine | None = engine
        self._cleaner: TranscriptCleaner | None = None
        self._chat_manager: ChatManager | None = None
        self._llm: LLMBackend | None = None
        self._transcript_writer: TranscriptWriter | None = None
        self._json_writer: JSONWriter | None = None
        self._timer_handle: object | None = None
        self._silence_warned = False
        self._segment_queue: asyncio.Queue[SpeechSegment] | None = None
        self._segment_worker_task: asyncio.Task[None] | None = None
        self._cleanup_queue: asyncio.Queue[CleanupEntry] | None = None
        self._cleanup_worker_task: asyncio.Task[None] | None = None
        self._transcript_width_pct = 50

    def bell(self) -> None:
        """Override to disable the system bell completely."""
        pass  # Do nothing - no bell sounds

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-content"):
            yield TranscriptPane()
            yield ChatPane()
        yield StatusBar()
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        """Initialize pipeline components after the app is mounted."""
        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, self._signal_shutdown)
            except (NotImplementedError, OSError):
                pass  # Signal handlers not supported on this platform/event loop

        self._llm = create_llm_backend(self.config)
        if self._engine is None:
            self._engine = TranscriptionEngine(self.config.transcription)
        self._cleaner = TranscriptCleaner(self._llm)
        self._chat_manager = ChatManager(self._llm)
        if self._vad is None:
            self._vad = VADProcessor(self.config.vad, sample_rate=self.config.audio.sample_rate)
        self._transcript_writer = TranscriptWriter(
            self.config.persistence.output_dir,
            self.config.persistence.title,
        )
        self._json_writer = JSONWriter(
            self.config.persistence.output_dir,
            self.config.persistence.title,
        )

        # Update status bar model name and initial state
        status = self.query_one(StatusBar)
        backend = self.config.llm.backend
        if backend == "ollama":
            status.model_name = f"ollama/{self.config.llm.ollama_model}"
        elif backend == "openai":
            status.model_name = self.config.llm.openai_model
        elif backend == "gemini":
            status.model_name = self.config.llm.gemini_model
        
        # Show ready state
        status.activity = ""
        self._apply_panel_widths()
        self.notify("Ready to record. Press Ctrl+R to start.", severity="information", timeout=3)

    def _apply_panel_widths(self) -> None:
        """Apply current split widths to transcript and chat panes."""
        transcript = self.query_one(TranscriptPane)
        chat = self.query_one(ChatPane)
        transcript.styles.width = f"{self._transcript_width_pct}%"
        chat.styles.width = f"{100 - self._transcript_width_pct}%"

    def _signal_shutdown(self) -> None:
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        self.run_worker(self.action_quit(), name="signal-shutdown")

    async def action_toggle_recording(self) -> None:
        """Start or stop recording."""
        if self._loading:
            self.notify("Models are still loading, please wait...", severity="warning")
            return
        if self._recording:
            await self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        """Start the audio capture and transcription pipeline."""
        self._loading = True

        status = self.query_one(StatusBar)
        if self._models_ready:
            status.activity = "Starting microphone..."
            self.notify("Starting recording...", severity="information", timeout=2)
        else:
            status.activity = "Preparing models..."
            self.notify("Loading models, please wait...", severity="information", timeout=5)

        # Pre-load models in background, then start audio capture
        self.run_worker(self._load_and_start_pipeline(), name="startup", exclusive=True)

    _LOAD_RETRIES = 3
    _LOAD_RETRY_DELAY = 0.5  # seconds between retries

    async def _load_off_loop(self, func: Callable[[], None], label: str) -> None:
        """Run a blocking model-load synchronously.

        NOTE: Ideally this would use ``run_in_executor`` but CTranslate2
        triggers a Python 3.13+ ``fds_to_keep`` race when loaded from
        *any* thread inside an asyncio loop.  Models should be pre-loaded
        in ``__main__`` before the event loop starts.  This fallback is
        only reached when the app is constructed without pre-loaded models.
        """
        func()
        await asyncio.sleep(0)

    async def _load_and_start_pipeline(self) -> None:
        """Load ML models, then start audio capture and pipeline."""
        status = self.query_one(StatusBar)

        # Load VAD model (downloads from GitHub on first run)
        if not self._models_ready:
            status.activity = "Loading VAD model (first run may download)..."
            self.refresh()
            try:
                await self._load_off_loop(self._vad.load_model, "VAD")
            except Exception as e:
                log.error("Failed to load VAD model: %s", e)
                self.notify(f"VAD model error: {e}", severity="error", timeout=10)
                self._loading = False
                status.activity = ""
                return

            # Load Whisper model (downloads on first run)
            status.activity = f"Loading Whisper '{self.config.transcription.model_size}' model..."
            self.refresh()
            try:
                await self._load_off_loop(self._engine.load_model, "Whisper")
            except Exception as e:
                log.error("Failed to load Whisper model: %s", e)
                self.notify(f"Whisper model error: {e}", severity="error", timeout=10)
                self._loading = False
                status.activity = ""
                return

            self._models_ready = True
            self.notify("Models loaded successfully!", severity="information", timeout=2)

        # Models loaded — start audio capture
        status.activity = "Starting microphone..."
        self._audio_capture = AudioCapture(self.config.audio, loop=asyncio.get_event_loop())
        try:
            self._audio_capture.start()
        except Exception as e:
            self._loading = False
            status.activity = ""
            self.notify(f"Mic error: {e}. Check --list-devices.", severity="error", timeout=10)
            log.error("Failed to start audio capture: %s", e)
            return

        # Everything ready — switch to recording state
        self._loading = False
        self._recording = True
        self._recording_start = datetime.now()
        self._silence_warned = False
        self._start_segment_worker()
        status.activity = ""
        status.recording = True
        self.notify("Recording started!", severity="information", timeout=3)

        # Start the timer
        self._timer_handle = self.set_interval(1.0, self._update_timer)

        # Run the pipeline loop directly (we're already in a worker)
        await self._pipeline_loop()

    async def _stop_recording(self) -> None:
        """Stop recording and flush remaining segments."""
        self._recording = False

        if self._audio_capture:
            try:
                self._audio_capture.stop()
            except Exception as e:
                log.warning("Error stopping audio capture: %s", e)

        status = self.query_one(StatusBar)
        status.recording = False
        status.audio_level = 0.0
        status.no_speech_warning = False

        if self._timer_handle:
            self._timer_handle.stop()
            self._timer_handle = None

        # Flush remaining VAD segment and await its processing
        if self._vad:
            segment = self._vad.flush()
            if segment:
                await self._enqueue_segment(segment)

        await self._drain_pipeline_queues()
        await self._stop_segment_worker()

    def _start_segment_worker(self) -> None:
        """Start background workers for segment processing and cleanup."""
        if self._segment_worker_task and not self._segment_worker_task.done():
            return
        self._segment_queue = asyncio.Queue(maxsize=SEGMENT_QUEUE_MAXSIZE)
        self._cleanup_queue = asyncio.Queue(maxsize=CLEANUP_QUEUE_MAXSIZE)
        self._segment_worker_task = asyncio.create_task(self._segment_worker_loop())
        self._cleanup_worker_task = asyncio.create_task(self._cleanup_worker_loop())

    async def _stop_segment_worker(self) -> None:
        """Stop segment/cleanup workers gracefully."""
        segment_task = self._segment_worker_task
        cleanup_task = self._cleanup_worker_task
        self._segment_worker_task = None
        self._cleanup_worker_task = None

        if segment_task is not None:
            segment_task.cancel()
            try:
                await segment_task
            except asyncio.CancelledError:
                pass
        if cleanup_task is not None:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        self._segment_queue = None
        self._cleanup_queue = None

    async def _enqueue_segment(self, segment: SpeechSegment) -> None:
        """Enqueue a segment for background processing."""
        if not self._segment_queue:
            await self._process_segment(segment)
            return
        await self._segment_queue.put(segment)

    async def _drain_pipeline_queues(self) -> None:
        """Wait until all queued segment and cleanup work is fully processed."""
        if self._segment_queue:
            await self._segment_queue.join()
        if self._cleanup_queue:
            await self._cleanup_queue.join()

    async def _segment_worker_loop(self) -> None:
        """Process queued speech segments serially in the background."""
        assert self._segment_queue is not None
        while True:
            segment = await self._segment_queue.get()
            try:
                await self._process_segment(segment)
            except Exception as e:
                log.error("Unexpected segment processing error: %s", e)
            finally:
                self._segment_queue.task_done()

    async def _cleanup_worker_loop(self) -> None:
        """Process queued cleanup/persistence work serially in the background."""
        assert self._cleanup_queue is not None
        while True:
            entry = await self._cleanup_queue.get()
            try:
                await self._process_cleanup_entry(entry)
            except Exception as e:
                log.error("Unexpected cleanup processing error: %s", e)
            finally:
                self._cleanup_queue.task_done()

    def _update_timer(self) -> None:
        """Update the elapsed time in the status bar."""
        if self._recording and self._recording_start:
            elapsed = (datetime.now() - self._recording_start).total_seconds()
            status = self.query_one(StatusBar)
            status.elapsed_seconds = int(elapsed)

    async def _pipeline_loop(self) -> None:
        """Main audio processing pipeline: capture → VAD → transcribe → clean → display."""
        status = self.query_one(StatusBar)
        while self._recording and self._audio_capture:
            try:
                chunk = await asyncio.wait_for(self._audio_capture.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                # Mic disconnection — attempt recovery
                log.warning("Audio capture error: %s — attempting recovery", e)
                self.notify("Mic disconnected. Attempting recovery...", severity="warning")
                await self._attempt_mic_recovery()
                continue

            # Update audio level indicator
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            status.audio_level = min(rms * 10.0, 1.0)

            try:
                segment = await self._vad.process_chunk(chunk)
            except Exception as e:
                log.error("VAD error: %s", e)
                self.notify(f"VAD processing error: {e}", severity="error", timeout=5)
                continue

            if segment is not None:
                self._silence_warned = False
                status.no_speech_warning = False
                await self._enqueue_segment(segment)
            elif not self._silence_warned and self._recording_start:
                elapsed = (datetime.now() - self._recording_start).total_seconds()
                if elapsed > 15.0 and self._segment_count == 0:
                    self._silence_warned = True
                    status.no_speech_warning = True
                    if rms < 0.001:
                        self.notify(
                            "No audio signal detected for 15 s. "
                            "Check microphone permissions and input device (--list-devices).",
                            severity="warning", timeout=10,
                        )
                    else:
                        self.notify(
                            "Audio signal present but no speech detected for 15 s. "
                            "Try speaking louder or adjust VAD threshold.",
                            severity="warning", timeout=10,
                        )

    async def _attempt_mic_recovery(self) -> None:
        """Try to recover from a mic disconnection."""
        if self._audio_capture:
            self._audio_capture.stop()

        for attempt in range(3):
            await asyncio.sleep(2.0 * (attempt + 1))
            try:
                self._audio_capture = AudioCapture(
                    self.config.audio, loop=asyncio.get_event_loop()
                )
                self._audio_capture.start()
                self.notify("Mic reconnected!", severity="information")
                return
            except Exception:
                log.warning("Mic recovery attempt %d failed", attempt + 1)

        self.notify("Mic recovery failed. Press Ctrl+R to retry.", severity="error")
        await self._stop_recording()

    async def _process_segment(self, segment) -> None:
        """Process a speech segment: transcribe + raw display, then queue cleanup."""
        # Transcribe
        try:
            result = await self._engine.transcribe(
                segment.audio, segment.start_time, segment.end_time
            )
        except Exception as e:
            log.error("Transcription error: %s", e)
            self.notify(f"Transcription error: {e}", severity="error")
            return

        if not result.text.strip():
            return

        # Format timestamp
        minutes, seconds = divmod(int(segment.start_time), 60)
        hours, minutes = divmod(minutes, 60)
        timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Prepend speaker label if set
        speaker_prefix = f"[{self._current_speaker}] " if self._current_speaker else ""

        # Show raw text immediately
        transcript_pane = self.query_one(TranscriptPane)
        transcript_pane.add_raw_segment(timestamp, f"{speaker_prefix}{result.text}")

        cleanup_entry = CleanupEntry(
            start_time=segment.start_time,
            end_time=segment.end_time,
            timestamp=timestamp,
            raw_text=result.text,
            speaker_prefix=speaker_prefix,
            confidence=result.confidence,
            language=result.language,
        )

        if not self._cleanup_queue:
            await self._process_cleanup_entry(cleanup_entry)
            return

        await self._cleanup_queue.put(cleanup_entry)

    async def _process_cleanup_entry(self, entry: CleanupEntry) -> None:
        """Run delayed cleanup/persistence stage for a transcribed segment."""

        # Clean via LLM with retry and backoff
        status = self.query_one(StatusBar)
        status.activity = "Cleaning transcript..."
        clean_text = await self._clean_with_retry(entry.raw_text)
        status.activity = ""

        if entry.speaker_prefix:
            clean_text = f"{entry.speaker_prefix}{clean_text}"

        # Update display with clean text
        transcript_pane = self.query_one(TranscriptPane)
        transcript_pane.add_segment(entry.timestamp, clean_text)

        # Save to files
        self._transcript_writer.append(entry.timestamp, clean_text)
        self._json_writer.add_segment(
            start_time=entry.start_time,
            end_time=entry.end_time,
            timestamp=entry.timestamp,
            raw_text=entry.raw_text,
            clean_text=clean_text,
            confidence=entry.confidence,
            language=entry.language,
        )

        # Update chat context
        self._chat_manager.add_transcript_segment(entry.timestamp, clean_text)

        # Update stats
        self._word_count += len(clean_text.split())
        self._segment_count += 1
        status = self.query_one(StatusBar)
        status.word_count = self._word_count
        status.segment_count = self._segment_count

    async def _clean_with_retry(self, raw_text: str) -> str:
        """Clean text via LLM with exponential backoff retry."""
        delay = LLM_RETRY_DELAY
        for attempt in range(LLM_MAX_RETRIES):
            try:
                return await self._cleaner.clean(raw_text)
            except Exception as e:
                log.warning("LLM cleanup attempt %d failed: %s", attempt + 1, e)
                if attempt < LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
        # All retries failed — return raw text
        log.error("LLM cleanup failed after %d retries, using raw text", LLM_MAX_RETRIES)
        return raw_text

    async def on_chat_submitted(self, event: ChatSubmitted) -> None:
        """Handle a chat message from the user."""
        chat_pane = self.query_one(ChatPane)

        if self._loading:
            chat_pane.add_assistant_message("⏳ Models are still loading, please wait...")
            return

        delay = LLM_RETRY_DELAY
        status = self.query_one(StatusBar)
        for attempt in range(LLM_MAX_RETRIES):
            try:
                status.activity = "AI is thinking..."
                chat_pane.begin_assistant_stream()
                async for token in self._chat_manager.stream_message(event.text):
                    chat_pane.append_stream_token(token)
                chat_pane.end_assistant_stream()
                status.activity = ""
                return
            except Exception as e:
                log.warning("Chat LLM attempt %d failed: %s", attempt + 1, e)
                if attempt < LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    status.activity = ""
                    chat_pane.add_assistant_message(f"Error after {LLM_MAX_RETRIES} retries: {e}")

    def action_label_speaker(self) -> None:
        """Prompt for a speaker label to tag subsequent transcript segments."""
        if self._loading:
            self.notify("Models are still loading, please wait...", severity="warning")
            return
        self.push_screen(SpeakerLabelScreen(), callback=self._set_speaker_label)

    def _set_speaker_label(self, label: str | None) -> None:
        """Set or clear the current speaker label."""
        if label:
            self._current_speaker = label
            self.notify(f"Speaker label set: {label}")
        else:
            self._current_speaker = None
            self.notify("Speaker label cleared")

    def action_export(self) -> None:
        """Force-save the current transcript."""
        if self._loading:
            self.notify("Models are still loading, please wait...", severity="warning")
            return
        if self._json_writer:
            self._json_writer.flush()
        if self._transcript_writer:
            self.notify(
                f"Exported to {self._transcript_writer.filepath} "
                f"and {self._json_writer.filepath}"
            )

    def action_switch_focus(self) -> None:
        """Switch focus between transcript and chat panes."""
        chat_input = self.query_one("#chat-input")
        if chat_input.has_focus:
            self.query_one(TranscriptPane).focus()
        else:
            chat_input.focus()

    def action_copy_transcript(self) -> None:
        """Copy transcript panel text to clipboard."""
        transcript = self.query_one(TranscriptPane)
        text = transcript.get_plain_text()
        if not text:
            self.notify("Transcript is empty.", severity="warning", timeout=2)
            return
        self.copy_to_clipboard(text)
        self.notify("Transcript copied to clipboard.", severity="information", timeout=2)

    def action_copy_chat(self) -> None:
        """Copy chat panel text to clipboard."""
        chat = self.query_one(ChatPane)
        text = chat.get_plain_text()
        if not text:
            self.notify("Chat is empty.", severity="warning", timeout=2)
            return
        self.copy_to_clipboard(text)
        self.notify("Chat copied to clipboard.", severity="information", timeout=2)

    def action_resize_left(self) -> None:
        """Widen the transcript panel and shrink chat panel."""
        self._transcript_width_pct = min(
            PANEL_MAX_WIDTH_PCT,
            self._transcript_width_pct + PANEL_STEP_PCT,
        )
        self._apply_panel_widths()

    def action_resize_right(self) -> None:
        """Widen the chat panel and shrink transcript panel."""
        self._transcript_width_pct = max(
            PANEL_MIN_WIDTH_PCT,
            self._transcript_width_pct - PANEL_STEP_PCT,
        )
        self._apply_panel_widths()

    async def action_quit(self) -> None:
        """Graceful shutdown — save everything before exiting."""
        if self._recording:
            await self._stop_recording()
        if self._transcript_writer:
            self._transcript_writer.finalize()
        # Save chat history alongside transcript
        if self._chat_manager and self._chat_manager.history:
            self._save_chat_history()
        if self._llm:
            try:
                await self._llm.close()
            except Exception:
                pass
        self.exit()

    def _save_chat_history(self) -> None:
        """Save chat history to a Markdown file next to the transcript."""
        if not self._transcript_writer:
            return
        chat_path = self._transcript_writer.filepath.with_name(
            self._transcript_writer.filepath.stem + "_chat.md"
        )
        lines = [f"# Chat History — {self.config.persistence.title}\n\n"]
        for msg in self._chat_manager.history:
            prefix = "**You:**" if msg.role == "user" else "**AI:**"
            lines.append(f"{prefix} {msg.content}\n\n")
        lines.append(f"\n---\n\n*Chat ended at {datetime.now().strftime('%H:%M')}*\n")
        chat_path.write_text("".join(lines))


class SpeakerLabelScreen(ModalScreen[str | None]):
    """Modal screen for entering a speaker label."""

    DEFAULT_CSS = """
    SpeakerLabelScreen {
        align: center middle;
    }
    #speaker-dialog {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #speaker-dialog Static {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical
        from textual.widgets import Input, Static

        with Vertical(id="speaker-dialog"):
            yield Static("Enter speaker name (empty to clear):")
            yield Input(placeholder="e.g., Alice, Bob...", id="speaker-input")

    def on_input_submitted(self, event) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)
