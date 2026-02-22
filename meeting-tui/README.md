# Meeting TUI

A terminal-based meeting companion with live transcription and AI chat — all within your terminal.

```
┌─────────────────────────────────────────────────────────┐
│                    Meeting TUI                           │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │  📝 Live Transcript   │  │  💬 Chat                 │ │
│  │                       │  │                          │ │
│  │  [00:01:23] We need   │  │  You: What was decided   │ │
│  │  to finalize the Q2   │  │       about the budget?  │ │
│  │  budget by Friday...  │  │                          │ │
│  │                       │  │  AI: Based on the        │ │
│  │  [00:02:05] I think   │  │      discussion at       │ │
│  │  we should allocate   │  │      00:01:23, the team  │ │
│  │  more to marketing.   │  │      needs to finalize   │ │
│  │                       │  │      the Q2 budget by    │ │
│  │                       │  │      Friday.             │ │
│  └──────────────────────┘  └──────────────────────────┘ │
│  🔴 Recording 00:02:05 │ 🎤 █████░░░ │ Words: 342 │ Segments: 12  │
└─────────────────────────────────────────────────────────┘
```

## Features

- **Live Transcription** — Captures microphone audio, detects speech with Silero VAD, and transcribes in real-time using faster-whisper
- **LLM Transcript Cleanup** — Automatically cleans up raw transcription (fixes grammar, removes filler words)
- **Interactive Chat** — Query the meeting context with AI — ask questions, request summaries, find action items
- **Multiple LLM Backends** — Ollama (local/private), OpenAI, or Google Gemini
- **Auto-save** — Markdown transcript + JSONL sidecar with timestamps, confidence scores, and raw/clean text pairs
- **Rich TUI** — Split-pane interface with live transcript, chat, and status bar with real-time audio level meter
- **Audio Diagnostics** — Live microphone level indicator and automatic warnings when no speech is detected

---

## Quick Start

### 1. Install Prerequisites

**Python 3.11+** is required.

**PortAudio** (audio capture library):

```bash
# macOS
brew install portaudio

# Ubuntu / Debian
sudo apt install portaudio19-dev

# Fedora
sudo dnf install portaudio-devel
```

**An LLM backend** (pick one):

