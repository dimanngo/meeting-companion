"""Auto-save structured transcript data to JSON Lines sidecar files."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class TranscriptSegment:
    """A single transcript segment with metadata."""

    segment_id: int
    start_time: float
    end_time: float
    timestamp: str
    raw_text: str
    clean_text: str
    confidence: float
    language: str | None = None


class JSONWriter:
    """Writes structured transcript data to a JSON Lines (.jsonl) sidecar file.

    Each segment is appended as an individual JSON object on its own line,
    giving O(1) per-segment I/O instead of rewriting the entire file.
    """

    def __init__(self, output_dir: str, title: str = "meeting"):
        self._output_dir = Path(output_dir).expanduser()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._title = title
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._filepath = self._output_dir / f"{date_str}_{title}.jsonl"
        self._segment_count = 0
        self._next_id = 1

    @property
    def filepath(self) -> Path:
        return self._filepath

    def add_segment(
        self,
        start_time: float,
        end_time: float,
        timestamp: str,
        raw_text: str,
        clean_text: str,
        confidence: float,
        language: str | None = None,
    ) -> None:
        """Add a transcript segment and append it to disk."""
        segment = TranscriptSegment(
            segment_id=self._next_id,
            start_time=start_time,
            end_time=end_time,
            timestamp=timestamp,
            raw_text=raw_text,
            clean_text=clean_text,
            confidence=confidence,
            language=language,
        )
        self._next_id += 1
        self._segment_count += 1
        with open(self._filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(segment), ensure_ascii=False) + "\n")

    @property
    def total_segments(self) -> int:
        """Return the number of segments written so far."""
        return self._segment_count

    def flush(self) -> None:
        """Explicit flush — a no-op since each segment is written immediately.

        Provided as a public API for callers that previously used ``_save()``.
        """
