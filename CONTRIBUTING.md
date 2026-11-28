# Contributing to Kogarasu

An investigator needs to trace an imported value, a detection or an erasure record back to its source.
Changes that affect these workflows need an observable result and a reproducible check.

## Set up

```bash
python -m venv .venv && . .venv/bin/activate
python -m pip install -e '.[dev,web,browser,pdf]'
python -m playwright install --with-deps chromium
python -m scripts.dev_check --quick     # version, ruff, client JavaScript, the Desktop window
```

Host CI uses Python 3.12 on Linux. Install Node.js for JavaScript checks. On a minimal
Ubuntu machine the Qt smoke test also needs `libegl1`, `libopengl0`, `libxkbcommon0`
and `libgl1`. The historical Desktop build runs on Windows. [Windows build notes](docs/development/CONTRIBUER.md)

## The checks a change must pass

```bash
python -m ruff format --check src scripts tests
python -m ruff check src scripts tests
QT_QPA_PLATFORM=offscreen python -m pytest tests -q --ignore=tests/windows --ignore=tests/ui
```

`tests/web/test_browser*.py` drive the client with a real mouse and need Playwright and a Chromium
(set `FIREBLADE_CHROMIUM` to use one Playwright did not download); without them they are skipped.
The same checks run in CI on every pull request. `pre-commit install` runs the formatter and the
linter before each commit.

## What a change looks like

- **One concern per commit**, with a message that says what was wrong and what is true now, not
  only what was edited. Reference the issue when there is one.
- **A test that fails without the change.** A bug fix carries the test that would have caught it;
  for the Host's client that means a browser test, because a handler that works when a script calls
  it can still be unreachable by a hand.
- **Observable behaviour, failure included.** A change to a query, an import, a cancellation or a
  persistence path is checked on what the analyst sees, including when it fails.
- **Evidence is never altered.** Source values, column names of a file the analyst brought, and
  the bytes of a source stay as they were; anything derived says so.
- **Synthetic or public data only**, with its provenance recorded. No real case, no client data.
- **English.** The product, its messages, its documents and its commit messages are in English.
  The core still writes some sentences in French, its source language, and `core/i18n*.py` carries
  the English: a new refusal or document sentence needs its entry, and `tests/test_error_messages.py`
  and `tests/test_translation_coverage.py` fail until it has one.

## Layout

| Path | Role |
| --- | --- |
| `src/fireblade/core` | the engine every edition runs |
| `src/fireblade/web` | the Host: service, per-case driver, browser client |
| `src/fireblade/ui` | the Desktop (Qt), frozen |
| `tests` | `core`, `web` (including real-browser tests), `runtime`, `ui` |
| `docs`, `deploy/host` | documentation and deployment |

The architecture map is in [docs/development/ARCHITECTURE.md](docs/development/ARCHITECTURE.md).

## Pull requests

Work on a branch, open a pull request against `main`, and fill the template. The checks must pass
and a maintainer must approve before it is merged (branch protection enforces this on `main`).
Keep a pull request to one subject so it can be reviewed, reverted, or bisected as one.

## Releases

For Host, a `vX.Y.Z` tag on `main` triggers publication of the Host and driver images.
The release notes and changelog describe the analyst-visible changes and the checks
run against that version. The on-disk case format is the compatibility commitment.
The HTTP API is internal. Windows Desktop is frozen at 0.7.9.
[Publication guide](docs/development/PUBLICATION.md) · [Release notes](docs/development/RELEASE-NOTES.md) · [Changelog](CHANGELOG.md)

## Reporting a problem

Bugs and requests: the [issue forms](https://github.com/23R0534ZXT/kogarasu/issues/new/choose).
Security problems: [SECURITY.md](SECURITY.md), not a public issue.
