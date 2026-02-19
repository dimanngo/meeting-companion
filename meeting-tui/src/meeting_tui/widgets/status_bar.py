"""Status bar widget showing recording state and statistics."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Static):
    """Status bar showing recording indicator, elapsed time, word count, and model info."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $boost;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    """

    recording: reactive[bool] = reactive(False)
    elapsed_seconds: reactive[int] = reactive(0)
    word_count: reactive[int] = reactive(0)
    segment_count: reactive[int] = reactive(0)
    model_name: reactive[str] = reactive("—")
    activity: reactive[str] = reactive("")  # Background activity indicator
    audio_level: reactive[float] = reactive(0.0)  # 0.0–1.0 normalised mic level
    no_speech_warning: reactive[bool] = reactive(False)

    def render(self) -> str:
        if self.activity:
            return f"⏳ {self.activity} │ Model: {self.model_name}"

        indicator = "🔴 Recording" if self.recording else "⏸️  Ready"
        hours, remainder = divmod(self.elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        parts = [f"{indicator} {time_str}"]

        if self.recording:
            parts.append(f"🎤 {self._format_level()}")
            if self.no_speech_warning:
                parts.append("⚠️ No speech")

        parts.extend([
            f"Words: {self.word_count:,}",
            f"Segments: {self.segment_count}",
            f"Model: {self.model_name}",
        ])

        return " │ ".join(parts)

    def _format_level(self) -> str:
        """Return a small visual bar representing the current audio level."""
        blocks = min(int(self.audio_level * 8), 8)
        if blocks == 0 and self.audio_level > 0.001:
            blocks = 1  # show at least a sliver when signal exists
        return "█" * blocks + "░" * (8 - blocks)
