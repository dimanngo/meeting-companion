# Implementation Plan — Meeting TUI

## Overview

A single Python application with a rich split-pane terminal interface built with Textual. Captures microphone audio, transcribes in real-time using faster-whisper (local), cleans up transcription via LLM, and provides an interactive chat pane to query the meeting context — all within the terminal.

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| UI Framework | Textual 3+ | Rich TUI with split panes, scrolling, input |
| Audio Capture | sounddevice | Cross-platform mic capture via PortAudio |
| Voice Activity Detection | Silero VAD (ONNX Runtime) | Detect speech vs silence to chunk audio |
| Transcription | faster-whisper | CTranslate2-based Whisper, fast on CPU/GPU |
| LLM (local) | Ollama | Transcript cleanup + chat |
| LLM (cloud) | Google Gemini API, OpenAI API | Alternative/fallback for cleanup + chat |
| Persistence | Markdown + JSON sidecar | Clean `.md` transcript + structured `.json` |
| Config | TOML + CLI overrides + env vars | Layered configuration with precedence |
| Package Management | uv | Fast Python package/project manager |

## Project Structure

```
meeting-tui/
├── pyproject.toml
├── README.md
├── .env.example
├── src/
│   └── meeting_tui/
│       ├── __init__.py
│       ├── __main__.py              # Entry point (Click CLI)
│       ├── app.py                   # Textual App class, layout, pipeline wiring
│       ├── config.py                # Configuration loading (TOML + CLI + env vars)
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── capture.py           # Mic capture via sounddevice
│       │   └── vad.py               # Voice activity detection + chunking (Silero VAD)
│       ├── transcription/
│       │   ├── __init__.py
│       │   ├── engine.py            # faster-whisper transcription engine
│       │   └── cleaner.py           # LLM-based transcript cleanup
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract LLM interface
│       │   ├── ollama_backend.py    # Ollama local backend
│       │   ├── openai_backend.py    # OpenAI API backend
│       │   └── gemini_backend.py    # Google Gemini API backend
│       ├── chat/
│       │   ├── __init__.py
│       │   └── manager.py           # Chat context manager, history, token budget
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── transcript_writer.py # Auto-save clean transcript to .md
│       │   └── json_writer.py       # Auto-save structured data to .json
│       └── widgets/
│           ├── __init__.py
│           ├── transcript_pane.py   # Live transcript display widget
│           ├── chat_pane.py         # Chat input/output widget
│           └── status_bar.py        # Recording status, stats
└── tests/
    ├── __init__.py
    ├── test_audio_capture.py        # Audio capture + VAD state machine tests
    ├── test_transcription.py        # Transcription engine + cleaner tests
    ├── test_llm_backends.py         # Ollama, OpenAI, Gemini backend tests
    ├── test_chat_manager.py         # Chat context assembly + truncation tests
    └── test_integration.py          # Full pipeline integration tests
```

---

## Phase 1: Project Scaffolding & Audio Pipeline

- √ Initialize Python project with `pyproject.toml`, dependencies, and `uv` setup
- √ Create package structure with `src/meeting_tui/` and all subpackages
- √ Implement `config.py` — layered configuration: load defaults from `~/.config/meeting-tui/config.toml`, override with environment variables (secrets/API keys), override with CLI flags (via Click). Precedence: CLI > env > config file > defaults
- √ Implement `audio/capture.py` — mic capture using sounddevice in a background thread, yielding raw PCM chunks via `asyncio.Queue`
- √ Implement `audio/vad.py` — Silero VAD wrapper (via ONNX Runtime) that receives raw audio chunks and groups them into speech segments using frame-level confidence smoothing: speech start when confidence > 0.5 for N consecutive frames, speech end after M frames of silence
- √ Write unit tests for audio capture (mock sounddevice) and VAD chunking logic (8 + 7 tests)
- √ Pipeline wiring: capture → VAD → transcribe integrated in `app.py` pipeline loop

## Phase 2: Transcription Engine

