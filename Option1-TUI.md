# Option 1: Pure Terminal UI (TUI) — "meeting-tui"

## Overview

A single Python application with a rich split-pane terminal interface built with Textual. Captures microphone audio, transcribes in real-time using faster-whisper (local), cleans up transcription via LLM, and provides an interactive chat pane to query the meeting context — all within the terminal.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Textual TUI App                       │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │   Live Transcript     │  │   Chat Interface         │ │
│  │   (auto-scrolling)    │  │   (query meeting context)│ │
│  │                       │  │                          │ │
│  │  [14:01] ...spoke...  │  │  You: What was decided   │ │
│  │  [14:02] ...about...  │  │       about the budget?  │ │
│  │  [14:03] ...then we.. │  │                          │ │
│  │                       │  │  AI: Based on the        │ │
│  │                       │  │      discussion at 14:02 │ │
│  └──────────────────────┘  └──────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ ● Recording 00:23:45 │ Words: 3,412 │ Chunks: 47   │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌─────────────────┐     ┌────────────────────┐
│  Audio Pipeline  │     │   LLM Backend      │
│  sounddevice     │     │   Ollama (local)   │
│  → VAD           │     │   or OpenAI API    │
│  → faster-whisper│     │                    │
└─────────────────┘     └────────────────────┘
         │
         ▼
