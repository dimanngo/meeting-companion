# Meeting Companion

```text
  __  __           _   _             
 |  \/  | ___  ___| |_(_)_ __   __ _ 
 | |\/| |/ _ \/ _ \ __| | '_ \ / _` |
 | |  | |  __/  __/ |_| | | | | (_| |
 |_|  |_|\___|\___|\__|_|_| |_|\__, |
                               |___/ 
   ____                                  _             
  / ___|___  _ __ ___  _ __   __ _ _ __ (_) ___  _ __  
 | |   / _ \| '_ ` _ \| '_ \ / _` | '_ \| |/ _ \| '_ \ 
 | |__| (_) | | | | | | |_) | (_| | | | | | (_) | | | |
  \____\___/|_| |_| |_| .__/ \__,_|_| |_|_|\___/|_| |_|
                      |_|
```

[![CI](https://github.com/dimanngo/meeting-companion/actions/workflows/ci.yml/badge.svg)](https://github.com/dimanngo/meeting-companion/actions/workflows/ci.yml)

A portfolio repository for building AI-assisted meeting tools, with a production-ready terminal app in the `meeting-tui` subproject.

## Flagship Project

- **Meeting TUI** — real-time terminal meeting companion with live transcription, transcript cleanup, and contextual AI chat.
- Project docs and usage: [meeting-tui/README.md](meeting-tui/README.md)

## Why this project

Building real AI tools in the terminal. Shows streaming transcription, smart text cleanup, and multi-LLM support.

**Key capabilities:**

- low-latency audio ingestion and speech segmentation
- streaming transcription with post-processing cleanup
- multi-backend LLM integration (local and cloud)
- resilient async pipeline design and recovery logic

## Repository Structure

- [meeting-tui](meeting-tui) — runnable Python application (primary deliverable)
- Top-level planning artifacts (`Idea.md`, `Comparison.md`, etc.) — product/architecture history

## Quick Start (Meeting TUI)

```bash
# macOS (Recommended)
brew tap dimanngo/tools
brew install meeting-tui

# Linux / Python Users (requires PortAudio)
pipx install meeting-tui
```

For full setup requirements (PortAudio for non-macOS users, API keys, backend selection), see [meeting-tui/README.md](meeting-tui/README.md).

## Supported Platforms

- CI-verified: macOS and Linux
- CI Python matrix: minimal supported version

## License

MIT — see [LICENSE](LICENSE).
