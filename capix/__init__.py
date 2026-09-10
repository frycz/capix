"""A thin, stateless wrapper around the Claude Messages API."""

from importlib.metadata import PackageNotFoundError, version as _version

from .client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    FALLBACK_MODELS,
    THINKING_MODELS,
    MissingCredentialsError,
    RefusalError,
    ask,
    ask_message,
    default_model,
    get_client,
)

try:
    __version__ = _version("capix")
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "ask",
    "ask_message",
    "get_client",
    "default_model",
    "RefusalError",
    "MissingCredentialsError",
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "THINKING_MODELS",
    "FALLBACK_MODELS",
]
