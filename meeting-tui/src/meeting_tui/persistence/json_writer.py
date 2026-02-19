"""Auto-save structured transcript data to JSON sidecar files."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
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
    """Writes structured transcript data to a JSON sidecar file."""

    def __init__(self, output_dir: str, title: str = "meeting"):
        self._output_dir = Path(output_dir).expanduser()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._title = title
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._filepath = self._output_dir / f"{date_str}_{title}.json"
        self._segments: list[TranscriptSegment] = []
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
        """Add a transcript segment and save to disk."""
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
        self._segments.append(segment)
        self._save()

    def _save(self) -> None:
        """Write all segments to the JSON file."""
        data = {
            "title": self._title,
            "date": datetime.now().isoformat(),
            "segments": [asdict(s) for s in self._segments],
            "total_segments": len(self._segments),
        }
        with open(self._filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
