# Contributing to meeting-companion

Thank you for your interest in contributing! This is a solo-maintained project and contributions are welcome within the scope below.

## Before You Open a Pull Request

> [!IMPORTANT]
> **Please open an issue first** before starting work on significant changes or new features.
> As a solo maintainer, I cannot guarantee I'll review or merge large unsolicited PRs that don't align with the project direction. A brief issue discussion saves everyone time.

Small fixes (typos, documentation, minor bugs) can go straight to a PR.

## Dev Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for environment and dependency management.

```bash
git clone https://github.com/dimanngo/meeting-companion.git
cd meeting-companion/meeting-tui

# Install all dependencies including dev tools
uv sync --extra dev
```

You'll also need:
- **macOS**: `brew install portaudio`
- **Linux**: `sudo apt-get install portaudio19-dev`

Copy `.env.example` to `.env` and fill in your API keys.

## Running Tests

```bash
cd meeting-tui
uv run pytest --cov=meeting_tui --cov-report=term-missing
```

## Code Style

This project uses `ruff` for linting and formatting, and `mypy` for type checking.

```bash
# Lint
uv run ruff check src/

# Auto-fix lint issues
uv run ruff check --fix src/

# Format
uv run ruff format src/

# Type check
uv run mypy src/
```

All CI checks must pass before a PR is merged.

## Commit Style

This project follows [Conventional Commits](https://www.conventionalcommits.org/). PR titles must match the format:

```
<type>: <short description>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

Examples:
- `feat: add summary export to markdown`
- `fix: handle empty transcript on session end`
- `docs: update quick start for Linux`

> [!NOTE]
> The repo is configured for **squash merges only**. Your PR title becomes the commit on `main` and feeds directly into the automated changelog and release pipeline.

## Release Process

Releases are fully automated via `release-please`. You don't need to do anything special — once changes land on `main`, the release bot will propose the changelog and version bump.

```
PR opened
  → PR title validated (Conventional Commits: feat/fix/docs/refactor/...)
  → CI: ruff lint + ruff format + mypy + pytest (Ubuntu & macOS)

PR merged to main (squash — title becomes the commit)
  → release-please updates its rolling Release PR (adds CHANGELOG entry)

Release PR merged
  → release-please creates GitHub Release + tag
  → publish.yml fires: uv build → PyPI (OIDC) + Homebrew bump
```
