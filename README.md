# capix

A thin, stateless wrapper around the Claude Messages API. Send a prompt, get text
back — no conversation history, no session state.

## Install

```sh
uv tool install capix     # global CLI
pip install capix         # or into a project, for the library
uvx capix "hello"         # or run it without installing anything
```

Set `ANTHROPIC_API_KEY` in your environment, or put it in a `.env` file in the
directory you run from — the CLI loads `.env` automatically.

## Developing on it

Managed with [uv](https://docs.astral.sh/uv/). Install it once
(`curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```sh
uv sync                   # creates .venv and installs the project
cp .env.example .env      # then paste your key into .env
```

`uv sync` reads `uv.lock`, so everyone gets the same dependency versions. After
editing `[project.dependencies]`, run `uv lock` (or just `uv sync`, which
re-locks when `pyproject.toml` changed) and commit the updated lockfile.

`.env` is gitignored. The key is read from the environment by the Anthropic SDK;
the CLI loads `.env` into the environment first. An exported
`ANTHROPIC_API_KEY` in your shell takes precedence over the one in `.env`.

Note that loading `.env` is CLI-only. Imported as a library, `capix` reads the
real environment and never touches `.env` — loading it would be a surprising
side effect in someone else's application.

`.env` also accepts `ANTHROPIC_MODEL` to set the default model for every call.

## CLI

```sh
capix "explain CRDTs in two sentences"
capix -e low "what's the capital of France?"
cat notes.md | capix "summarize this"
```

From a source checkout, prefix with `uv run` (`uv run capix "..."`) — that
works without activating anything.

Output streams as it arrives. Options:

| Flag | Meaning |
| --- | --- |
| `-v, --version` | Print the installed version and exit |
| `-s, --system` | System prompt |
| `-m, --model` | Model id (default: `ANTHROPIC_MODEL`, else `claude-haiku-4-5`) |
| `-t, --max-tokens` | Output ceiling (default 16000) |
| `-e, --effort` | `low` … `max`; only on models that support it (see below) |
| `--no-stream` | Wait for the complete response, then print |

`python -m capix "..."` works the same way.

## Library

```python
from capix import ask

answer = ask("explain CRDTs in two sentences")

# With a system prompt and cheaper settings
answer = ask("classify: positive or negative?\n\nthis is great", system="Reply with one word.", effort="low")

# Print tokens as they arrive
ask("write a haiku", on_text=lambda chunk: print(chunk, end="", flush=True))
```

`ask_message(...)` returns the full message object instead of a string, if you
need `usage`, `stop_reason`, or the raw content blocks.

## Choosing a model

Resolution order for every call: explicit `model=` / `-m` → `ANTHROPIC_MODEL`
→ the built-in `claude-haiku-4-5`.

| Id | Notes |
| --- | --- |
| `claude-haiku-4-5` | the default; fastest and cheapest, 200K context |
| `claude-sonnet-5` | near-Opus quality, 1M context |
| `claude-opus-5` | strongest for coding and agentic work |
| `claude-fable-5` | most capable overall, priced above Opus |

Not every model takes the same parameters, so the wrapper sends them
conditionally (see `THINKING_MODELS` / `FALLBACK_MODELS` in `client.py`):

- **Adaptive thinking and `--effort`** are sent only to Sonnet 4.6+/Opus 4.6+
  and the 5-series. Haiku 4.5 rejects both, so they are omitted for it —
  passing `--effort` with such a model raises a `ValueError` up front rather
  than letting the API 400.
- **Server-side refusal fallbacks** are sent only to Opus 5, Fable 5, and
  Mythos 5, whose safety classifiers can decline a request. Other models don't
  accept the parameter.

Both sets are plain frozensets — extend them as new models ship.

## Notes

- **Context-free by construction.** Each call builds a fresh
  `[{"role": "user", ...}]` array. The Messages API is stateless, so there is
  nothing to clear between calls.
- **Always streams internally**, even when you don't consume the chunks — this
  keeps long responses from hitting request timeouts.
- **Refusals raise `RefusalError`** rather than returning empty text.

## Releasing

Published to PyPI from the command line with twine — see [RELEASING.md](RELEASING.md).

## Unofficial

`capix` is a personal, unofficial client. It is not affiliated with or endorsed
by Anthropic. "Claude" is a trademark of Anthropic, PBC.
