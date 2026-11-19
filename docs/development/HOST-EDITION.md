# Fireblade Host — the first containerised edition

Three editions share one repository:

| Edition | What it is | State |
| --- | --- | --- |
| **Fireblade Desktop** | the Windows application (`Fireblade.exe`), the reference | shipped (0.7.9) |
| **Fireblade Host** | the same core served over HTTP, one analyst or a small team, cases on the local disk | first slice, this document |
| **Fireblade Server** | the multi-analyst edition: central API, one container per case, RBAC, audit log | not started |

## What is in place

- `src/fireblade/web/` — a FastAPI service over `fireblade.core`, no Qt anywhere.
  - `service.py` reads the catalogue (`InvestigationLibrary`), opens an analysis
    read-only, pages it with the desktop's own `View`/`Filter`/`SortKey` objects,
    and exports the current view as CSV.
  - `server.py` exposes `/health`, `/api/cases`, `/api/cases/{id}`,
    `/api/cases/{id}/analyses/{n}/rows`, `…/export`, and serves the interface.
  - `cli.py` gives two commands: `serve` and `count`.
- `src/fireblade/web/static/` — the grid, carried over from the desktop window:
  same palette from `ui/theme.py`, same density, same column filters, same
  Root/Previous/Next pager, same status bar. Display settings scale the text.
- `tests/core/test_no_qt.py` — fails if any `fireblade.core` module imports Qt at
  module level, and imports every core module with PySide6 blocked.
- `tests/web/test_web_service.py` — builds a case the way the desktop does and
  reads it back through the service.
- `requirements-core.txt`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`.

## Running it

```bash
# the smoke test: open a case and count its rows, no window, no Qt
python -m fireblade.web count --root /data/cases

# the interface
python -m fireblade.web serve --root /data/cases --port 8080
```

In Docker:

```bash
FIREBLADE_CASES=/srv/fireblade/cases docker compose up -d
# http://localhost:8080
```

The image installs `requirements-core.txt` (no PySide6), so it stays small; the
desktop edition keeps PySide6 as a hard dependency and is unaffected.

## Compatibility with the Windows edition

The case folder is untouched: `case.json`, the session file and the DuckDB files
are read where the desktop wrote them, never rewritten (the service opens
analyses with `read_only=True`). A case created on Windows opens here and the
other way round.

## Not there yet, and known on purpose

- **Importing artifacts.** The thirteen readers are Windows executables; until
  phase 5 the Host edition reads cases prepared elsewhere.
- **The other tabs.** Timeline, IOC hunting, Hayabusa, actions, attack graph and
  the report are shown disabled in the tab strip, so the interface never pretends
  they work.
- **Writing anything.** Bookmarks and views are read-only for now.
- **Authentication.** The service binds `127.0.0.1` by default. The token and the
  RBAC arrive with the Server edition, not by quietly exposing a Host instance.

## Deliberate decision: no share of a Windows folder as a shortcut

Mounting the desktop's case folder and calling it "containerised" would have
looked cheap and delivered nothing: the interface is Qt, so there is nothing to
show in a browser, and the readers are Windows binaries. The container therefore
carries a real HTTP service and a real grid; the import step comes later.
