# Meeting TUI

A terminal-based meeting companion with live transcription and AI chat — all within your terminal.

## Features

- **Live Transcription** — Captures microphone audio, detects speech with Silero VAD, and transcribes in real-time using faster-whisper
- **LLM Transcript Cleanup** — Automatically cleans up raw transcription (fixes grammar, removes filler words)
- **Interactive Chat** — Query the meeting context with AI (ask questions, get summaries, find action items)
- **Multiple LLM Backends** — Ollama (local), OpenAI, or Google Gemini
- **Auto-save** — Markdown transcript + JSON sidecar with timestamps, confidence scores, and raw/clean text pairs
- **Rich TUI** — Split-pane interface with live transcript, chat, and status bar

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- PortAudio (for audio capture)
  - macOS: `brew install portaudio`
  - Ubuntu/Debian: `sudo apt install portaudio19-dev`
- For local LLM: [Ollama](https://ollama.ai/) with a model pulled (e.g., `ollama pull mistral`)

## Installation

```bash
# Clone the repository
cd meeting-tui

# Using uv (recommended)
uv sync
uv run meeting-tui

# Or using pip
pip install -e .
meeting-tui
```

## Usage

```bash
# Start with defaults (Ollama backend, base Whisper model)
meeting-tui

# List available audio devices
meeting-tui --list-devices

# Use a specific audio device
meeting-tui --device 2

# Use a larger Whisper model for better accuracy
meeting-tui --model small

# Use Gemini as LLM backend
meeting-tui --llm-backend gemini

# Set meeting title and output directory
meeting-tui --title "Sprint Planning" --output ./transcripts

# Use a custom config file
meeting-tui --config /path/to/config.toml
```

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+R` | Start/Stop recording |
| `Ctrl+E` | Export/save transcript |
| `Ctrl+L` | Switch focus between transcript and chat |
| `Tab` | Cycle focus |
| `Ctrl+Q` | Quit |

## Configuration

Settings are loaded with precedence: **CLI flags > environment variables > config file > defaults**.

### Config File

Create `~/.config/meeting-tui/config.toml`:

```toml
[audio]
device = 0          # Audio device index
sample_rate = 16000
block_duration_ms = 30

[vad]
threshold = 0.5
min_speech_frames = 6
min_silence_frames = 30

[transcription]
model_size = "base"     # tiny, base, small, medium, large-v3
compute_type = "int8"
beam_size = 5

[llm]
backend = "ollama"      # ollama, openai, gemini
ollama_base_url = "http://localhost:11434"
ollama_model = "mistral"
# openai_api_key = "sk-..."    # Or use OPENAI_API_KEY env var
# gemini_api_key = "..."       # Or use GEMINI_API_KEY env var
# gemini_model = "gemini-2.5-flash-preview"

[persistence]
output_dir = "~/meeting-transcripts"
title = "meeting"
```

### Environment Variables

See `.env.example` for all available environment variables. API keys should be set via environment variables rather than the config file.

## Output

Transcripts are saved to `~/meeting-transcripts/` (configurable):

```
~/meeting-transcripts/
├── 2026-02-18_meeting.md       # Clean Markdown transcript
├── 2026-02-18_meeting.json     # Structured JSON sidecar
```

## Architecture

```
Audio → VAD → Transcription → LLM Cleanup → Display + Save
                                    ↓
                              Chat Context → LLM Chat → Display
```

## License

MIT
