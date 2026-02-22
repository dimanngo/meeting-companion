"""Chat input/output widget for querying meeting context."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static, RichLog, Input


class ChatSubmitted(Message):
    """Message sent when user submits a chat message."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class ChatPane(Static):
    """Chat pane with message history and input field."""

    _STREAM_UPDATE_INTERVAL_SEC = 0.05
    _STREAM_UPDATE_TOKEN_BATCH = 8

    DEFAULT_CSS = """
    ChatPane {
        height: 1fr;
        border: solid $secondary;
        padding: 1;
    }
    ChatPane #chat-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    ChatPane RichLog {
        height: 1fr;
        margin-bottom: 1;
    }
    ChatPane Input {
        dock: bottom;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._messages: list[str] = []  # Rendered message history
        self._plain_messages: list[str] = []
        self._stream_tokens: list[str] = []
        self._stream_tokens_since_render = 0
        self._last_stream_render_ts = 0.0

    def compose(self) -> ComposeResult:
        yield Static("💬 Chat", id="chat-title")
        yield RichLog(highlight=True, markup=True, wrap=True, id="chat-log")
        yield Input(placeholder="Ask about the meeting...", id="chat-input")

    @property
    def log_widget(self) -> RichLog:
        return self.query_one("#chat-log", RichLog)

    @property
    def input_widget(self) -> Input:
        return self.query_one("#chat-input", Input)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user pressing Enter in the chat input."""
        text = event.value.strip()
        if not text:
            return
        self.input_widget.value = ""
        self.add_user_message(text)
        self.post_message(ChatSubmitted(text))

    def _write_message(self, markup: str, plain: str | None = None) -> None:
        """Write a message and track it in history."""
        self._messages.append(markup)
        if plain is not None:
            self._plain_messages.append(plain)
        self.log_widget.write(markup)

    def _rewrite_all(self, extra: str | None = None) -> None:
        """Clear the log and re-render all tracked messages plus optional extra."""
        self.log_widget.clear()
        for msg in self._messages:
            self.log_widget.write(msg)
        if extra:
            self.log_widget.write(extra)

    def add_user_message(self, text: str) -> None:
        """Display a user message in the chat log."""
        self._write_message(f"[bold green]You:[/bold green] {text}", f"You: {text}")

    def add_assistant_message(self, text: str) -> None:
        """Display a complete assistant message."""
        self._write_message(f"[bold blue]AI:[/bold blue] {text}", f"AI: {text}")

    def begin_assistant_stream(self) -> None:
        """Begin streaming an assistant response."""
        self._stream_tokens = []
        self._stream_tokens_since_render = 0
        self._last_stream_render_ts = 0.0

    def _render_stream_cursor(self) -> None:
        """Render the current streaming assistant text with a cursor."""
        accumulated = "".join(self._stream_tokens)
        self._rewrite_all(f"[bold blue]AI:[/bold blue] {accumulated}▍")
        self._stream_tokens_since_render = 0
        self._last_stream_render_ts = time.monotonic()

    def append_stream_token(self, token: str) -> None:
        """Accumulate a token and live-update the display."""
        self._stream_tokens.append(token)
        self._stream_tokens_since_render += 1
        now = time.monotonic()
        should_render = (
            self._stream_tokens_since_render >= self._STREAM_UPDATE_TOKEN_BATCH
            or (now - self._last_stream_render_ts) >= self._STREAM_UPDATE_INTERVAL_SEC
        )
        if should_render:
            self._render_stream_cursor()

    def end_assistant_stream(self) -> None:
        """Finish the streaming response — write final message."""
        if self._stream_tokens_since_render > 0:
            self._render_stream_cursor()
        accumulated = "".join(self._stream_tokens)
        self._stream_tokens = []
        self._stream_tokens_since_render = 0
        self._write_message(
            f"[bold blue]AI:[/bold blue] {accumulated}",
            f"AI: {accumulated}",
        )
        # Re-render cleanly without the cursor
        self._rewrite_all()

    def get_plain_text(self) -> str:
        """Return chat history as plain text."""
        return "\n".join(self._plain_messages)
