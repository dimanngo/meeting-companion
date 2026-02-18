"""Entry point for meeting-tui — CLI interface using Click."""

from __future__ import annotations

import click
import sounddevice as sd

from meeting_tui.config import load_config


@click.command()
@click.option("--device", type=str, default=None, help="Audio input device index or name")
@click.option(
    "--model",
    type=click.Choice(["tiny", "base", "small", "medium", "large-v3"]),
    default=None,
    help="Whisper model size for transcription",
)
@click.option("--output", type=click.Path(), default=None, help="Output directory for transcripts")
@click.option(
    "--llm-backend",
    type=click.Choice(["ollama", "openai", "gemini"]),
    default=None,
    help="LLM backend to use",
)
@click.option("--title", type=str, default=None, help="Meeting title for transcript files")
@click.option("--list-devices", is_flag=True, help="List available audio input devices and exit")
@click.option("--config", "config_path", type=click.Path(), default=None, help="Path to config file")
def main(
    device: str | None,
    model: str | None,
    output: str | None,
    llm_backend: str | None,
    title: str | None,
    list_devices: bool,
    config_path: str | None,
) -> None:
    """Meeting TUI — Live meeting transcription and AI chat in your terminal."""
    if list_devices:
        _print_devices()
        return

    # Build CLI overrides dict
    cli_overrides: dict = {}
    if device is not None:
        try:
            cli_overrides.setdefault("audio", {})["device"] = int(device)
        except ValueError:
            # Partial name match — find the device index by name substring
            resolved = _resolve_device_by_name(device)
            if resolved is not None:
                cli_overrides.setdefault("audio", {})["device"] = resolved
            else:
                click.echo(f"Error: No audio input device matching '{device}'. Use --list-devices.")
                raise SystemExit(1)
    if model is not None:
        cli_overrides.setdefault("transcription", {})["model_size"] = model
    if output is not None:
        cli_overrides.setdefault("persistence", {})["output_dir"] = output
    if llm_backend is not None:
        cli_overrides.setdefault("llm", {})["backend"] = llm_backend
    if title is not None:
        cli_overrides.setdefault("persistence", {})["title"] = title

    from pathlib import Path

    config = load_config(
        config_path=Path(config_path) if config_path else None,
        cli_overrides=cli_overrides if cli_overrides else None,
    )

    from meeting_tui.app import MeetingApp

    app = MeetingApp(config)
    app.run()


def _resolve_device_by_name(name: str) -> int | None:
    """Resolve a device name (partial, case-insensitive) to a device index."""
    devices = sd.query_devices()
    name_lower = name.lower()
    matches = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and name_lower in dev["name"].lower():
            matches.append(i)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        click.echo(f"Ambiguous device name '{name}'. Matches:")
        for i in matches:
            click.echo(f"  [{i}] {devices[i]['name']}")
        return None
    return None


def _print_devices() -> None:
    """Print available audio input devices."""
    devices = sd.query_devices()
    click.echo("Available audio input devices:\n")
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            marker = " *" if i == sd.default.device[0] else ""
            click.echo(f"  [{i}] {dev['name']} (channels: {dev['max_input_channels']}){marker}")
    click.echo("\n  * = default device")
    click.echo("\nUse --device <index> to select a device.")


if __name__ == "__main__":
    main()
