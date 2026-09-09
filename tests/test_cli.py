"""CLI argument handling and exit codes. No network: `ask` is monkeypatched."""

from __future__ import annotations

import io

import pytest

import capix.cli as cli
from capix.client import MissingCredentialsError, RefusalError


@pytest.fixture
def fake_ask(monkeypatch):
    """Replace cli.ask with a recorder; returns the recorded kwargs dict."""
    recorded: dict = {}

    def install(result: str = "answer", raises: Exception | None = None):
        def _ask(prompt, **kwargs):
            recorded["prompt"] = prompt
            recorded.update(kwargs)
            if raises is not None:
                raise raises
            if kwargs.get("on_text") is not None:
                kwargs["on_text"](result)
            return result

        monkeypatch.setattr(cli, "ask", _ask)
        return recorded

    return install


class TestReadPrompt:
    def test_joins_argv_words(self):
        assert cli.read_prompt(["explain", "CRDTs"]) == "explain CRDTs"

    def test_reads_stdin_when_argv_empty(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("piped prompt\n"))
        assert cli.read_prompt([]) == "piped prompt"

    def test_dash_means_stdin(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("piped\n"))
        assert cli.read_prompt(["-"]) == "piped"

    def test_empty_when_tty_and_no_args(self, monkeypatch):
        stdin = io.StringIO("")
        stdin.isatty = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr("sys.stdin", stdin)
        assert cli.read_prompt([]) == ""


class TestMain:
    def test_no_prompt_is_usage_error(self, monkeypatch, capsys):
        stdin = io.StringIO("")
        stdin.isatty = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr("sys.stdin", stdin)
        assert cli.main([]) == 2
        assert "no prompt given" in capsys.readouterr().err

    def test_streams_by_default(self, fake_ask):
        recorded = fake_ask()
        assert cli.main(["hello"]) == 0
        assert recorded["on_text"] is not None

    def test_no_stream_flag_disables_callback(self, fake_ask):
        recorded = fake_ask()
        assert cli.main(["--no-stream", "hello"]) == 0
        assert recorded["on_text"] is None

    def test_flags_are_forwarded(self, fake_ask):
        recorded = fake_ask()
        cli.main(["-s", "Be terse.", "-m", "claude-opus-5", "-t", "50", "-e", "low", "hi"])
        assert recorded["system"] == "Be terse."
        assert recorded["model"] == "claude-opus-5"
        assert recorded["max_tokens"] == 50
        assert recorded["effort"] == "low"

    def test_prompt_words_are_joined(self, fake_ask):
        recorded = fake_ask()
        cli.main(["explain", "CRDTs", "briefly"])
        assert recorded["prompt"] == "explain CRDTs briefly"

    @pytest.mark.parametrize(
        "exc, code",
        [
            (ValueError("bad effort"), 2),
            (RefusalError("category", "explanation"), 1),
            (MissingCredentialsError(), 1),
        ],
    )
    def test_error_exit_codes(self, fake_ask, capsys, exc, code):
        fake_ask(raises=exc)
        assert cli.main(["hi"]) == code
        assert "error:" in capsys.readouterr().err
