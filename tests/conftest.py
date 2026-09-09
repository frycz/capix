"""Shared fakes.

Nothing here touches the network: every test swaps in a fake Anthropic client
and inspects the parameters the wrapper would have sent.
"""

from __future__ import annotations

import pytest

import capix.client as client_mod


class FakeBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class FakeMessage:
    def __init__(self, text: str = "hi", stop_reason: str = "end_turn") -> None:
        self.content = [FakeBlock(text)]
        self.stop_reason = stop_reason
        self.stop_details = None


class FakeStream:
    def __init__(self, message: FakeMessage, chunks: list[str]) -> None:
        self._message = message
        self.text_stream = iter(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class FakeClient:
    """Records the params of the last stream() call."""

    def __init__(self, message: FakeMessage, chunks: list[str]) -> None:
        self.message = message
        self.chunks = chunks
        self.params: dict = {}
        self.beta = self  # beta.messages.stream(...) all resolves back here
        self.messages = self

    def stream(self, **params):
        self.params = params
        return FakeStream(self.message, self.chunks)


@pytest.fixture
def fake_client(monkeypatch):
    """Install a FakeClient and hand it back for assertions."""

    def install(text: str = "hi", stop_reason: str = "end_turn", chunks=None):
        message = FakeMessage(text, stop_reason)
        fake = FakeClient(message, chunks if chunks is not None else [text])
        monkeypatch.setattr(client_mod, "get_client", lambda: fake)
        return fake

    return install


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """No ambient ANTHROPIC_* settings should leak into a test."""
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
