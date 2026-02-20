# Meeting TUI — Unified Improvement Plan

Both review reports agree on the core bottlenecks (JSON persistence, chat rendering) and complement each other with distinct findings (Report 1 focuses on LLM prompt architecture and context strategy; Report 2 surfaces the confidence bug, unbounded queue, signal safety, dependency weight, and code structure). No outright contradictions exist — only one minor effort-estimate disagreement, captured in the Disagreements section below.

## Phase 1 — Quick Wins (Low effort, High value)

### 1. Fix transcription confidence bug *(Report 2 only)*

In `src/meeting_tui/transcription/engine.py` L70, change `getattr(segment, "avg_logprob", 0.0)` → `getattr(segment, "avg_log_prob", getattr(segment, "avg_logprob", 0.0))` to match the actual `faster-whisper` attribute name while keeping a fallback for older versions. This immediately fixes the failing test at `tests/test_transcription.py` L64–76 and restores meaningful confidence output.

### 2. Guard signal handler for cross-platform safety *(Report 2 only)*

Wrap the `add_signal_handler` call at `src/meeting_tui/app.py` L139 in a `try/except (NotImplementedError, OSError)` block so the app doesn't crash on Windows or unsupported event loops.

### 3. Add `close()` to `LLMBackend` base class *(Discovered during research)*

Declare an `async def close(self)` method (default no-op) in `src/meeting_tui/llm/base.py` so `app.py` L525 can call it directly without `hasattr` duck-typing.

## Phase 2 — Critical Performance (Medium effort, High value)

### 4. Refactor JSON persistence to append-only JSONL *(Both reports, P0 / Rank 2)*

Replace the full-rewrite `_save()` in `src/meeting_tui/persistence/json_writer.py` L65–73 with a JSON Lines strategy: open the output file in append mode and write one JSON object per line per segment. This drops cumulative I/O from $O(N^2)$ to $O(N)$. Update `add_segment()` to write only the new segment. Provide a `flush()` public method to replace the external `_save()` call in `src/meeting_tui/app.py` L500.

### 5. Bound the audio queue *(Report 2 only, Rank 3)*

Set `maxsize` on the `asyncio.Queue` at `src/meeting_tui/audio/capture.py` L22 (e.g., 200 chunks ≈ ~30 s of audio at typical chunk sizes). In the `_audio_callback` at L32–38, handle `QueueFull` by dropping the oldest chunk or logging a warning. Also surface `status` flags (overflow/underflow) instead of silently ignoring them.

### 6. Optimize chat pane streaming rendering *(Both reports, P1 / Rank 4)*

Replace the per-token `_rewrite_all()` in `src/meeting_tui/widgets/chat_pane.py` L75–78 with in-place appending to the last `RichLog` line, or batch UI updates on a timer (e.g., every 50 ms). Also fix the redundant double-render in `end_assistant_stream()` at L80–85.

## Phase 3 — LLM Architecture (Medium effort, High value)

### 7. Refactor chat prompt to structured message lists *(Report 1 only, P0)*

- Define a `ChatMessage` dataclass (`role: str`, `content: str`) in `src/meeting_tui/llm/base.py`.
- Change `LLMBackend.complete()` and `stream()` signatures from `(prompt: str, context: str)` to accept `messages: list[ChatMessage]` with a `context: str` for the system prompt.
- Update `src/meeting_tui/chat/manager.py` L57–63 to pass `_messages` as a structured list instead of flattening into a single string via `_build_chat_prompt()`.
- Update all three backends (openai, ollama, gemini) to map `ChatMessage` objects to their native message formats.

### 8. Expose public model-loading API *(Report 2, Rank 8)*

Rename `_load_model()` to `load_model()` in both `VADProcessor` and `TranscriptionEngine`. Update callers in `src/meeting_tui/__main__.py` L81–85 and `src/meeting_tui/app.py` L192, L201.

## Phase 4 — Resilience & UX (High effort, Medium value)

### 9. Smart context window management *(Report 1 only, P2)*

Replace the naive prefix-drop truncation in `src/meeting_tui/chat/manager.py` L43–51 with a strategy that keeps the first $K$ segments (introductions/agenda) plus a sliding window of recent segments. Optionally, summarize the middle section using the LLM itself when the transcript exceeds the context budget.

### 10. Split `MeetingApp` into smaller components *(Report 2, Rank 7)*

Factor `src/meeting_tui/app.py` (576 LOC) into:

- `PipelineController` — audio → VAD → transcription → clean loop
- `UIAdapter` — widget queries, focus, keybindings
- `PersistenceCoordinator` — JSON/Markdown/chat-history save logic

Cache `self.query_one(StatusBar)` into an instance variable instead of re-querying per segment.

## Phase 5 — Dependency Optimization (Medium–High effort, Medium value)

### 11. Make LLM backends optional extras *(Report 2, Rank 6)*

In `pyproject.toml`, move `openai`, `google-genai`, and `httpx` into optional dependency groups (`[project.optional-dependencies]`) so users install only the backend they need.

### 12. Explore lighter VAD runtime path *(Report 2, Rank 6)*

Investigate whether `silero-vad` can run on `onnxruntime` alone (without full `torch`/`torchaudio` — currently ~333 MB of the 671 MB venv). If feasible, make `torch` an optional extra and default to the ONNX path.

## Future / Deferred

### 13. Automatic speaker diarization *(Report 1 only, P3)*

Integrate `pyannote.audio` or similar for auto speaker detection. Low priority for MVP — manual `Ctrl+S` labeling is sufficient for now.

---

## Verification

- **After Step 1:** `pytest tests/test_transcription.py` — all 48 tests should pass (currently 47 pass, 1 fails).
- **After Steps 4–6:** Run a simulated 1000-segment micro-benchmark on `JSONWriter`; confirm < 0.1 s total. Stream a long chat and verify no UI flicker.
- **After Step 7:** Inspect LLM API payloads (e.g., with `httpx` logging) to confirm multi-turn message lists are sent instead of a single user string.
- **After Step 10:** `wc -l src/meeting_tui/app.py` should be < 200 LOC.
- **End-to-end:** Run a 5-minute live meeting capture and verify transcript, chat, and export all function correctly.

---

## Disagreements Between Reports

| Topic | Report 1 (Gemini CLI) | Report 2 | Resolution |
|---|---|---|---|
| **JSON persistence refactor effort** | **Low** — "switch to JSONL" | **Medium** — considers downstream consumers, testing, migration | Treat as **Medium**: the write path is simple, but callers that read/parse the output (export, tests) also need updating. |
