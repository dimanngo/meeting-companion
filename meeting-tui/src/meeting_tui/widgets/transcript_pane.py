"""Live transcript display widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static, RichLog


class TranscriptUpdated(Message):
    """Message sent when a new transcript segment is available."""

    def __init__(self, timestamp: str, raw_text: str, clean_text: str) -> None:
        super().__init__()
        self.timestamp = timestamp
        self.raw_text = raw_text
        self.clean_text = clean_text


class TranscriptPane(Static):
    """Scrollable pane showing the live meeting transcript."""

    DEFAULT_CSS = """
    TranscriptPane {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    TranscriptPane #transcript-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    TranscriptPane RichLog {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("📝 Live Transcript", id="transcript-title")
        yield RichLog(highlight=True, markup=True, wrap=True, id="transcript-log")

    @property
    def log_widget(self) -> RichLog:
        return self.query_one("#transcript-log", RichLog)

    def add_segment(self, timestamp: str, clean_text: str) -> None:
        """Add a cleaned transcript segment to the display."""
        self.log_widget.write(f"[bold cyan]\\[{timestamp}][/bold cyan] {clean_text}")

    def add_raw_segment(self, timestamp: str, raw_text: str) -> None:
        """Add a raw (uncleaned) transcript segment."""
        self.log_widget.write(
            f"[bold cyan]\\[{timestamp}][/bold cyan] [dim]{raw_text}[/dim]"
        )
