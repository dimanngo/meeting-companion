"""Auto-save clean transcript to Markdown files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class TranscriptWriter:
    """Append-only Markdown writer for clean transcripts."""

    def __init__(self, output_dir: str, title: str = "meeting"):
        self._output_dir = Path(output_dir).expanduser()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._title = title
        date_str = datetime.now().strftime("%Y-%m-%d")
        self._filepath = self._output_dir / f"{date_str}_{title}.md"
        self._initialized = False

    @property
    def filepath(self) -> Path:
        return self._filepath

    def _init_file(self) -> None:
        """Write the Markdown header if the file doesn't exist yet."""
        if self._initialized:
            return
        if not self._filepath.exists():
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            header = f"# Meeting Transcript — {self._title}\n\n"
            header += f"**Date:** {date_str}\n\n---\n\n"
            self._filepath.write_text(header)
        self._initialized = True

    def append(self, timestamp: str, text: str) -> None:
        """Append a transcript segment to the Markdown file."""
        self._init_file()
        with open(self._filepath, "a") as f:
            f.write(f"**[{timestamp}]** {text}\n\n")

    def finalize(self) -> None:
        """Add a footer to the transcript file."""
        self._init_file()
        end_time = datetime.now().strftime("%H:%M")
        with open(self._filepath, "a") as f:
            f.write(f"\n---\n\n*Transcript ended at {end_time}*\n")
