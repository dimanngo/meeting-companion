# Meeting TUI - Deep Review and Analysis Report

## Top Findings (Ranked)

| Rank | Issue | Severity | End-User Value if Fixed | Effort | Evidence |
|---|---|---|---|---|---|
| 1 | Transcription confidence bug (`avg_logprob` vs `avg_log_prob`) causes incorrect confidence output | High | High | Low | `src/meeting_tui/transcription/engine.py:70`, failing test `tests/test_transcription.py:86` |
| 2 | JSON persistence is quadratic: rewrites full JSON on every segment | High | High (long meetings stay responsive) | Medium | `src/meeting_tui/persistence/json_writer.py:63`, `src/meeting_tui/persistence/json_writer.py:65` |
| 3 | Audio queue has no max size; can grow unbounded if downstream slows | High | High (prevents memory growth / lag) | Medium | `src/meeting_tui/audio/capture.py:22`, `src/meeting_tui/audio/capture.py:38` |
| 4 | Chat streaming redraws entire chat log per token (`O(n*m)` behavior) | Medium | High (smoother chat on long sessions) | Medium | `src/meeting_tui/widgets/chat_pane.py:73`, `src/meeting_tui/widgets/chat_pane.py:97` |
| 5 | Signal handler setup is Unix-specific and can fail on unsupported loops/platforms | Medium | Medium | Low | `src/meeting_tui/app.py:139` |
| 6 | Heavy dependency footprint (torch via `silero-vad`) increases install size/time significantly | Medium | High (faster install/start adoption) | Medium/High | `pyproject.toml:14`, measured `.venv` size `671M`, `torch` ~`333MB` |
| 7 | `MeetingApp` is a large orchestrator (575 LOC), raising maintenance risk | Medium | Medium | Medium/High | `src/meeting_tui/app.py`, module metrics collected |
| 8 | Private method coupling across modules (`_load_model`, `_save`) reduces API safety | Medium | Medium | Low/Medium | `src/meeting_tui/__main__.py:81`, `src/meeting_tui/__main__.py:85`, `src/meeting_tui/app.py:500` |

## Performance and Quality Metrics

- Code size: `1,888` LOC in `src`, `931` LOC in tests.
- Test status: `47 passed`, `1 failed` (`tests/test_transcription.py::test_transcribe_confidence_averaging`), total `~0.79s`.
- Slowest tests: Gemini/OpenAI backend tests dominate (up to `0.30s` each).
- Cold import timings (fresh process):
  - `meeting_tui.config`: `~28ms`
  - `meeting_tui.audio.capture`: `~146ms`
  - `meeting_tui.app`: `~269ms`
- JSON writer micro-benchmark (1000 segments): `~5.01s` total, clear nonlinear growth.
- Markdown transcript writer micro-benchmark (1000 appends): `~0.03s`.

## Codebase Structure Assessment

### Strong points

- Clear domain split: `audio/`, `transcription/`, `llm/`, `chat/`, `persistence/`, `widgets/`.
- Async-first pipeline with test coverage across unit + integration.
- Config layering (defaults/file/env/CLI) is practical.

### Weak points

- Runtime orchestration concentrated in `src/meeting_tui/app.py`, mixing UI state, pipeline control, retries, persistence, and lifecycle.
- Some internal/private APIs are called externally, making refactors fragile.

## Dependency Assessment

- Dependency graph is broad due multi-backend + speech stack.
- Main cost driver is `silero-vad -> torch/torchaudio` footprint.
- For a TUI tool, installation weight is high relative to app size/functionality.

## Overarching Improvement Plan (Prioritized)

1. Fix confidence attribute handling in transcription engine (`avg_logprob` + fallback for `avg_log_prob`) and keep the existing test.
2. Refactor `JSONWriter` to append incrementally (JSONL or buffered writes + periodic flush) instead of full file rewrite per segment.
3. Add bounded audio queue with overflow policy (drop oldest or backpressure) and monitoring.
4. Rework streaming chat rendering to update only the active assistant line instead of full-log redraw.
5. Make signal registration platform-safe (`try/except NotImplementedError`) and test lifecycle behavior.
6. Split `MeetingApp` into pipeline controller + UI adapter + persistence coordinator.
7. Replace cross-module private method calls with public API methods (`load_model()`, `flush()`/`save()`).
8. Revisit dependency strategy for VAD to reduce install footprint (optional extras or lighter runtime path).

 
