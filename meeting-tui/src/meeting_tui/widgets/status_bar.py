"""Status bar widget showing recording state and statistics."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Static):
    """Bottom status bar showing recording indicator, elapsed time, word count, and model info."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    """

    recording: reactive[bool] = reactive(False)
    elapsed_seconds: reactive[int] = reactive(0)
    word_count: reactive[int] = reactive(0)
    segment_count: reactive[int] = reactive(0)
    model_name: reactive[str] = reactive("—")
    activity: reactive[str] = reactive("")  # Background activity indicator

    def render(self) -> str:
        if self.activity:
            return f" ⏳ {self.activity} │ Model: {self.model_name} "

        indicator = "● Recording" if self.recording else "⏸ Ready"
        hours, remainder = divmod(self.elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return (
            f" {indicator} {time_str} │ "
            f"Words: {self.word_count:,} │ "
            f"Segments: {self.segment_count} │ "
            f"Model: {self.model_name} "
        )
