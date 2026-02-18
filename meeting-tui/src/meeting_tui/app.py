"""Textual App — main application class with layout and pipeline wiring."""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Footer, Header

from meeting_tui.audio.capture import AudioCapture
from meeting_tui.audio.vad import VADProcessor
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
        Binding("ctrl+s", "label_speaker", "Speaker Label", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._recording = False
        self._recording_start: datetime | None = None
        self._word_count = 0
        self._segment_count = 0
        self._current_speaker: str | None = None

        # Pipeline components (initialized on mount)
        self._audio_capture: AudioCapture | None = None
        self._vad: VADProcessor | None = None
        self._engine: TranscriptionEngine | None = None
        self._cleaner: TranscriptCleaner | None = None
        self._chat_manager: ChatManager | None = None
        self._llm: LLMBackend | None = None
        self._transcript_writer: TranscriptWriter | None = None
        self._json_writer: JSONWriter | None = None
        self._timer_handle: object | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-content"):
            yield TranscriptPane()
            yield ChatPane()
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize pipeline components after the app is mounted."""
        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(sig, self._signal_shutdown)

        self._llm = create_llm_backend(self.config)
        self._engine = TranscriptionEngine(self.config.transcription)
        self._cleaner = TranscriptCleaner(self._llm)
        self._chat_manager = ChatManager(self._llm)
        self._vad = VADProcessor(self.config.vad, sample_rate=self.config.audio.sample_rate)
        self._transcript_writer = TranscriptWriter(
            self.config.persistence.output_dir,
            self.config.persistence.title,
        )
        self._json_writer = JSONWriter(
            self.config.persistence.output_dir,
            self.config.persistence.title,
        )

        # Update status bar model name
        status = self.query_one(StatusBar)
        backend = self.config.llm.backend
        if backend == "ollama":
            status.model_name = f"ollama/{self.config.llm.ollama_model}"
        elif backend == "openai":
            status.model_name = self.config.llm.openai_model
        elif backend == "gemini":
            status.model_name = self.config.llm.gemini_model

    def _signal_shutdown(self) -> None:
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        self.run_worker(self.action_quit(), name="signal-shutdown")

    def action_toggle_recording(self) -> None:
        """Start or stop recording."""
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        """Start the audio capture and transcription pipeline."""
        self._recording = True
        self._recording_start = datetime.now()

        self._audio_capture = AudioCapture(self.config.audio, loop=asyncio.get_event_loop())
        try:
            self._audio_capture.start()
        except Exception as e:
            self._recording = False
            self.notify(f"Mic error: {e}. Check --list-devices.", severity="error")
            log.error("Failed to start audio capture: %s", e)
            return

        status = self.query_one(StatusBar)
        status.recording = True

        # Show model loading notification (first run triggers downloads)
        self.notify(
            f"Loading Whisper '{self.config.transcription.model_size}' model (first run may download)...",
            timeout=5,
        )

        # Start the timer
        self._timer_handle = self.set_interval(1.0, self._update_timer)

        # Start the pipeline worker
        self.run_worker(self._pipeline_loop(), name="pipeline", exclusive=True)

    def _stop_recording(self) -> None:
        """Stop recording and flush remaining segments."""
        self._recording = False

        if self._audio_capture:
            try:
                self._audio_capture.stop()
            except Exception as e:
                log.warning("Error stopping audio capture: %s", e)

        status = self.query_one(StatusBar)
        status.recording = False

        if self._timer_handle:
            self._timer_handle.stop()
            self._timer_handle = None

        # Flush remaining VAD segment
        if self._vad:
            segment = self._vad.flush()
            if segment:
                self.run_worker(self._process_segment(segment), name="flush")

    def _update_timer(self) -> None:
        """Update the elapsed time in the status bar."""
        if self._recording and self._recording_start:
            elapsed = (datetime.now() - self._recording_start).total_seconds()
            status = self.query_one(StatusBar)
            status.elapsed_seconds = int(elapsed)

    async def _pipeline_loop(self) -> None:
        """Main audio processing pipeline: capture → VAD → transcribe → clean → display."""
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

            try:
                segment = await self._vad.process_chunk(chunk)
            except Exception as e:
                log.error("VAD error: %s", e)
                continue

            if segment is not None:
                await self._process_segment(segment)

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
        self._stop_recording()

    async def _process_segment(self, segment) -> None:
        """Process a speech segment: transcribe, clean, display, save."""
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

        # Clean via LLM with retry and backoff
        clean_text = await self._clean_with_retry(result.text)

        if speaker_prefix:
            clean_text = f"{speaker_prefix}{clean_text}"

        # Update display with clean text
        transcript_pane.add_segment(timestamp, clean_text)

        # Save to files
        self._transcript_writer.append(timestamp, clean_text)
        self._json_writer.add_segment(
            start_time=segment.start_time,
            end_time=segment.end_time,
            timestamp=timestamp,
            raw_text=result.text,
            clean_text=clean_text,
            confidence=result.confidence,
            language=result.language,
        )

        # Update chat context
        self._chat_manager.add_transcript_segment(timestamp, clean_text)

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

        delay = LLM_RETRY_DELAY
        for attempt in range(LLM_MAX_RETRIES):
            try:
                chat_pane.begin_assistant_stream()
                async for token in self._chat_manager.stream_message(event.text):
                    chat_pane.append_stream_token(token)
                chat_pane.end_assistant_stream()
                return
            except Exception as e:
                log.warning("Chat LLM attempt %d failed: %s", attempt + 1, e)
                if attempt < LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    chat_pane.add_assistant_message(f"Error after {LLM_MAX_RETRIES} retries: {e}")

    def action_label_speaker(self) -> None:
        """Prompt for a speaker label to tag subsequent transcript segments."""
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
        if self._transcript_writer:
            self.notify(f"Transcript saved to {self._transcript_writer.filepath}")

    def action_switch_focus(self) -> None:
        """Switch focus between transcript and chat panes."""
        chat_input = self.query_one("#chat-input")
        if chat_input.has_focus:
            self.query_one(TranscriptPane).focus()
        else:
            chat_input.focus()

    async def action_quit(self) -> None:
        """Graceful shutdown — save everything before exiting."""
        if self._recording:
            self._stop_recording()
        if self._transcript_writer:
            self._transcript_writer.finalize()
        # Save chat history alongside transcript
        if self._chat_manager and self._chat_manager.history:
            self._save_chat_history()
        if self._llm and hasattr(self._llm, "close"):
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
