"""The model-capability gating is the actual logic in this wrapper, so that is
what these cover: which parameters get sent to which models, and what happens
when a caller asks for one the model rejects.
"""

from __future__ import annotations

import pytest

from capix import (
    DEFAULT_MODEL,
    FALLBACK_MODELS,
    THINKING_MODELS,
    RefusalError,
    ask,
    ask_message,
    default_model,
)
from capix.client import FALLBACK_BETA

THINKING = "claude-sonnet-5"
NON_THINKING = "claude-haiku-4-5"
FALLBACK = "claude-opus-5"


def test_frozensets_are_consistent():
    # Every model that accepts fallbacks must also accept thinking; the
    # reverse is not true.
    assert FALLBACK_MODELS <= THINKING_MODELS
    assert NON_THINKING not in THINKING_MODELS


class TestModelResolution:
    def test_falls_back_to_builtin_default(self):
        assert default_model() == DEFAULT_MODEL

    def test_env_var_overrides_builtin(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")
        assert default_model() == "claude-opus-5"

    def test_explicit_argument_beats_env_var(self, monkeypatch, fake_client):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")
        fake = fake_client()
        ask("hi", model=THINKING)
        assert fake.params["model"] == THINKING

    def test_library_never_loads_dotenv(self, tmp_path, monkeypatch):
        """A .env in the cwd must not influence the library.

        Loading it is a CLI-only convenience; doing it on import would be a
        surprising side effect inside someone else's application.
        """
        (tmp_path / ".env").write_text("ANTHROPIC_MODEL=claude-from-dotenv\n")
        monkeypatch.chdir(tmp_path)
        assert default_model() == DEFAULT_MODEL


class TestThinkingParameters:
    def test_thinking_model_gets_adaptive_thinking(self, fake_client):
        fake = fake_client()
        ask("hi", model=THINKING)
        assert fake.params["thinking"] == {"type": "adaptive"}

    def test_effort_is_sent_as_output_config(self, fake_client):
        fake = fake_client()
        ask("hi", model=THINKING, effort="low")
        assert fake.params["output_config"] == {"effort": "low"}

    def test_effort_omitted_when_not_requested(self, fake_client):
        fake = fake_client()
        ask("hi", model=THINKING)
        assert "output_config" not in fake.params

    def test_non_thinking_model_gets_neither(self, fake_client):
        fake = fake_client()
        ask("hi", model=NON_THINKING)
        assert "thinking" not in fake.params
        assert "output_config" not in fake.params

    def test_effort_on_non_thinking_model_raises_before_any_request(self, fake_client):
        """Fail locally rather than letting the API 400."""
        fake = fake_client()
        with pytest.raises(ValueError, match="does not support the effort parameter"):
            ask("hi", model=NON_THINKING, effort="low")
        assert fake.params == {}


class TestFallbacks:
    def test_fallback_model_gets_beta_header(self, fake_client):
        fake = fake_client()
        ask("hi", model=FALLBACK)
        assert fake.params["betas"] == [FALLBACK_BETA]
        assert fake.params["fallbacks"] == "default"

    def test_other_models_do_not(self, fake_client):
        fake = fake_client()
        ask("hi", model=THINKING)
        assert "betas" not in fake.params
        assert "fallbacks" not in fake.params


class TestMessageShape:
    def test_single_turn_user_message(self, fake_client):
        fake = fake_client()
        ask("what is 2+2?")
        assert fake.params["messages"] == [{"role": "user", "content": "what is 2+2?"}]

    def test_system_prompt_omitted_when_none(self, fake_client):
        fake = fake_client()
        ask("hi")
        assert "system" not in fake.params

    def test_system_prompt_passed_through(self, fake_client):
        fake = fake_client()
        ask("hi", system="Be terse.")
        assert fake.params["system"] == "Be terse."

    def test_calls_do_not_accumulate_history(self, fake_client):
        """Context-free by construction: every call is a fresh array."""
        fake = fake_client()
        ask("first")
        ask("second")
        assert fake.params["messages"] == [{"role": "user", "content": "second"}]


class TestOutput:
    def test_ask_returns_joined_text(self, fake_client):
        fake_client(text="hello world")
        assert ask("hi") == "hello world"

    def test_ask_message_returns_the_object(self, fake_client):
        fake_client(text="hello")
        message = ask_message("hi")
        assert message.stop_reason == "end_turn"

    def test_on_text_receives_each_chunk(self, fake_client):
        fake_client(text="abc", chunks=["a", "b", "c"])
        seen: list[str] = []
        ask("hi", on_text=seen.append)
        assert seen == ["a", "b", "c"]

    def test_refusal_raises(self, fake_client):
        fake_client(stop_reason="refusal")
        with pytest.raises(RefusalError):
            ask("hi")
