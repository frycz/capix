# Releasing capix

Publishing is done from the command line with [twine](https://twine.readthedocs.io/),
authenticated by API tokens in `~/.pypirc`. There is no CI: every release is a
deliberate local action.

`uvx twine` runs twine without installing it into the project, so it is not a
dependency of this package.

## One-time setup

1. Register at [pypi.org](https://pypi.org/account/register/) and enable 2FA
   (mandatory — uploads are rejected without it).
2. Do the same at [test.pypi.org](https://test.pypi.org/account/register/).
   It is a completely separate account, with its own password and tokens.
3. Create an API token on each:
   [PyPI](https://pypi.org/manage/account/token/) ·
   [TestPyPI](https://test.pypi.org/manage/account/token/).
   Scope the PyPI one to **"Entire account"** — a project-scoped token cannot
   be created until the project exists. Swap it for a project-scoped token
   after the first release (see [After the first release](#after-the-first-release)).
4. Put both in `~/.pypirc`:

   ```ini
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   username = __token__
   password = pypi-AgEIcHlwaS5vcmc...

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-AgENdGVzdC5weXBpLm9yZw...
   ```

   ```sh
   chmod 600 ~/.pypirc      # plaintext credentials
   ```

**`username` must be the literal string `__token__`**, not your account name.
That is how the upload API expects an API token to be presented. Guides that
tell you to enter your PyPI username and password predate mandatory 2FA and no
longer work — if an existing `~/.pypirc` has a real username in it, this is the
line to fix.

## Every release

### 1. Bump the version

`version` in `pyproject.toml` is the single source of truth.

```sh
$EDITOR pyproject.toml     # e.g. 0.1.0 -> 0.1.1
```

**A version number on PyPI can never be reused.** Publishing a broken 0.1.1
means yanking it and releasing 0.1.2; there is no overwrite. This is the reason
for the TestPyPI step below.

### 2. Test and build

```sh
uv sync
uv run pytest -q
rm -rf dist && uv build
uvx twine check dist/*
```

`rm -rf dist` matters: twine uploads whatever `dist/*` matches, and stale
artifacts from an earlier version would be uploaded alongside the new ones.

`twine check` catches a README that would fail to render on the project page —
worth running before the upload, not after.

### 3. Dry run on TestPyPI

```sh
uvx twine upload -r testpypi dist/*
```

Then install it the way a stranger would:

```sh
uvx --index https://test.pypi.org/simple/ \
    --index-strategy unsafe-best-match \
    --from capix capix "say hi"
```

`--index-strategy unsafe-best-match` is required because TestPyPI has no copy
of `anthropic`; without it the dependency cannot resolve from real PyPI.

### 4. Publish

```sh
uvx twine upload dist/*
```

With `~/.pypirc` in place this prompts for nothing.

### 5. Verify and tag

```sh
uvx --from capix capix "say hi"
git tag "v$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
git push --tags
```

The tag is a record of what was released; nothing is triggered by it.

## After the first release

Once `capix` exists on PyPI, replace the account-wide token with one scoped to
just this project — a leaked project token can only harm this package.

1. Create a project-scoped token at
   [pypi.org/manage/project/capix/settings](https://pypi.org/manage/project/capix/settings/).
2. Replace the `password` under `[pypi]` in `~/.pypirc`.
3. Delete the account-wide token at
   [pypi.org/manage/account/token](https://pypi.org/manage/account/token/).

## Fixing a bad release

There is no delete, only *yank*: the release stays downloadable for anyone who
pinned it exactly, but resolvers stop selecting it.

```
pypi.org/manage/project/capix/release/<version>/  ->  Yank
```

Then fix, bump the patch version, and release again.

## Notes

- Nothing here reads `.env`; `ANTHROPIC_API_KEY` has no role in publishing.
- `~/.pypirc` holds credentials in plaintext. Keep it `600`, and never commit
  a copy into a project.
- To override the file for one upload, twine also honours `TWINE_USERNAME`
  (`__token__`) and `TWINE_PASSWORD`.
