## What changes, and why

<!-- What was wrong, and what is true now. One subject per pull request. -->

## How it was checked

- [ ] `ruff format --check` and `ruff check` pass
- [ ] `pytest` passes, and a test fails without this change
- [ ] A change to the Host's client has a browser test (`tests/web/test_browser*.py`)
- [ ] Wording the analyst reads is in English, with its entry in `core/i18n*.py` when the core words it
- [ ] Evidence is never altered; no real data in fixtures

## Notes for the reviewer

<!-- Limits, follow-ups, anything not verified (for example, no Docker daemon or .NET runtime here). -->