| Backend | Setup | Best for |
|---|---|---|
| [Ollama](https://ollama.ai/) (default) | `brew install ollama && ollama pull mistral` | Privacy, offline use, no API costs |
| [OpenAI](https://platform.openai.com/) | Get API key → set `OPENAI_API_KEY` | High quality, easy setup |
| [Google Gemini](https://ai.google.dev/) | Get API key → set `GEMINI_API_KEY` | 1M token context, best price/performance |

### 2. Install Meeting TUI

```bash
cd meeting-tui

# Using uv (recommended — https://github.com/astral-sh/uv)
uv sync

# Or using pip
pip install -e .
```

### 3. Run It

```bash
# With uv
uv run meeting-tui

# Or if installed via pip
meeting-tui
```

On first launch, the app downloads and loads ML models (~144 MB total for the default `base` model).
You'll see progress in the terminal:

```
Loading VAD model...
Loading Whisper 'base' model...
Models loaded. Starting app...
```

Once the TUI appears, press **Ctrl+R** to start recording — it begins instantly since models are pre-loaded.

---

## User Guide

### Starting a Meeting

1. **Launch the app:**

   ```bash
   uv run meeting-tui --title "Sprint Planning"
   ```

2. **Select your microphone** (if not using the default):

   ```bash
   # List available devices
   uv run meeting-tui --list-devices

   # Output:
   #   [0] DG Microphone (channels: 1)
   #   [1] MacBook Air Microphone (channels: 1) *
   #   [3] Microsoft Teams Audio (channels: 1)
   #   ...
   #   * = default device

   # Use a specific device by index or name (partial match)
   uv run meeting-tui --device 0
   uv run meeting-tui --device "MacBook"
   ```

3. **Press `Ctrl+R`** to start recording. The status bar shows `🔴 Recording` with a running timer and a live audio level meter (`🎤 ████░░░░`).

4. **Speak normally.** The left pane shows live transcription as you talk. Each segment is automatically cleaned up by the LLM (grammar fixes, filler word removal).

### Chatting with Your Meeting

While the meeting is running (or after stopping), use the **Chat** pane on the right:

1. **Press `Ctrl+L`** to switch focus to the chat input (or click on it).
2. **Type a question** and press **Enter**. Examples:

   - `What has been discussed so far?`
   - `Summarize the key decisions.`
   - `What action items were mentioned?`
   - `What did the team say about the budget?`

3. The AI responds based on the full meeting transcript with timestamp references.

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+R` | Start / stop recording |
| `Ctrl+E` | Export — save transcript now (also auto-saves continuously) |
| `Ctrl+L` | Switch focus between transcript pane and chat input |
| `Ctrl+T` | Copy transcript pane to clipboard |
| `Ctrl+Y` | Copy chat pane to clipboard |
| `Ctrl+Shift+Left` | Widen transcript pane |
| `Ctrl+Shift+Right` | Widen chat pane |
| `Option+Shift+Left` | Widen transcript pane (fallback for terminals where Ctrl+Shift+Arrow is reserved) |
| `Option+Shift+Right` | Widen chat pane (fallback for terminals where Ctrl+Shift+Arrow is reserved) |
| `Ctrl+S` | Set speaker label — tags subsequent transcript segments with a name |
| `Tab` | Cycle focus across all UI elements |
| `Ctrl+Q` | Quit (gracefully saves transcript and chat history) |

### Stopping and Saving

- **Press `Ctrl+R`** to pause/stop recording. You can resume with `Ctrl+R` again.
- **Press `Ctrl+Q`** to quit. The transcript is finalized and saved automatically.
- Transcripts are saved **continuously** as new segments arrive — you won't lose data on a crash.

---

## CLI Reference

```
Usage: meeting-tui [OPTIONS]

Options:
  --device TEXT                    Audio input device index or name
  --model [tiny|base|small|medium|large-v3]
                                   Whisper model size for transcription
  --output PATH                    Output directory for transcripts
  --llm-backend [ollama|openai|gemini]
                                   LLM backend to use
  --title TEXT                     Meeting title for transcript files
  --list-devices                   List available audio input devices and exit
  --config PATH                    Path to config file
  --help                           Show this message and exit
```

**Examples:**

```bash
# Quick start with all defaults
uv run meeting-tui

# High-accuracy transcription with Gemini chat
uv run meeting-tui --model small --llm-backend gemini --title "Board Meeting"

# Save to a specific directory
uv run meeting-tui --output ~/Documents/meetings --title "1-on-1"

# Use a specific mic with the smallest/fastest model
uv run meeting-tui --device 0 --model tiny
```

### Whisper Model Sizes

Choose based on your hardware and accuracy needs:

| Model | Download | Speed | Quality | Recommended for |
|---|---|---|---|---|
| `tiny` | 75 MB | Fastest | Acceptable | Testing, low-resource machines |
| `base` | 142 MB | Fast | Good | **Default — good real-time balance** |
| `small` | 466 MB | Moderate | Very good | Better accuracy when you can afford it |
| `medium` | 1.5 GB | Slow | Excellent | When accuracy is the priority |
| `large-v3` | 3.1 GB | Slowest | Best | Post-meeting reprocessing |

The model is downloaded automatically on first use.

---

## Configuration

Settings are loaded with this precedence: **CLI flags > environment variables > config file > defaults**.

### Config File

Create `~/.config/meeting-tui/config.toml` to set persistent defaults:

```toml
[audio]
device = 0              # Audio device index (run --list-devices to find yours)
sample_rate = 16000     # 16kHz is optimal for speech recognition
block_duration_ms = 32  # Audio block size — must produce a supported Silero VAD frame size (512/1024/1536 @ 16kHz)

[vad]
threshold = 0.5         # Speech detection sensitivity (0.0–1.0, lower = more sensitive)
min_speech_frames = 6   # Frames above threshold to start a segment (~180ms)
min_silence_frames = 30 # Frames below threshold to end a segment (~900ms)

[transcription]
model_size = "base"     # tiny, base, small, medium, large-v3
compute_type = "int8"   # int8 is fastest on CPU; use float16 for GPU
beam_size = 5           # Higher = more accurate but slower

[llm]
backend = "ollama"                          # ollama, openai, or gemini
ollama_base_url = "http://localhost:11434"
ollama_model = "mistral"                    # Any model you've pulled in Ollama

[persistence]
output_dir = "~/meeting-transcripts"
title = "meeting"                           # Default title (override with --title)
```

### Environment Variables

Set API keys and overrides via environment variables (or a `.env` file):

```bash
# LLM backend selection
MEETING_TUI_LLM_BACKEND=ollama         # ollama, openai, or gemini

# Ollama
MEETING_TUI_OLLAMA_BASE_URL=http://localhost:11434
MEETING_TUI_OLLAMA_MODEL=mistral

# OpenAI
OPENAI_API_KEY=sk-...

# Google Gemini
GEMINI_API_KEY=...
MEETING_TUI_GEMINI_MODEL=gemini-2.5-flash-preview

# Transcription
MEETING_TUI_WHISPER_MODEL=base

# Audio
MEETING_TUI_AUDIO_DEVICE=0

# Output
MEETING_TUI_OUTPUT_DIR=~/meeting-transcripts
```

### LLM Backend Setup

#### Ollama (local, default)

```bash
# Install Ollama
brew install ollama      # macOS
# or: curl -fsSL https://ollama.ai/install.sh | sh   # Linux

# Start the server
ollama serve

# Pull a model (in another terminal)
ollama pull mistral      # 4.1 GB — good default
# or: ollama pull phi3:mini    # 2.3 GB — faster, lighter
# or: ollama pull llama3.1:8b  # 4.7 GB — latest quality

# Run meeting-tui (uses Ollama by default)
uv run meeting-tui
```

#### OpenAI

```bash
export OPENAI_API_KEY="sk-..."
uv run meeting-tui --llm-backend openai
```

#### Google Gemini

```bash
export GEMINI_API_KEY="..."
uv run meeting-tui --llm-backend gemini
```

Gemini 3 Flash offers the best price/performance with a 1M token context window — long meetings fit entirely without truncation.

---

## Output Files

Transcripts are saved to `~/meeting-transcripts/` (configurable via `--output` or config):

```
~/meeting-transcripts/
├── 2026-02-18_sprint-planning.md       # Clean, human-readable Markdown
├── 2026-02-18_sprint-planning.jsonl    # Structured data (one JSON object per segment)
```

### Markdown Transcript (`*.md`)

```markdown
# Meeting Transcript — Sprint Planning

**Date:** 2026-02-18 14:00

---

**[00:01:23]** We need to finalize the Q2 budget by Friday.

**[00:02:05]** I think we should allocate more to marketing this quarter.

---

*Transcript ended at 15:30*
```

### JSONL Sidecar (`*.jsonl`)

```json
{"segment_id":1,"start_time":83.2,"end_time":87.5,"timestamp":"00:01:23","raw_text":"We, uh, need to finalize the the Q2 budget by Friday.","clean_text":"We need to finalize the Q2 budget by Friday.","confidence":-0.35,"language":"en"}
{"segment_id":2,"start_time":92.1,"end_time":96.7,"timestamp":"00:01:32","raw_text":"I think we should allocate more to marketing.","clean_text":"I think we should allocate more to marketing.","confidence":-0.31,"language":"en"}
```

The JSONL file enables programmatic access for search, analytics, or re-processing while keeping writes append-only and efficient for long meetings.

---

## Architecture

```
┌─────────────┐     ┌───────────┐     ┌──────────────┐     ┌─────────────┐
│  Microphone  │────▶│  Silero   │────▶│ faster-whisper│────▶│ LLM Cleanup │
│ (sounddevice)│     │   VAD     │     │ transcription │     │  (Ollama/   │
└─────────────┘     └───────────┘     └──────────────┘     │  Gemini/    │
                     speech segments   raw text             │  OpenAI)    │
                                                           └──────┬──────┘
                                                                  │ clean text
                                          ┌───────────────────────┼──────────┐
                                          ▼                       ▼          ▼
                                   ┌────────────┐        ┌──────────┐ ┌──────────┐
                                   │  Textual    │        │   .md    │ │  .jsonl  │
                                   │  TUI App    │        │ writer   │ │ writer   │
                                   │ (transcript │        └──────────┘ └──────────┘
                                   │  + chat)    │
                                   └─────┬──────┘
                                         │ user question
                                         ▼
                                   ┌────────────┐
                                   │ Chat Manager│──▶ LLM (with full transcript as context)
                                   └────────────┘
```

## Troubleshooting

| Problem | Solution |
|---|---|
| `No module named 'sounddevice'` | Install PortAudio: `brew install portaudio` (macOS) |
| No audio devices listed | Check microphone permissions in System Settings → Privacy → Microphone |
| Audio level meter is flat | Check microphone permissions, or select correct device with `--device` |
| `Audio queue full; dropped oldest chunk` in logs | Transcription is temporarily slower than incoming audio; app keeps real-time behavior by dropping oldest buffered chunks |
| "No speech detected" warning | Audio is arriving but VAD isn't triggering — speak louder or lower `vad.threshold` in config |
| Ollama connection refused | Start the server: `ollama serve` |
| Transcription is slow | Use a smaller model: `--model tiny` or `--model base` |
| Poor transcription quality | Use a larger model: `--model small` or `--model medium` |
| High memory usage | Ollama models use 4–8 GB RAM. Use `phi3:mini` (2.3 GB) for less memory |
| Mic disconnected mid-meeting | The app auto-retries 3 times with backoff. If recovery fails, press `Ctrl+R` to restart |
| LLM errors / timeouts | Requests are retried 3 times with exponential backoff. Raw text is used if cleanup fails |
| Slow startup on first run | First launch downloads Whisper model (~142 MB for `base`). Subsequent starts use the cache and load in ~6s |

Meeting TUI uses Textual, which renders the interface to `stderr`. If you run `uv run meeting-tui 2> meeting-tui.log`, the UI is redirected into the file and won't be visible in your terminal.

For normal interactive use, run without stderr redirection:

```bash
uv run meeting-tui
```

Meeting TUI now writes application logs to a dedicated file:

- `~/meeting-transcripts/meeting-tui.log` by default
- If you use `--output`, logs go to `<output-dir>/meeting-tui.log`
- Size-based rotation is enabled by default (5 MB per file, 3 backups)

You can follow logs in real time without affecting the UI:

```bash
tail -f ~/meeting-transcripts/meeting-tui.log
```

Optional log rotation controls:

```bash
# Defaults
MEETING_TUI_LOG_MAX_BYTES=5242880
MEETING_TUI_LOG_BACKUP_COUNT=3

# Disable rotation (single growing file)
MEETING_TUI_LOG_MAX_BYTES=0
```

---

## Development & Testing

### Setup

```bash
cd meeting-tui

# Install all dependencies including dev tools
uv sync --extra dev
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_audio_capture.py
uv run pytest tests/test_transcription.py
uv run pytest tests/test_llm_backends.py
uv run pytest tests/test_chat_manager.py
uv run pytest tests/test_integration.py

# Run a specific test class or method
uv run pytest tests/test_audio_capture.py::TestVADProcessor
uv run pytest tests/test_chat_manager.py::TestChatManager::test_send_message
```

### Test Suite Overview

| Test File | Tests | What It Covers |
|---|---|---|
| `test_audio_capture.py` | 15 | AudioCapture (mock sounddevice), VAD state machine |
| `test_transcription.py` | 9 | Transcription engine (mock model), LLM cleaner (mock LLM) |
| `test_llm_backends.py` | 11 | Ollama, OpenAI, Gemini backends (mock HTTP) |
| `test_chat_manager.py` | 11 | Context assembly, truncation, history management |
| `test_integration.py` | 2 | Full pipeline: audio → transcribe → clean → save → chat |
| **Total** | **48** | |

All tests use mocks — no microphone, GPU, or API keys required to run the test suite.

## License

MIT
