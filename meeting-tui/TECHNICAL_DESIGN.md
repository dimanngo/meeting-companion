# Meeting TUI — Technical Design Specification

> **Version:** 0.1.0  
> **Last updated:** 2026-02-19  
> **Runtime:** Python ≥ 3.11 | macOS (primary), Linux  
> **Package manager:** uv / hatch  

---

## 1. System Overview

Meeting TUI is a terminal-based application that captures live microphone audio, performs real-time speech-to-text transcription, cleans the transcript using an LLM, and provides an interactive chat interface for querying the meeting content. It runs entirely in a single process using the [Textual](https://textual.textualize.io/) TUI framework with asyncio concurrency.

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Terminal (Textual App)                       │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐ │
│  │     TranscriptPane       │  │          ChatPane                │ │
│  │  (RichLog — live text)   │  │  (RichLog + Input — Q&A)        │ │
│  └──────────────────────────┘  └──────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────────┤
│  │  StatusBar (recording state, timer, audio level, model info)    │
│  └──────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────┤
│  │  Footer (key bindings)                                          │
│  └──────────────────────────────────────────────────────────────────┘
│                                                                     │
│  ┌─ Pipeline (async) ──────────────────────────────────────────────┐│
│  │  AudioCapture → VADProcessor → TranscriptionEngine → Cleaner   ││
│  │                                      │                         ││
│  │                          ┌───────────┴────────────┐            ││
│  │                          ▼                        ▼            ││
│  │                  TranscriptWriter          JSONWriter           ││
│  │                   (.md output)            (.jsonl output)      ││
│  └────────────────────────────────────────────────────────────────┘││
│                                                                     │
│  ┌─ Chat (async) ──────────────────────────────────────────────────┐│
│  │  ChatManager → LLMBackend (stream/complete)                    ││
│  └────────────────────────────────────────────────────────────────┘││
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Data Flow

```
Microphone
  │ float32 PCM chunks (512 samples @ 16 kHz = 32 ms frames)
  ▼
AudioCapture (sounddevice InputStream, PortAudio thread)
  │ np.ndarray chunks → bounded asyncio.Queue(maxsize=200)
  ▼
VADProcessor (Silero VAD, ONNX Runtime)
  │ State machine: speech-start / speech-end detection
  │ Emits SpeechSegment (concatenated audio + timestamps)
  ▼
TranscriptionEngine (faster-whisper / CTranslate2)
  │ Runs in thread executor to avoid blocking
  │ Returns TranscriptionResult (text, confidence, language)
  ▼
TranscriptCleaner (LLM-based)                          ┌──► ChatManager
  │ Removes fillers, fixes grammar                     │    (maintains history +
  │ Retry with exponential backoff (3 attempts)        │     transcript context)
  ▼                                                    │
Display + Persist                                      │
  ├─► TranscriptPane (raw → dim, clean → normal)      │
  ├─► TranscriptWriter (append-only .md)               │
  ├─► JSONWriter (structured .jsonl, append-only)      │
  └─► ChatManager.add_transcript_segment() ────────────┘
```

---

## 2. Module Structure

```
src/meeting_tui/
├── __init__.py              # Package metadata (__version__)
├── __main__.py              # CLI entry point (Click)
├── app.py                   # Textual App, pipeline orchestration
├── config.py                # Configuration loading (TOML + env + CLI)
│
├── audio/
│   ├── capture.py           # Microphone capture via sounddevice
│   └── vad.py               # Silero VAD (ONNX) + speech segment detection
│
├── transcription/
│   ├── engine.py            # faster-whisper speech-to-text
│   └── cleaner.py           # LLM-based transcript cleanup
│
├── llm/
│   ├── base.py              # Abstract LLMBackend interface
│   ├── ollama_backend.py    # Ollama HTTP API backend
│   ├── openai_backend.py    # OpenAI API backend
│   └── gemini_backend.py    # Google Gemini API backend
│
├── chat/
│   └── manager.py           # Chat context + structured message assembly
│
├── persistence/
│   ├── transcript_writer.py # Append-only Markdown writer
│   └── json_writer.py       # Structured JSONL sidecar writer
│
└── widgets/
    ├── transcript_pane.py   # Live transcript display widget
    ├── chat_pane.py         # Chat I/O widget with streaming
    └── status_bar.py        # Recording status, timer, audio meter
```

---

## 3. Component Specifications

### 3.1 Entry Point — `__main__.py`

**Responsibility:** CLI argument parsing, pre-loading ML models, launching the Textual app.

**CLI Options (Click):**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--device` | `str` | `None` | Audio device index or name substring |
| `--model` | Choice | `None` | Whisper model size (`tiny`/`base`/`small`/`medium`/`large-v3`) |
| `--output` | Path | `None` | Transcript output directory |
| `--llm-backend` | Choice | `None` | LLM backend (`ollama`/`openai`/`gemini`) |
| `--title` | `str` | `None` | Meeting title for filenames |
| `--list-devices` | flag | — | Print audio input devices and exit |
| `--config` | Path | `None` | Path to TOML config file |

**Startup Sequence:**

1. Parse CLI arguments
2. `load_config()` — merge defaults → TOML → env vars → CLI overrides
3. **Synchronously** load VAD model (`VADProcessor.load_model()`)
4. **Synchronously** load Whisper model (`TranscriptionEngine.load_model()`)
5. Construct `MeetingApp(config, vad=vad, engine=engine)` with pre-loaded models
6. `app.run()` — enters the Textual event loop

**Design rationale — pre-loading models:** CTranslate2 (used by faster-whisper) triggers a Python 3.13+ `fds_to_keep` race condition when loaded from any thread inside an asyncio loop. Loading models synchronously before `app.run()` avoids this entirely. Progress messages are printed to stdout before the TUI takes over.

**Device Resolution:** `_resolve_device_by_name(name)` performs case-insensitive substring matching against `sounddevice.query_devices()`. If exactly one input device matches, its index is returned. Ambiguous matches print all candidates and exit.

**File Logging:** Startup configures a dedicated `meeting_tui` logger writing to `{output_dir}/meeting-tui.log`.
- Default mode uses `RotatingFileHandler` (`5 MB`, `3` backups).
- Rotation can be configured with `MEETING_TUI_LOG_MAX_BYTES` and `MEETING_TUI_LOG_BACKUP_COUNT`.
- If either is non-positive, logging falls back to a plain non-rotating file handler.

---

### 3.2 Configuration — `config.py`

**Responsibility:** Layered configuration with precedence: **CLI > environment > TOML file > defaults**.

**Configuration Dataclasses:**

| Dataclass | Key Fields | Defaults |
|-----------|-----------|----------|
| `AudioConfig` | `device`, `sample_rate`, `channels`, `block_duration_ms` | `None`, `16000`, `1`, `32` |
| `VADConfig` | `threshold`, `min_speech_frames`, `min_silence_frames`, `frame_duration_ms` | `0.5`, `6`, `30`, `32` |
| `TranscriptionConfig` | `model_size`, `language`, `compute_type`, `beam_size` | `"base"`, `None` (auto), `"int8"`, `5` |
| `LLMConfig` | `backend`, `ollama_*`, `openai_*`, `gemini_*` | `"ollama"`, see below |
| `PersistenceConfig` | `output_dir`, `title` | `~/meeting-transcripts`, `"meeting"` |
| `AppConfig` | Composes all above | — |

**LLM Defaults:**
- Ollama: `http://localhost:11434`, model `mistral`
- OpenAI: model `gpt-4o-mini`
- Gemini: model `gemini-3-flash-preview`, thinking level `low`

**Environment Variable Mapping:**

| Env Var | Config Path |
|---------|------------|
| `MEETING_TUI_LLM_BACKEND` | `llm.backend` |
| `MEETING_TUI_OLLAMA_BASE_URL` | `llm.ollama_base_url` |
| `MEETING_TUI_OLLAMA_MODEL` | `llm.ollama_model` |
| `OPENAI_API_KEY` | `llm.openai_api_key` |
| `MEETING_TUI_OPENAI_MODEL` | `llm.openai_model` |
| `GEMINI_API_KEY` | `llm.gemini_api_key` |
| `MEETING_TUI_GEMINI_MODEL` | `llm.gemini_model` |
| `MEETING_TUI_OUTPUT_DIR` | `persistence.output_dir` |
| `MEETING_TUI_WHISPER_MODEL` | `transcription.model_size` |
| `MEETING_TUI_AUDIO_DEVICE` | `audio.device` |

**Config File Location:** `~/.config/meeting-tui/config.toml` (TOML format, loaded via `tomllib`).

**Loading Algorithm:**
1. Instantiate `AppConfig()` with dataclass defaults
2. Load TOML file → `_apply_dict_to_config()`
3. Load environment variables → `_apply_dict_to_config()`
4. Apply CLI overrides dict → `_apply_dict_to_config()`

`_apply_dict_to_config()` iterates over section keys, matching them to the corresponding dataclass field via `setattr`. Unknown keys are silently ignored.

---

### 3.3 Application Core — `app.py`

**Responsibility:** Textual App subclass that owns all pipeline components, handles user interactions, and orchestrates the recording/transcription/chat pipeline.

**Class:** `MeetingApp(App)`

#### 3.3.1 Layout

```
┌─ Header ─────────────────────────────────────────────────────┐
│ ┌─ Horizontal #main-content ──────────────────────────────── │
│ │  TranscriptPane (1fr width)  │  ChatPane (1fr width)     │ │
│ └──────────────────────────────────────────────────────────── │
│ ┌─ StatusBar (height: 1) ────────────────────────────────── │ │
│ └──────────────────────────────────────────────────────────── │
│ ┌─ Footer ───────────────────────────────────────────────── │ │
│ └──────────────────────────────────────────────────────────── │
└──────────────────────────────────────────────────────────────┘
```

#### 3.3.2 Key Bindings

| Binding | Action | Description |
|---------|--------|-------------|
| `Ctrl+R` | `action_toggle_recording` | Start/stop recording |
| `Ctrl+E` | `action_export` | Force-save transcript files |
| `Ctrl+L` | `action_switch_focus` | Toggle focus between transcript and chat input |
| `Ctrl+T` | `action_copy_transcript` | Copy transcript panel text |
| `Ctrl+Y` | `action_copy_chat` | Copy chat panel text |
| `Ctrl+Shift+Left` | `action_resize_left` | Widen transcript pane |
| `Ctrl+Shift+Right` | `action_resize_right` | Widen chat pane |
| `Option+Shift+Left` | `action_resize_left` | Fallback widen transcript pane (terminal-dependent) |
| `Option+Shift+Right` | `action_resize_right` | Fallback widen chat pane (terminal-dependent) |
| `Ctrl+S` | `action_label_speaker` | Open speaker label modal |
| `Ctrl+Q` | `action_quit` | Graceful shutdown |

Command palette is disabled (`ENABLE_COMMAND_PALETTE = False`).

#### 3.3.3 Instance State

| Field | Type | Purpose |
|-------|------|---------|
| `_recording` | `bool` | Whether audio is being captured |
| `_loading` | `bool` | True while models are loading (blocks interactions) |
| `_models_ready` | `bool` | True when VAD + Whisper are loaded |
| `_recording_start` | `datetime \| None` | Recording start timestamp |
| `_word_count` | `int` | Cumulative word count |
| `_segment_count` | `int` | Cumulative segment count |
| `_current_speaker` | `str \| None` | Active speaker label |
| `_silence_warned` | `bool` | Whether 15-second silence warning was shown |
| `_audio_capture` | `AudioCapture \| None` | Mic capture instance |
| `_vad` | `VADProcessor \| None` | VAD processor |
| `_engine` | `TranscriptionEngine \| None` | Whisper engine |
| `_cleaner` | `TranscriptCleaner \| None` | LLM transcript cleaner |
| `_chat_manager` | `ChatManager \| None` | Chat context manager |
| `_llm` | `LLMBackend \| None` | LLM backend instance |
| `_transcript_writer` | `TranscriptWriter \| None` | Markdown writer |
| `_json_writer` | `JSONWriter \| None` | JSON writer |
| `_timer_handle` | `object \| None` | Timer interval handle |
| `_segment_queue` | `asyncio.Queue[SpeechSegment] \| None` | Decouples VAD detection from segment processing |
| `_segment_worker_task` | `asyncio.Task[None] \| None` | Background segment-processing task |
| `_transcript_width_pct` | `int` | Left pane width percentage for resizable split |

#### 3.3.4 Lifecycle

**`on_mount()`:**
1. Register `SIGINT`/`SIGTERM` handlers for graceful shutdown (when supported by the platform loop)
2. Create LLM backend via `create_llm_backend(config)` — factory function
3. Create `TranscriptionEngine`, `TranscriptCleaner`, `ChatManager`
4. Create `VADProcessor` (if not pre-loaded)
5. Create `TranscriptWriter` and `JSONWriter`
6. Set status bar model name and apply initial pane widths
7. Show "Ready to record" notification

**`action_toggle_recording()`:**
- If `_loading`: show warning, return
- If `_recording`: call `_stop_recording()`
- Else: call `_start_recording()`

**`_start_recording()` → `_load_and_start_pipeline()` (worker):**
1. If models not pre-loaded: load VAD → load Whisper (blocking via `_load_off_loop`)
2. Create `AudioCapture` with event loop reference
3. Start the `sd.InputStream`
4. Start segment worker (`_start_segment_worker()`) with a bounded async queue
5. Set `_recording = True`, start 1-second timer
6. Enter `_pipeline_loop()` — capture/VAD loop that enqueues segments

**`_pipeline_loop()` — Main Processing Loop:**
```
while _recording:
    chunk = await audio_capture.queue.get(timeout=0.5)
    update audio_level on StatusBar
    segment = await vad.process_chunk(chunk)
    if segment:
    await _enqueue_segment(segment)
    elif 15s elapsed with 0 segments:
        show no-speech warning
```

**`_segment_worker_loop()` — Background Segment Processing:**
```
while True:
  segment = await _segment_queue.get()
  try:
    await _process_segment(segment)
  finally:
    _segment_queue.task_done()
```

**`_cleanup_worker_loop()` — Delayed Cleanup/Persistence:**
```
while True:
  entry = await _cleanup_queue.get()
  try:
    await _process_cleanup_entry(entry)
  finally:
    _cleanup_queue.task_done()
```

On stop, `_stop_recording()` flushes VAD, enqueues the final segment (if present), waits for both queues to drain (`_drain_pipeline_queues()`), then cancels both workers.

**`_process_segment(segment)`:**
1. Transcribe via `_engine.transcribe(audio, start, end)` → `TranscriptionResult`
2. Skip if text is empty
3. Format timestamp as `HH:MM:SS`
4. Prepend speaker label if set
5. Display raw text in `TranscriptPane` (dimmed) immediately
6. Enqueue cleanup payload to `_cleanup_queue`

**`_process_cleanup_entry(entry)`:**
1. Clean via `_clean_with_retry(raw_text)` — 3 retries, exponential backoff
2. Display clean text in `TranscriptPane`
3. Persist to `.md` and `.jsonl` files
4. Add to `ChatManager` transcript context
5. Update word/segment counts in StatusBar

**`_stop_recording()`:**
1. Set `_recording = False`
2. Stop `AudioCapture`
3. Reset status bar
4. Stop timer
5. Flush remaining VAD segment, drain pending segment + cleanup queues, then stop workers

**`_attempt_mic_recovery()`:**
- On audio capture error, stop current stream
- Retry 3 times with increasing delays (2s, 4s, 6s)
- On failure: notify user, stop recording

#### 3.3.5 Panel Utilities

- `action_copy_transcript()` copies `TranscriptPane.get_plain_text()` to clipboard.
- `action_copy_chat()` copies `ChatPane.get_plain_text()` to clipboard.
- `action_resize_left()`/`action_resize_right()` adjust split widths in bounded 5% steps (30%–70%) via `_apply_panel_widths()`.

#### 3.3.6 Chat Handling

**`on_chat_submitted(event: ChatSubmitted)`:**
1. If `_loading`: show "still loading" message, return
2. Retry loop (3 attempts, exponential backoff):
   - Set status bar activity to "AI is thinking..."
   - `begin_assistant_stream()` on `ChatPane`
   - Stream tokens from `ChatManager.stream_message()`
   - `end_assistant_stream()` on `ChatPane`
3. On all retries failed: display error message

#### 3.3.7 LLM Retry Strategy

| Parameter | Value |
|-----------|-------|
| `LLM_MAX_RETRIES` | `3` |
| `LLM_RETRY_DELAY` | `1.0s` (initial) |
| Backoff | `delay *= 2` per retry |
| Fallback | Raw text returned (transcript cleanup), error shown (chat) |

#### 3.3.8 Graceful Shutdown (`action_quit`)

1. Stop recording if active
2. Finalize transcript writer (append footer)
3. Save chat history to `*_chat.md` file
4. Close LLM client if applicable
5. `self.exit()`

#### 3.3.9 Speaker Labeling

`SpeakerLabelScreen` — a `ModalScreen` that prompts for a speaker name. The label is prepended as `[SpeakerName]` to subsequent transcript segments. Empty input clears the label.

#### 3.3.10 Export

`action_export()` force-saves the current JSON file and shows a notification with both output file paths.

#### 3.3.11 System Bell Override

`bell()` is overridden to be a no-op, preventing terminal beep sounds on notifications or focus changes.

---

### 3.4 Audio Capture — `audio/capture.py`

**Class:** `AudioCapture`

**Responsibility:** Capture raw PCM audio from the system microphone and deliver fixed-size chunks to a bounded asyncio queue.

**Threading Model:**
- `sounddevice.InputStream` runs a **PortAudio callback** on a dedicated audio thread
- The callback copies the audio data and uses `loop.call_soon_threadsafe()` to push the chunk into an `asyncio.Queue(maxsize=200)`
- The main async pipeline consumes from this queue
- If the queue is full, the oldest chunk is dropped so the pipeline stays near real-time instead of accumulating unbounded backlog
- Callback status flags and queue overflow events are logged as warnings

**Audio Format:**
- Sample rate: 16,000 Hz (configurable)
- Channels: 1 (mono, configurable)
- Dtype: `float32`
- Block size: `sample_rate * block_duration_ms / 1000` = **512 samples** at default settings

**Chunk Shape:** The callback normalizes to 1D regardless of input: if `indata.ndim > 1`, takes `indata[:, 0]` (first channel); otherwise flattens.

**Lifecycle:**
- `start()` → opens `sd.InputStream` and starts it
- `stop()` → stops and closes the stream
- `queue` property → the `asyncio.Queue[np.ndarray]` consumer endpoint (bounded)

**Static Method:** `list_devices()` → returns a list of dicts with `index`, `name`, `channels` for all input-capable devices.

---

### 3.5 Voice Activity Detection — `audio/vad.py`

**Class:** `VADProcessor`

**Responsibility:** Detect speech boundaries in a stream of audio chunks and emit complete speech segments.

**ML Model:** Silero VAD (ONNX format), loaded from the `silero_vad` Python package at `silero_vad.data/silero_vad.onnx`.

**ONNX Runtime Configuration:**
- Provider: `CPUExecutionProvider`
- Threads: `inter_op=1`, `intra_op=1` (minimal CPU usage)
- State tensor shape: `(2, 1, 128)` — internal LSTM state
- Context window: 64 samples prepended to each frame

**State Machine:**

```
                    confidence ≥ threshold
         ┌──────────────────────────────────────┐
         │                                      ▼
    ┌────┴─────┐                         ┌──────────┐
    │  SILENCE │                         │ COUNTING │
    │          │◄──── reset if            │ SPEECH   │
    │          │   confidence < threshold │ FRAMES   │
    └──────────┘      before min_speech   └────┬─────┘
                                               │ speech_frames ≥ min_speech_frames
                                               ▼
                                        ┌──────────┐
                     ┌─────────────────►│IN_SPEECH │
                     │                  │          │
                     │ silence_frames   └────┬─────┘
                     │ < min_silence         │ confidence < threshold
                     │                       ▼
                     │               ┌───────────────┐
                     └───────────────│ COUNTING       │
                                    │ SILENCE FRAMES │
                                    └───────┬────────┘
                                            │ silence_frames ≥ min_silence_frames
                                            ▼
                                     Emit SpeechSegment
                                     Reset state
```

**Default Thresholds:**
- `threshold = 0.5` — VAD confidence threshold
- `min_speech_frames = 6` — ~192 ms of consecutive speech to confirm start
- `min_silence_frames = 30` — ~960 ms of consecutive silence to confirm end

**Continuous Speech Split:** To keep raw transcript updates near real-time, long uninterrupted speech is force-split into segments (default max segment duration: 8 seconds), even if no long silence is detected yet.

**Frame Size Validation:** On first chunk, validates that `len(chunk)` matches a supported Silero VAD frame size for the sample rate (`{512, 1024, 1536}` @ 16 kHz). Logs a warning if mismatched.

**Output:** `SpeechSegment` dataclass:
- `audio: np.ndarray` — concatenated audio of the entire speech segment
- `start_time: float` — seconds from recording start
- `end_time: float` — seconds from recording start

**Concurrency:** `_get_confidence()` runs in a thread executor via `run_in_executor()` to avoid blocking the event loop during ONNX inference.

**`flush()`:** Called when recording stops. If currently in speech, emits the accumulated segment. Otherwise returns `None`.

---

### 3.6 Transcription Engine — `transcription/engine.py`

**Class:** `TranscriptionEngine`

**Responsibility:** Convert speech audio to text using faster-whisper (CTranslate2 backend).

**Model Loading:**
- Lazy initialization via `load_model()` (but typically pre-loaded in `__main__`)
- Creates `WhisperModel(model_size, compute_type=compute_type)`
- Default: `base` model, `int8` compute type

**Transcription:**
- `transcribe(audio, start_time, end_time)` — async wrapper, delegates to executor
- `_transcribe_sync()` — calls `model.transcribe()` with:
  - `beam_size` from config (default 5)
  - `language` from config (default `None` = auto-detect)
  - `vad_filter=False` — VAD is handled externally by `VADProcessor`

**Output:** `TranscriptionResult` dataclass:
- `text: str` — concatenated text from all segments
- `start_time / end_time: float` — passed through from caller
- `language: str | None` — detected language
- `confidence: float` — average of `avg_logprob` across segments

**Concurrency:** The synchronous `_transcribe_sync()` runs in the default thread executor to avoid blocking the asyncio loop.

---

### 3.7 Transcript Cleaner — `transcription/cleaner.py`

**Class:** `TranscriptCleaner`

**Responsibility:** Post-process raw transcription output using an LLM to fix grammar, remove filler words, and improve readability.

**Prompt Template:**
```
Rules:
- Fix grammar and punctuation
- Remove filler words (um, uh, like, you know, etc.)
- Keep the original meaning and speaker intent
- Do not add information that wasn't in the original
- Do not summarize — keep the full content
- Return ONLY the cleaned text, no explanations
```

**Interface:** `clean(raw_text) -> str` — calls `LLMBackend.complete()` with the cleanup prompt. Empty input is returned as-is.
Internally this is passed as structured messages: a single `ChatMessage(role="user", content=prompt)`.

**Retry:** Handled by the caller (`MeetingApp._clean_with_retry()`), not internally.

---

### 3.8 LLM Backend — `llm/`

**Abstract Base:** `LLMBackend(ABC)` — defines two abstract methods:

| Method | Signature | Description |
|--------|-----------|-------------|
| `complete` | `(messages: list[ChatMessage], context="") -> str` | Single-shot completion from structured messages |
| `stream` | `(messages: list[ChatMessage], context="") -> AsyncIterator[str]` | Token-by-token streaming from structured messages |
| `close` | `() -> None` | Optional async resource cleanup hook |

`ChatMessage` is a dataclass with `role` and `content`. Backends also accept optional `context` used as a system/context instruction when supported.

#### 3.8.1 Ollama Backend — `ollama_backend.py`

- **Transport:** `httpx.AsyncClient` with 120s timeout
- **API:** `/api/chat` (Ollama HTTP API)
- **Complete:** `stream=False`, returns `data["message"]["content"]`
- **Stream:** `stream=True`, parses NDJSON lines, yields `message.content`
- **Message format:** Optional system context + full structured conversation history

#### 3.8.2 OpenAI Backend — `openai_backend.py`

- **Transport:** `AsyncOpenAI` client from `openai` SDK
- **Complete:** `chat.completions.create()`, returns `choices[0].message.content`
- **Stream:** `chat.completions.create(stream=True)`, yields `delta.content` chunks
- **Message format:** Optional system context + full structured conversation history

#### 3.8.3 Gemini Backend — `gemini_backend.py`

- **Transport:** `google.genai.Client` from `google-genai` SDK
- **Complete:** `aio.models.generate_content()` with thinking config
- **Stream:** `aio.models.generate_content_stream()`, yields `chunk.text`
- **Thinking Budget:** Maps level string to token budget:
  - `minimal` → 128, `low` → 1024, `medium` → 4096, `high` → 16384
- **Message format:** `list[types.Content]` built from structured history (`assistant` mapped to Gemini `model` role); optional context is prepended as a `user` content item

#### 3.8.4 Backend Factory

`create_llm_backend(config)` in `app.py` — selects and instantiates the backend based on `config.llm.backend`. Uses lazy imports to avoid loading unused SDK dependencies.

---

### 3.9 Chat Manager — `chat/manager.py`

**Class:** `ChatManager`

**Responsibility:** Maintain conversation history, build transcript-aware system context, construct structured message lists, and proxy LLM calls.

**System Prompt Template:**
```
You are a helpful meeting assistant. You have access to the live meeting transcript below.
Answer questions about the meeting based on the transcript. Be concise and specific.
Reference timestamps when relevant. If something wasn't discussed in the transcript, say so.

MEETING TRANSCRIPT:
{transcript}
```

**Transcript Context:**
- Segments stored in `_transcript_segments` as `"[HH:MM:SS] clean text"`
- Added via `add_transcript_segment(timestamp, text)` after each transcription
- Truncation: if estimated tokens (`len // 4`) exceed `max_transcript_tokens` (default 100,000), the oldest content is truncated with a `[...earlier transcript truncated...]` marker

**Chat History:**
- Stored as `list[ChatMessage]` with `role` ("user"/"assistant") and `content`
- Passed directly to backends as structured messages (no flattened role-prefixed text)
- Clearable via `clear_history()` (transcript context preserved)

**Methods:**

| Method | Description |
|--------|-------------|
| `send_message(msg)` | Builds structured messages + transcript context, calls `LLMBackend.complete()` |
| `stream_message(msg)` | Builds structured messages + transcript context, calls `LLMBackend.stream()` |
| `add_transcript_segment(ts, text)` | Append to transcript context |
| `clear_history()` | Clear chat history, keep transcript |

---

### 3.10 Persistence — `persistence/`

#### 3.10.1 Transcript Writer — `transcript_writer.py`

**Class:** `TranscriptWriter`

**Output Format:** Markdown (`.md`)

**File Naming:** `{YYYY-MM-DD_HH-MM-SS}_{title}.md` (e.g., `2026-02-19_14-30-00_meeting.md`)

**File Location:** Configured via `PersistenceConfig.output_dir` (default: `~/meeting-transcripts/`)

**Structure:**
```markdown
# Meeting Transcript — {title}

**Date:** YYYY-MM-DD HH:MM

---

**[HH:MM:SS]** Cleaned transcript text

**[HH:MM:SS]** Next segment...

---

*Transcript ended at HH:MM*
```

**Write Strategy:** Append-only. Header written on first call via `_init_file()`. Each `append(timestamp, text)` opens the file in append mode. `finalize()` adds the footer.

#### 3.10.2 JSON Writer — `json_writer.py`

**Class:** `JSONWriter`

**Output Format:** JSON Lines (`.jsonl`)

**File Naming:** `{YYYY-MM-DD_HH-MM-SS}_{title}.jsonl` (same timestamp pattern as Markdown)

**Structure:** One JSON object per line, each line is a single transcript segment.
```json
{"segment_id":1,"start_time":0.0,"end_time":3.5,"timestamp":"00:00:00","raw_text":"um so like we were discussing","clean_text":"So we were discussing","confidence":-0.35,"language":"en"}
{"segment_id":2,"start_time":4.0,"end_time":8.1,"timestamp":"00:00:04","raw_text":"we should lock budget","clean_text":"We should lock the budget.","confidence":-0.29,"language":"en"}
```

**Write Strategy:** Append-only. Each `add_segment()` writes exactly one JSON line. `flush()` is a public no-op API for caller compatibility because writes are immediate.

**Segment Data:** `TranscriptSegment` dataclass with `segment_id` (auto-incremented), `start_time`, `end_time`, `timestamp`, `raw_text`, `clean_text`, `confidence`, `language`.

#### 3.10.3 Chat History Persistence

On shutdown (`action_quit`), chat history is saved to `{stem}_chat.md` alongside the transcript files. Format:

```markdown
# Chat History — {title}

**You:** question text

**AI:** response text

---

*Chat ended at HH:MM*
```

---

### 3.11 Widgets — `widgets/`

#### 3.11.1 TranscriptPane — `transcript_pane.py`

**Class:** `TranscriptPane(Static)`

**Layout:** Title (`📝 Live Transcript`) + `RichLog` (scrollable, markup-enabled, word-wrapped)

**Methods:**
- `add_raw_segment(timestamp, text)` — dimmed text for immediate raw display
- `add_segment(timestamp, text)` — normal text for cleaned result

**Display Note:** Raw text is shown first (dimmed), then clean text is appended below it when available. Both lines remain visible — the clean version does not replace the raw one.

**Message:** `TranscriptUpdated` — defined but not currently emitted by the pane.

#### 3.11.2 ChatPane — `chat_pane.py`

**Class:** `ChatPane(Static)`

**Layout:** Title (`💬 Chat`) + `RichLog` (message log) + `Input` (docked bottom)

**Message History:** Maintains `_messages: list[str]` (markup) and `_plain_messages: list[str]` (clipboard-friendly text).

**Streaming Protocol:**
1. `begin_assistant_stream()` — initialize `_stream_tokens` accumulator
2. `append_stream_token(token)` — append token and re-render only when either threshold is reached (`8` tokens) or interval elapsed (`50 ms`)
3. `end_assistant_stream()` — store final message, re-render without cursor

**User Input:** `on_input_submitted` clears the input, displays the user message, and posts `ChatSubmitted` message (consumed by `MeetingApp`).

**Clipboard Support:** `get_plain_text()` returns the full plain-text chat history.

**Custom Message:** `ChatSubmitted(text)` — bubbles up to the app for LLM processing.

#### 3.11.3 StatusBar — `status_bar.py`

**Class:** `StatusBar(Static)`

**Reactive Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `recording` | `bool` | Recording active indicator |
| `elapsed_seconds` | `int` | Timer since recording start |
| `word_count` | `int` | Cumulative words transcribed |
| `segment_count` | `int` | Cumulative segments |
| `model_name` | `str` | Active LLM model display name |
| `activity` | `str` | Background activity text (e.g., "AI is thinking...") |
| `audio_level` | `float` | 0.0–1.0 normalized mic level |
| `no_speech_warning` | `bool` | Show ⚠️ indicator |

**Render States:**
- **Activity mode:** `⏳ {activity} │ Model: {model_name}` — when background work is happening
- **Ready mode:** `⏸️  Ready HH:MM:SS │ Words: N │ Segments: N │ Model: name`
- **Recording mode:** `🔴 Recording HH:MM:SS │ 🎤 ████░░░░ │ Words: N │ Segments: N │ Model: name`

**Audio Level Meter:** 8-character bar using `█` (filled) and `░` (empty), scaled from 0.0–1.0. Shows at least one block when signal exists (`> 0.001`).

---

## 4. Concurrency Model

The application uses a single-process, single-event-loop architecture with strategic use of thread executors:

| Component | Thread | Mechanism |
|-----------|--------|-----------|
| Textual UI | Main thread (asyncio) | Event loop |
| PortAudio capture | Dedicated audio thread | `sd.InputStream` callback |
| Queue bridge | Audio → Main | `loop.call_soon_threadsafe()` |
| VAD inference | Thread pool | `run_in_executor()` |
| Whisper inference | Thread pool | `run_in_executor()` |
| LLM API calls | Main thread (async I/O) | `httpx` / SDK async clients |
| Pipeline loop | Textual worker | `run_worker()` capture + VAD only |
| Segment processor | Main event loop task | `asyncio.create_task()` over bounded queue |
| Cleanup processor | Main event loop task | `asyncio.create_task()` over bounded queue |
| Timer | Textual interval | `set_interval(1.0)` |

**Worker Usage:** The pipeline loop runs inside a Textual `run_worker(exclusive=True)` — meaning only one startup worker can exist at a time.

---

## 5. Error Handling Strategy

| Scenario | Handling |
|----------|---------|
| Model load failure | Notification + status reset, recording does not start |
| Mic start failure | Notification referencing `--list-devices`, recording does not start |
| Mic disconnection mid-recording | 3 recovery attempts with increasing delays, then stop recording |
| Audio queue timeout | `continue` (re-check `_recording` flag) |
| VAD processing error | Log + notification, skip chunk |
| Transcription error | Log + notification, skip segment |
| LLM cleanup failure | 3 retries with exponential backoff, fallback to raw text |
| Chat LLM failure | 3 retries with exponential backoff, display error message |
| Empty transcription | Silently skip (no display, no persist) |
| 15s silence | One-time warning distinguishing no-signal vs. no-speech |
| SIGINT / SIGTERM | Graceful shutdown via `action_quit()` |

---

## 6. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `textual` | ≥ 3.0 | TUI framework |
| `sounddevice` | ≥ 0.5 | PortAudio microphone capture |
| `numpy` | ≥ 1.26 | Audio array manipulation |
| `faster-whisper` | ≥ 1.1 | Speech-to-text (CTranslate2) |
| `onnxruntime` | ≥ 1.17 | ONNX model inference for VAD |
| `silero-vad` | ≥ 5.1 | VAD ONNX model weights |
| `httpx` | ≥ 0.27 | Async HTTP client (Ollama) |
| `openai` | ≥ 1.50 | OpenAI API client |
| `google-genai` | ≥ 1.0 | Gemini API client |
| `rich` | ≥ 13.0 | Terminal markup rendering |
| `click` | ≥ 8.1 | CLI argument parsing |
| `python-dotenv` | ≥ 1.0 | `.env` file loading |

**Dev Dependencies:** `pytest` ≥ 8.0, `pytest-asyncio` ≥ 0.23

---

## 7. File Output

### 7.1 Output File Naming

Pattern: `{YYYY-MM-DD}_{HH-MM-SS}_{title}.{ext}`

For a meeting titled "meeting" started at 2026-02-19 14:30:00:

| File | Path |
|------|------|
| Markdown transcript | `~/meeting-transcripts/2026-02-19_14-30-00_meeting.md` |
| JSON transcript | `~/meeting-transcripts/2026-02-19_14-30-00_meeting.jsonl` |
| Chat history | `~/meeting-transcripts/2026-02-19_14-30-00_meeting_chat.md` |

The timestamp is captured at writer construction time (during `on_mount()`), not at recording start. This means the timestamp reflects app launch time.

### 7.2 Output Directory

Default: `~/meeting-transcripts/`  
Created automatically if it does not exist (`mkdir(parents=True, exist_ok=True)`).

---

## 8. Known Constraints & Design Decisions

1. **Pre-loading models is mandatory on Python 3.13+** due to CTranslate2 file descriptor race. The fallback in-app loader exists but is unreliable.

2. **No speaker diarization** — speaker labels are manually set via `Ctrl+S` and apply to all subsequent segments until changed or cleared.

3. **Transcript pane shows both raw and clean text** — the clean version does not replace the raw. Over long sessions this doubles the display volume.

4. **JSON writer is append-only JSONL** with immediate writes. This avoids whole-file rewrites and supports long sessions efficiently.

5. **Transcript context in chat** uses a rough token estimate (4 chars/token). With `max_transcript_tokens=100,000`, this allows ~400 KB of transcript text before truncation from the beginning.

6. **Chat streaming still re-renders history** because `RichLog` lacks in-place line updates, but updates are throttled/batched (every 8 tokens or 50 ms) to reduce render pressure.

7. **VAD-internal `block_duration_ms` must match** a valid Silero frame size. At 16 kHz, valid values are 32 ms (512 samples), 64 ms (1024), or 96 ms (1536). Mismatches produce unreliable detection with a logged warning.

8. **System bell is disabled** globally via `bell()` override to prevent audible notifications in terminal.

9. **Gemini context** is prepended as a `user` content item because the `google-genai` contents API expects explicit role-tagged message parts rather than OpenAI-style system fields.
