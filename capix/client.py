"""A thin, stateless wrapper around the Claude Messages API.

Every call builds a fresh single-turn `messages` array, so there is no
conversation state to carry over or reset — the API itself is stateless.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import anthropic

# Built-in default model. ANTHROPIC_MODEL (from .env or the shell) overrides
# it; an explicit `model=` argument overrides both.
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 16_000

# Models that accept adaptive thinking and `output_config.effort`. Older
# models — including the default claude-haiku-4-5 — reject both with a 400,
# so these parameters are only sent for models listed here. Add new models as
# they ship.
THINKING_MODELS = frozenset(
    {
        "claude-fable-5",
        "claude-mythos-5",
        "claude-opus-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-sonnet-5",
        "claude-sonnet-4-6",
    }
)

# Safety classifiers on these models can decline a request. Server-side
# fallbacks re-run the declined request on a fallback model inside the same
# call; "default" lets Anthropic route by refusal category, so there is no
# model list to maintain. The parameter is not accepted on other models.
FALLBACK_MODELS = frozenset({"claude-opus-5", "claude-fable-5", "claude-mythos-5"})
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client: anthropic.Anthropic | None = None


class MissingCredentialsError(RuntimeError):
    """Raised when the SDK could not find an API key anywhere."""

    def __init__(self) -> None:
        super().__init__(
            "No Anthropic credentials found. Copy .env.example to .env and set "
            "ANTHROPIC_API_KEY, or export it in your shell."
        )


class RefusalError(RuntimeError):
    """Raised when Claude declined the request (`stop_reason == "refusal"`)."""

    def __init__(self, category: str | None, explanation: str | None) -> None:
        self.category = category
        self.explanation = explanation
        detail = explanation or "no explanation provided"
        super().__init__(f"Claude declined this request ({category or 'uncategorized'}): {detail}")


def default_model() -> str:
    """The model used when no `model` argument is given.

    Resolution order: ANTHROPIC_MODEL → DEFAULT_MODEL. This reads the real
    environment only — as a library we never load `.env` on the caller's
    behalf. The `capix` CLI loads it before doing anything else.
    """
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def get_client() -> anthropic.Anthropic:
    """Return a lazily-constructed, process-wide Anthropic client."""
    global _client
    if _client is None:
        # Zero-arg constructor: the SDK resolves the key from the environment.
        _client = anthropic.Anthropic()
    return _client


def ask(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    effort: str | None = None,
    on_text: Callable[[str], None] | None = None,
) -> str:
    """Send one context-free prompt and return Claude's text response.

    Args:
        prompt: The user message. This is the entire conversation.
        system: Optional system prompt.
        model: Model id. Defaults to ANTHROPIC_MODEL, else DEFAULT_MODEL.
        max_tokens: Hard ceiling on thinking + response tokens.
        effort: One of "low", "medium", "high", "xhigh", "max". Only accepted
            by the models in THINKING_MODELS. Omit for the API default.
        on_text: Called with each text chunk as it streams in. Use it to print
            output live; leave it None to just wait for the full answer.

    Raises:
        ValueError: if `effort` is set on a model that does not support it.
        MissingCredentialsError: if no API key could be resolved.
        RefusalError: if Claude declined the request.
    """
    message = ask_message(
        prompt,
        system=system,
        model=model,
        max_tokens=max_tokens,
        effort=effort,
        on_text=on_text,
    )
    return "".join(block.text for block in message.content if block.type == "text")


def ask_message(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    effort: str | None = None,
    on_text: Callable[[str], None] | None = None,
):
    """Same as `ask`, but returns the full message object (usage, stop_reason, ...)."""
    model = model or default_model()

    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system is not None:
        params["system"] = system

    if model in THINKING_MODELS:
        params["thinking"] = {"type": "adaptive"}
        if effort is not None:
            params["output_config"] = {"effort": effort}
    elif effort is not None:
        raise ValueError(
            f"model {model!r} does not support the effort parameter; "
            f"it is accepted by: {', '.join(sorted(THINKING_MODELS))}"
        )

    if model in FALLBACK_MODELS:
        params["betas"] = [FALLBACK_BETA]
        params["fallbacks"] = "default"

    # Always stream: it keeps long responses from hitting request timeouts,
    # whether or not the caller wants the chunks.
    try:
        with get_client().beta.messages.stream(**params) as stream:
            if on_text is not None:
                for chunk in stream.text_stream:
                    on_text(chunk)
            message = stream.get_final_message()
    except TypeError as exc:
        # The SDK reports "no credentials at all" as a bare TypeError deep in
        # header construction. Anything else is a genuine bug — re-raise it.
        if "Could not resolve authentication method" not in str(exc):
            raise
        raise MissingCredentialsError() from None

    if message.stop_reason == "refusal":
        details = message.stop_details
        raise RefusalError(
            getattr(details, "category", None),
            getattr(details, "explanation", None),
        )

    return message