┌─────────────────┐
│  transcript.md   │
│  transcript.json │
│  (auto-saved)    │
└─────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| UI Framework | [Textual](https://textual.textualize.io/) v3+ | Rich TUI with split panes, scrolling, input |
| Audio Capture | [sounddevice](https://python-sounddevice.readthedocs.io/) | Cross-platform mic capture via PortAudio |
| Voice Activity Detection | [silero-vad](https://github.com/snakers4/silero-vad) via [ONNX Runtime](https://onnxruntime.ai/) | Detect speech vs silence to chunk audio intelligently (lightweight ONNX backend, ~30MB) |
| Transcription | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2-based Whisper, fast on CPU/GPU |
| LLM (local) | [Ollama](https://ollama.ai/) + `mistral` or `phi-3` or `llama3.1:8b` | Transcript cleanup + chat |
| LLM (cloud) | [Google Gemini API](https://ai.google.dev/) (`gemini-3-flash-preview`, `gemini-3-pro-preview`) | Alternative/fallback for cleanup + chat. Gemini 3 Flash: best price-performance with 1M context. Gemini 3 Pro: most advanced reasoning. Both support dynamic thinking levels |
| Persistence | Markdown + JSON sidecar | Clean `.md` transcript + structured `.json` (timestamps, confidence, raw/clean pairs) |
| Config | TOML + CLI overrides + env vars | `~/.config/meeting-tui/config.toml` for defaults, `click` CLI flags for overrides, env vars for secrets (API keys). Precedence: CLI > env > config > defaults |
| Package Management | `uv` | Fast Python package/project manager, standard `pyproject.toml` |

## Project Structure

```
meeting-tui/
├── pyproject.toml
├── README.md
├── .env.example
├── src/
│   └── meeting_tui/
│       ├── __init__.py
│       ├── __main__.py              # Entry point
│       ├── app.py                   # Textual App class, layout
│       ├── config.py                # Configuration loading (TOML + CLI + env vars, layered precedence)
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── capture.py           # Mic capture via sounddevice
│       │   └── vad.py               # Voice activity detection + chunking
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
│       │   └── manager.py           # Chat context manager, history
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── transcript_writer.py # Auto-save clean transcript to .md
│       │   └── json_writer.py       # Auto-save structured data to .json (timestamps, confidence, raw/clean)
│       └── widgets/
│           ├── __init__.py
│           ├── transcript_pane.py   # Live transcript display widget
│           ├── chat_pane.py         # Chat input/output widget
│           └── status_bar.py        # Recording status, stats
└── tests/
    ├── test_audio_capture.py
    ├── test_transcription.py
    ├── test_cleaner.py
    └── test_chat_manager.py
```

## Implementation Plan

### Phase 1: Project Scaffolding & Audio Pipeline

- [ ] Initialize Python project with `pyproject.toml`, dependencies, and `uv`/`pip` setup
- [ ] Implement `config.py` — layered configuration: load defaults from `~/.config/meeting-tui/config.toml`, override with environment variables (secrets/API keys), override with CLI flags (via `click`). Precedence: CLI > env > config file > defaults
- [ ] Implement `audio/capture.py` — mic capture using `sounddevice` in a background thread, yielding raw PCM chunks via an `asyncio.Queue`
- [ ] Implement `audio/vad.py` — Silero VAD wrapper (via ONNX Runtime backend for lightweight footprint ~30MB) that receives raw audio chunks and groups them into speech segments (buffered by silence boundaries). Use frame-level confidence smoothing: speech start when confidence > 0.5 for N consecutive frames, speech end after M frames of silence
- [ ] Write unit tests for audio capture (mock `sounddevice`) and VAD chunking logic
- [ ] Manual integration test: run capture + VAD, print detected speech segments to stdout

### Phase 2: Transcription Engine

- [ ] Implement `transcription/engine.py` — load `faster-whisper` model (configurable size: `tiny`, `base`, `small`, `medium`), accept audio segments, return timestamped text
- [ ] Wire audio pipeline → transcription: capture → VAD → transcribe, print raw transcript to stdout
- [ ] Implement `transcription/cleaner.py` — LLM-based cleanup pass: takes raw transcript chunk, sends to LLM with a cleanup prompt (fix grammar, remove filler words, format), returns clean text
- [ ] Implement `persistence/transcript_writer.py` — append-only Markdown writer for clean transcript with timestamps; parallel `json_writer.py` for structured JSON sidecar (segment ID, timestamp, raw text, clean text, confidence score). Output: `{date}_{title}.md` + `{date}_{title}.json`
- [ ] Write unit tests for transcription engine (mock model) and cleaner (mock LLM)

### Phase 3: LLM Backends

- [ ] Implement `llm/base.py` — abstract interface with `complete(prompt, context) -> str` and `stream(prompt, context) -> AsyncIterator[str]`
- [ ] Implement `llm/ollama_backend.py` — Ollama HTTP API client (uses `httpx`), supports streaming
- [ ] Implement `llm/openai_backend.py` — OpenAI API client (uses `openai` SDK), supports streaming
- [ ] Implement `llm/gemini_backend.py` — Google Gemini API client (uses `google-genai` SDK), supports streaming. Leverage Gemini 3's 1M token context window for long meetings without rolling summary. Support configurable `thinking_level` (`low` for cleanup, `high` for chat reasoning)
- [ ] Config-driven backend selection: user picks `ollama`, `openai`, or `gemini` in config
- [ ] Write unit tests for both backends (mock HTTP responses)

### Phase 4: Chat Manager

- [ ] Implement `chat/manager.py` — maintains conversation history, builds prompts with meeting transcript as system context, manages token budget (truncation strategy for long meetings)
- [ ] Token budget strategy: use rolling window of most recent N tokens of transcript + full chat history, or summarize older transcript segments
- [ ] Write unit tests for context assembly and truncation

### Phase 5: Terminal UI

- [ ] Implement `app.py` — Textual `App` subclass, define layout (horizontal split: transcript | chat, bottom status bar)
- [ ] Implement `widgets/transcript_pane.py` — scrollable rich text area, receives transcript updates via Textual message passing, auto-scrolls, color-codes raw vs clean text
- [ ] Implement `widgets/chat_pane.py` — input field + scrollable output area, sends user messages to `ChatManager`, streams LLM responses token-by-token
- [ ] Implement `widgets/status_bar.py` — shows recording indicator (●/⏸), elapsed time, word count, current model, audio level meter
- [ ] Wire everything together: audio pipeline runs in background worker (`Textual.run_worker`), transcript updates push to UI, chat uses accumulated context
- [ ] Keyboard shortcuts:
  - `Ctrl+R` — start/stop recording
  - `Ctrl+E` — export/save transcript now
  - `Ctrl+L` — switch focus between transcript and chat pane
  - `Tab` — cycle focus
  - `Ctrl+Q` — quit

### Phase 6: Polish & Quality of Life

- [ ] Add `--device` CLI flag (via `click`) to list and select audio input devices
- [ ] Add `--model` CLI flag to override transcription model size
- [ ] Add `--output` CLI flag for transcript output directory
- [ ] Add `--llm-backend` CLI flag to select LLM backend (`ollama`, `openai`, `gemini`)
- [ ] Implement graceful shutdown: flush transcript, save chat history
- [ ] Add error handling: mic disconnection recovery, LLM timeout/retry
- [ ] Add optional speaker diarization hint (manual speaker labels via hotkey)
- [ ] Write integration tests: full pipeline from audio file → transcript → chat
- [ ] README with installation instructions, usage examples, configuration guide

## Key Design Decisions

1. **Async architecture:** The Textual event loop is asyncio-based. Audio capture runs in a background thread (sounddevice callback), bridged to async via `asyncio.Queue`. Transcription runs in a Textual worker thread to avoid blocking the UI.

2. **Chunking strategy:** VAD-based chunking (not fixed-time) produces better transcription quality because segments align with natural speech boundaries.

3. **Dual transcript (Markdown + JSON sidecar):** The `.md` file is the human-readable clean transcript. The `.json` sidecar stores structured data (segment IDs, timestamps, confidence scores, raw vs clean text) enabling future features like search, re-processing, and analytics without complicating the Markdown output.

4. **Token budget for long meetings:** For a 1-hour meeting (~10K words), the full transcript fits in most LLM context windows. For longer meetings, implement a rolling summary: older portions are summarized and prepended to the context.

## Dependencies

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "textual>=3.0",
    "sounddevice>=0.5",
    "numpy>=1.26",
    "faster-whisper>=1.1",
    "onnxruntime>=1.17",
    "silero-vad>=5.1",
    "httpx>=0.27",
    "openai>=1.50",
    "google-genai>=1.0",
    "rich>=13.0",
    "click>=8.1",
    "python-dotenv>=1.0",
]
```

> **Note:** `tomllib` is in the Python standard library since 3.11 — no external TOML dependency needed for reading config.

## Estimated Complexity

| Phase | Effort |
|---|---|
| Phase 1: Scaffolding & Audio | Small |
| Phase 2: Transcription | Small–Medium |
| Phase 3: LLM Backends | Small |
| Phase 4: Chat Manager | Medium |
| Phase 5: Terminal UI | Medium–Large |
| Phase 6: Polish | Medium |
