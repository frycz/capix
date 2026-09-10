"""Command-line entry point: `capix "your prompt"`."""

from __future__ import annotations

import argparse
import sys

import anthropic
from dotenv import find_dotenv, load_dotenv

from . import __version__
from .client import (
    DEFAULT_MAX_TOKENS,
    MissingCredentialsError,
    RefusalError,
    ask,
    default_model,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capix",
        description="Send a context-free prompt to Claude and print the answer.",
        epilog='Examples:\n  capix "explain CRDTs in two sentences"\n  cat notes.md | capix "summarize this"',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="The prompt. If omitted, it is read from stdin.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"capix {__version__}",
        help="Print the installed version and exit.",
    )
    parser.add_argument("-s", "--system", help="Optional system prompt.")
    parser.add_argument(
        "-m",
        "--model",
        default=None,
        help=f"Model id (default: {default_model()}; set ANTHROPIC_MODEL in .env to change).",
    )
    parser.add_argument(
        "-t",
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max output tokens (default: {DEFAULT_MAX_TOKENS}).",
    )
    parser.add_argument(
        "-e",
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="How much thinking to spend. Not supported by every model (see --help notes).",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Wait for the full response instead of printing it as it arrives.",
    )
    return parser


def load_env_from_cwd() -> str | None:
    """Load a `.env` found by walking up from the working directory.

    `usecwd=True` is essential. Without it python-dotenv searches upwards from
    the directory holding *this module*, which for an installed package is
    somewhere in site-packages — so a `.env` sitting next to the user in their
    project would never be found.

    Returns the path loaded, or None if there was no `.env` to load.
    """
    path = find_dotenv(usecwd=True)
    if not path:
        return None
    load_dotenv(path)
    return path


def read_prompt(words: list[str]) -> str:
    """Prompt comes from argv, or from stdin when argv is empty or is '-'."""
    joined = " ".join(words).strip()
    if joined and joined != "-":
        return joined
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()


def main(argv: list[str] | None = None) -> int:
    # Loading `.env` is a CLI convenience, never a library side effect. It runs
    # before the parser is built because --model's help shows the resolved
    # default. load_dotenv does not overwrite already-exported variables.
    load_env_from_cwd()
    args = build_parser().parse_args(argv)

    prompt = read_prompt(args.prompt)
    if not prompt:
        print("error: no prompt given (pass one as an argument or pipe it on stdin)", file=sys.stderr)
        return 2

    def emit(chunk: str) -> None:
        print(chunk, end="", flush=True)

    try:
        text = ask(
            prompt,
            system=args.system,
            model=args.model,
            max_tokens=args.max_tokens,
            effort=args.effort,
            on_text=None if args.no_stream else emit,
        )
    except ValueError as exc:  # e.g. --effort on a model that rejects it
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (RefusalError, MissingCredentialsError) as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1
    except anthropic.AuthenticationError:
        print(
            "error: ANTHROPIC_API_KEY was rejected. Check the value in .env.",
            file=sys.stderr,
        )
        return 1
    except anthropic.APIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.no_stream:
        print(text)
    else:
        print()  # terminate the streamed line
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
