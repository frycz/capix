"""CLI argument handling and exit codes. No network: `ask` is monkeypatched."""

from __future__ import annotations

import io
import os
import pathlib

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

import pytest

import capix
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


class TestDotenvDiscovery:
    """Regression: `.env` must be found relative to the user's cwd.

    python-dotenv's find_dotenv defaults to searching upward from the calling
    *module's* directory. For an installed package that is site-packages, so a
    bare load_dotenv() silently finds nothing when the CLI is run from a
    project directory — which is the only way it is ever run.
    """

    def test_finds_dotenv_in_cwd(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("ANTHROPIC_MODEL=from-dotenv\n")
        monkeypatch.chdir(tmp_path)
        assert cli.load_env_from_cwd() == str(tmp_path / ".env")
        assert os.environ["ANTHROPIC_MODEL"] == "from-dotenv"

    def test_finds_dotenv_in_a_parent_directory(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("ANTHROPIC_MODEL=from-parent\n")
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        cli.load_env_from_cwd()
        assert os.environ["ANTHROPIC_MODEL"] == "from-parent"

    def test_returns_none_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cli.load_env_from_cwd() is None

    def test_exported_variable_wins_over_dotenv(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("ANTHROPIC_MODEL=from-dotenv\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ANTHROPIC_MODEL", "from-shell")
        cli.load_env_from_cwd()
        assert os.environ["ANTHROPIC_MODEL"] == "from-shell"


class TestVersionFlag:
    """--version reads installed metadata, so it can never drift from the
    version in pyproject.toml the way a hardcoded string would."""

    @pytest.mark.parametrize("flag", ["-v", "--version"])
    def test_prints_version_and_exits_zero(self, capsys, flag):
        with pytest.raises(SystemExit) as exc:
            cli.main([flag])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert out.startswith("capix ")
        assert out.split()[1] == capix.__version__

    def test_matches_pyproject(self):
        """Guards against metadata going stale in an editable install."""
        if tomllib is None:
            pytest.skip("tomllib requires Python 3.11+")
        pyproject = pathlib.Path(__file__).parent.parent / "pyproject.toml"
        if not pyproject.exists():  # running against an installed copy
            pytest.skip("no source checkout")
        declared = tomllib.loads(pyproject.read_text())["project"]["version"]
        assert capix.__version__ == declared
