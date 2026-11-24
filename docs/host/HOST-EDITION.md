# Fireblade Host — the containerised edition

Three editions share one repository:

| Edition | What it is | State |
| --- | --- | --- |
| **Fireblade Desktop** | the Windows application (`Fireblade.exe`), the reference | shipped (0.7.9) |
| **Fireblade Host** | the same core served over HTTP, one analyst or a small team, cases on the local disk | usable slice, this document |
| **Fireblade Server** | the multi-analyst edition: central API, one container per case, RBAC, audit log | not started |

## What is in place

- `src/fireblade/web/` — a FastAPI service over `fireblade.core`, no Qt anywhere.
  - `service.py` reads the catalogue (`InvestigationLibrary`), opens analyses with
    the desktop's own `View`/`Filter`/`FilterGroup`/`SortKey` objects, and covers
    the case lifecycle (create, rename, archive, restore, destroy with certificate,
    portable `.fireblade` export and import), reading (rows, multi-column sort,
    filters, nested filter groups, grouping with date intervals, bookmarks, cell
    notes, views, colour rules, derived columns, CSV export, full-text search),
    importing (the thirteen readers plus native CSV, three layouts, per-file import
    history, and a preview before anything is read), Hayabusa detection, IOC
    hunting with saved hunts, the attack graph and its ATT&CK Navigator layer, the
    HTML report, the action tracking and its CSV export, and the timeline.
  - `server.py` exposes those operations under `/api/…` (plus `/health`,
    `/api/profiles`, `/api/settings`) and serves the interface.
  - `cli.py` gives two commands: `serve` and `count`.
- `src/fireblade/web/static/` — the grid, carried over from the desktop window:
  same palette from `ui/theme.py`, same density, same column filters, same
  Root/Previous/Next pager, same status bar. Dialogs cover the import preview, the
  filter tree, views, colour rules, grouping and the column manager.
- `tests/core/test_no_qt.py` — fails if any `fireblade.core` module imports Qt at
  module level, and imports every core module with PySide6 blocked.
- `tests/web/test_web_service.py` — builds a case the way the desktop does and
  reads it back through the service.
- `requirements-core.txt`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`.

## One container per case (0.8.0)

The Host used to serve every case from a single container. A case is now an object of its
own: `src/fireblade/web/agency.py` is a driver that creates one container per case opened,
proxies `/case/<id>/` to it, and erases the container with the case.

```
navigateur ──► driver :8080 ──► fireblade-case-<id8> (image fireblade:host)
                 │                    montage : /srv/fireblade/volumes/<id> → /data/library
                 └─ socket docker, /srv/fireblade/certificates
```

- **One volume per case** — `/srv/fireblade/volumes/<id>/` holds the case folder, `exports/`,
  `archives/` and the certificate annexes. The volume *is* the case's library root, which is
  how the service reads a case directory; the container mounts it and nothing else.
- **The driver reads nothing else than the volumes** and analyses nothing: its image
  (`deploy/host/Dockerfile.driver`, ~320 MB) carries the docker CLI, FastAPI, httpx and the
  core modules that describe and destroy a case — no Qt, no .NET, no readers, no DuckDB.
- **The prefix is the client's**: every absolute path goes through `url()`, which prepends
  `/case/<id>` when the page is served under it and leaves it alone otherwise, so the
  single-container Host is unchanged.
- **Erasing is the driver's job**: the prefixed `POST /api/cases/<id>/destroy` is answered by
  the driver — the case cannot destroy its own container. It stops the container, runs the
  same `core.case_destruction` as the desktop (residue included), writes the certificate
  into `/srv/fireblade/certificates` and removes the volume.
- **The ceiling**: `--max-open` (three by default) bounds the running containers; the oldest
  unused is stopped. Reopening is a start, not a rebuild.
- **Docker paths and uids**: a containerised driver asks the daemon for host paths
  (`--host-volumes`, `--host-certificates`), and hands each new volume to the case image's
  user (`--case-uid`, 10001) — without that, the case lists as a permission error.

## Running it

```bash
# the smoke test: open a case and count its rows, no window, no Qt
python -m fireblade.web count --root /data/cases

# the interface
python -m fireblade.web serve --root /data/cases --port 8080
```

In Docker, one container for the whole library (the 0.7 shape):

```bash
FIREBLADE_CASES=/srv/fireblade/cases docker compose up -d
# http://localhost:8080
```

Published images, so a Host starts without a clone:

```bash
docker run -d --name fireblade-host -p 8080:8080 \
    -v /srv/fireblade/cases:/data/cases \
    ghcr.io/23r0534zxt/fireblade-host:latest
```

One container per case, through the driver (`ghcr.io/23r0534zxt/fireblade-driver`):

```bash
docker network create fireblade-cases 2>/dev/null || true
docker run -d --name fireblade-driver -p 8080:8080 --network fireblade-cases \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /srv/fireblade/volumes:/data/volumes \
    -v /srv/fireblade/certificates:/data/certificates \
    ghcr.io/23r0534zxt/fireblade-driver:latest \
    python -m fireblade.web.agency serve \
      --image ghcr.io/23r0534zxt/fireblade:latest \
      --volumes /data/volumes --host-volumes /srv/fireblade/volumes \
      --certificates /data/certificates --host-certificates /srv/fireblade/certificates \
      --host 0.0.0.0 --port 8080
# http://localhost:8080 — the driver's page lists the cases
```

The image installs `requirements-core.txt` (no PySide6) on `python:3.12-slim`, adds
the .NET 10 runtime and ICU for the readers, runs as an unprivileged user, and
declares a healthcheck. The desktop edition keeps PySide6 as a hard dependency and
is unaffected.

## Importing in this edition

A browser cannot hand over a path on the server, so a file is sent to the case's
own `evidence/` folder first and read from there; a path can also be given directly
when the case folder is already on the server. All three layouts of the desktop are
available (one grid per file, per artifact family, or one merged grid).

Before the collection reads anything, **Import a file** shows a preview: the
columns and their role, the profile `fireblade.core.profiles.detect_profile`
recognises, the mapping `profile_view` will keep (sort column, timestamps,
booleans, derived timestamp columns, colour rules), the profile fields the file
does not carry, and sample rows. Nothing is hashed, copied or written during the
preview, so confirming it starts the same import the desktop would run.

## Compatibility with the Windows edition

The case folder is untouched: `case.json`, the session file and the DuckDB files
are read where the desktop wrote them, in the same format. An analysis is opened
writable, because the analyst books rows and writes cell notes from the grid; the
other files of the case keep their desktop layout, and a case written here opens in
the Windows application and the other way round.

## Not there yet, and known on purpose

- **Overriding the detected profile at import.** The preview shows it; the core
  applies its own choice and exposes no per-import override.
- **Naming a saved hunt.** Hunts are timestamped and restore their indicator list,
  so they can be replayed, but they cannot be named.
- **Editing an import profile.** The list is shown read-only; the editor belongs to
  the desktop preferences.
- **Authentication.** The service binds `127.0.0.1` by default. The token and the
  RBAC arrive with the Server edition, not by quietly exposing a Host instance.

The command-by-command status is in `HOST-PARITY.md`.

## Deliberate decision: no share of a Windows folder as a shortcut

Mounting the desktop's case folder and calling it "containerised" would have
looked cheap and delivered nothing: the interface is Qt, so there is nothing to
show in a browser, and the readers are Windows binaries. The container therefore
carries a real HTTP service and a real grid, and runs the readers it can: the
managed .NET parsers on the .NET runtime, Hayabusa as its Linux build.
