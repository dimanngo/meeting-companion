"""Textual App — main application class with layout and pipeline wiring."""

from __future__ import annotations

import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
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
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._recording = False
        self._recording_start: datetime | None = None
        self._word_count = 0
        self._segment_count = 0

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
        self._audio_capture.start()

        status = self.query_one(StatusBar)
        status.recording = True

        # Start the timer
        self._timer_handle = self.set_interval(1.0, self._update_timer)

        # Start the pipeline worker
        self.run_worker(self._pipeline_loop(), name="pipeline", exclusive=True)

    def _stop_recording(self) -> None:
        """Stop recording and flush remaining segments."""
        self._recording = False

        if self._audio_capture:
            self._audio_capture.stop()

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

            segment = await self._vad.process_chunk(chunk)
            if segment is not None:
                await self._process_segment(segment)

    async def _process_segment(self, segment) -> None:
        """Process a speech segment: transcribe, clean, display, save."""
        # Transcribe
        result = await self._engine.transcribe(
            segment.audio, segment.start_time, segment.end_time
        )

        if not result.text.strip():
            return

        # Format timestamp
        minutes, seconds = divmod(int(segment.start_time), 60)
        hours, minutes = divmod(minutes, 60)
        timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Show raw text immediately
        transcript_pane = self.query_one(TranscriptPane)
        transcript_pane.add_raw_segment(timestamp, result.text)

        # Clean via LLM
        try:
            clean_text = await self._cleaner.clean(result.text)
        except Exception:
            clean_text = result.text  # Fallback to raw on LLM error

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

    async def on_chat_submitted(self, event: ChatSubmitted) -> None:
        """Handle a chat message from the user."""
        chat_pane = self.query_one(ChatPane)

        try:
            chat_pane.begin_assistant_stream()
            async for token in self._chat_manager.stream_message(event.text):
                chat_pane.append_stream_token(token)
            chat_pane.end_assistant_stream()
        except Exception as e:
            chat_pane.add_assistant_message(f"Error: {e}")

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
        """Graceful shutdown."""
        if self._recording:
            self._stop_recording()
        if self._transcript_writer:
            self._transcript_writer.finalize()
        if self._llm and hasattr(self._llm, "close"):
            await self._llm.close()
        self.exit()
