"""Chat input/output widget for querying meeting context."""

from __future__ import annotations

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
        self._stream_tokens: list[str] = []

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

    def _write_message(self, markup: str) -> None:
        """Write a message and track it in history."""
        self._messages.append(markup)
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
        self._write_message(f"[bold green]You:[/bold green] {text}")

    def add_assistant_message(self, text: str) -> None:
        """Display a complete assistant message."""
        self._write_message(f"[bold blue]AI:[/bold blue] {text}")

    def begin_assistant_stream(self) -> None:
        """Begin streaming an assistant response."""
        self._stream_tokens = []

    def append_stream_token(self, token: str) -> None:
        """Accumulate a token and live-update the display."""
        self._stream_tokens.append(token)
        accumulated = "".join(self._stream_tokens)
        self._rewrite_all(f"[bold blue]AI:[/bold blue] {accumulated}▍")

    def end_assistant_stream(self) -> None:
        """Finish the streaming response — write final message."""
        accumulated = "".join(self._stream_tokens)
        self._stream_tokens = []
        self._write_message(f"[bold blue]AI:[/bold blue] {accumulated}")
        # Re-render cleanly without the cursor
        self._rewrite_all()