- √ Implement `transcription/engine.py` — load faster-whisper model (configurable size: tiny, base, small, medium), accept audio segments, return timestamped text with confidence scores
- √ Implement `transcription/cleaner.py` — LLM-based cleanup pass: takes raw transcript chunk, sends to LLM with a cleanup prompt (fix grammar, remove filler words, format), returns clean text
- √ Implement `persistence/transcript_writer.py` — append-only Markdown writer for clean transcript with timestamps and header/footer
- √ Implement `persistence/json_writer.py` — structured JSON sidecar writer (segment ID, timestamp, raw text, clean text, confidence score, language)
- √ Wire audio pipeline → transcription in `app.py`: capture → VAD → transcribe → clean → display + save
- √ Write unit tests for transcription engine (mock model) and cleaner (mock LLM) (5 + 4 tests)

## Phase 3: LLM Backends

- √ Implement `llm/base.py` — abstract interface with `complete(prompt, context) -> str` and `stream(prompt, context) -> AsyncIterator[str]`
- √ Implement `llm/ollama_backend.py` — Ollama HTTP API client (uses httpx), supports streaming via server-sent events
- √ Implement `llm/openai_backend.py` — OpenAI API client (uses openai SDK), supports streaming
- √ Implement `llm/gemini_backend.py` — Google Gemini API client (uses google-genai SDK), supports streaming with configurable `thinking_level` (minimal/low/medium/high)
- √ Config-driven backend selection: user picks `ollama`, `openai`, or `gemini` in config — factory function `create_llm_backend()` in `app.py`
- √ Write unit tests for all backends (mock HTTP responses) — 4 + 4 + 3 tests

## Phase 4: Chat Manager

- √ Implement `chat/manager.py` — maintains conversation history, builds prompts with meeting transcript as system context, manages token budget (truncation strategy for long meetings via rolling window of most recent content)
- √ Write unit tests for context assembly and truncation logic (11 tests)

## Phase 5: Terminal UI

- √ Implement `app.py` — Textual `App` subclass with horizontal split layout (transcript | chat) and bottom status bar. Wires audio pipeline → VAD → transcription → cleaner → display + save. Runs pipeline in background worker (`run_worker`)
- √ Implement `widgets/transcript_pane.py` — scrollable RichLog area, receives transcript updates, auto-scrolls, shows raw (dimmed) and clean text with timestamps
- √ Implement `widgets/chat_pane.py` — input field + scrollable output area, sends user messages to ChatManager, streams LLM responses token-by-token
- √ Implement `widgets/status_bar.py` — shows recording indicator (●/⏸), elapsed time, word count, segment count, current model name
- √ Implement `__main__.py` — Click CLI entry point with `--device`, `--model`, `--output`, `--llm-backend`, `--title`, `--list-devices`, `--config` flags
- √ Keyboard shortcuts: Ctrl+R (record), Ctrl+E (export), Ctrl+L (switch focus), Ctrl+S (speaker label), Tab (cycle), Ctrl+Q (quit with graceful shutdown)

## Phase 6: Polish & Quality of Life

- √ Create `.env.example` with all environment variable documentation
- √ Create `README.md` with comprehensive user guide (quick start, usage, configuration, output format, troubleshooting)
- √ Install dependencies and verify all imports succeed
- √ Verify CLI works (`--help`, `--list-devices`)
- √ Add `--device` CLI support for device selection by name (partial match with disambiguation)
- √ Implement graceful shutdown: SIGINT/SIGTERM signal handlers, flush transcript, save chat history to `_chat.md` sidecar
- √ Add error handling: mic disconnection recovery (3 retry attempts with backoff), LLM timeout/retry with exponential backoff (3 retries)
- √ Add optional speaker diarization hint (Ctrl+S opens modal for speaker label, labels prepended to transcript segments)
- √ Write integration tests: full pipeline from mocked audio → transcript → chat (2 tests)
- √ Add progress indicator for initial model download (notification on first recording start)

---

## Status Summary

> Historical snapshot captured at the time this implementation phase was completed. For current status, run the test suite in the active codebase.

| Phase | Status | Notes |
|---|---|---|
| Phase 1: Scaffolding & Audio | ✅ Complete | 15 tests passing |
| Phase 2: Transcription | ✅ Complete | 9 tests passing |
| Phase 3: LLM Backends | ✅ Complete | 11 tests passing |
| Phase 4: Chat Manager | ✅ Complete | 11 tests passing |
| Phase 5: Terminal UI | ✅ Complete | All widgets, layout, keybindings, speaker labels |
| Phase 6: Polish | ✅ Complete | Error handling, signal shutdown, retry logic, tests |

**All 48 tests passing. All planned tasks complete.**
