# Meeting Companion

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
cd meeting-tui
uv sync
uv run meeting-tui
```

For full setup requirements (PortAudio, API keys, backend selection), see [meeting-tui/README.md](meeting-tui/README.md).

## Supported Platforms

- CI-verified: macOS and Linux
- CI Python matrix: minimal supported version

## License

MIT — see [LICENSE](LICENSE).
