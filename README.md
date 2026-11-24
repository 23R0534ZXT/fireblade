# Fireblade

[![Windows validation](https://github.com/23R0534ZXT/fireblade/actions/workflows/windows.yml/badge.svg?branch=main)](https://github.com/23R0534ZXT/fireblade/actions/workflows/windows.yml)

**A local DFIR workspace for Windows artifacts, Linux logs and tabular evidence.**

Fireblade reads a collected folder, keeps every file accounted for, and puts the results in
one workspace: filterable tables, a cross-analysis timeline, indicator hunting, detections
grouped into findings, an attack graph, and a case that can be saved, moved and erased
verifiably. Everything runs on the analyst's own machine: no upload, no cloud account, no
API key, no telemetry. The Host's one outbound request is the optional check for a newer
release (see [Updates](#updates)).

![The Fireblade Host workspace: a case of Linux logs](docs/assets/host/host-workspace.png)

## Editions

| | **Host** | **Desktop** | **Server** |
| --- | --- | --- | --- |
| Status | **maintained** | frozen at 0.7.9 | planned |
| Runs on | a Linux container, in a browser | Windows x64 | a Linux host with Docker |
| Users | one analyst, on their own machine | one analyst | several analysts at once, on the same case or on different ones |
| Cases | one container per case | files on disk | one container per case |
| Access control | none — local use only | none | accounts, roles, audit log |

All editions share the same engine (`src/fireblade/core`), the same readers and the same case
format: a case written by one opens in another.

The **Host** is the Desktop's workspace served to a browser from a container. It is meant to
run on the analyst's own machine and to listen on it alone; it has no accounts, and nothing in
it is designed to be exposed to a network. The **Server** edition, for collaboration, is
specified but not started — see [Roadmap](#roadmap).

## Host

### Run it

One line; Docker downloads the image the first time, and creates the cases folder if it is missing:

```bash
docker run -d --name fireblade --restart unless-stopped -p 127.0.0.1:8080:8080 -v "$HOME/fireblade-cases:/data/cases" ghcr.io/23r0534zxt/fireblade:latest && echo "Fireblade is starting: open http://localhost:8080 in a few seconds"
```

Prefix the command with `sudo` if your user is not in the `docker` group. Then open <http://localhost:8080>. `/data/cases` is the path inside the container; your cases are in
`~/fireblade-cases` on your machine, and a case written by the Desktop opens as soon as its
folder is there. On Windows PowerShell, write the folder as `"$HOME\fireblade-cases"`.

| | |
| --- | --- |
| Stop / start | `docker stop fireblade` · `docker start fireblade` |
| Upgrade | `docker pull ghcr.io/23r0534zxt/fireblade:latest && docker rm -f fireblade`, then run the line above again (the cases stay in their folder) |
| Pin a version | replace `:latest` with `:0.8.3` · `:edge` follows `main` |
| Remove | `docker rm -f fireblade` (your cases are not touched) |

To build from a clone instead: `docker build -t fireblade:host .`.

### Updates

When a newer release exists, a band across the top of the page says so, with the release notes
and the line to run: pull the new image, remove the old container, start it again. Your cases
stay in their folder, and nothing updates itself — a tool that signs destruction certificates
changes version when someone decides to.

To find out, the container asks GitHub's public releases API at most once every six hours. That
request carries no information about you or your cases, and it is the only one the Host makes.
On an isolated network, or if you prefer it that way, switch it off with
`-e FIREBLADE_UPDATE_CHECK=off`: the band never appears, and you follow the
[releases](https://github.com/23R0534ZXT/fireblade/releases) yourself.

The image carries the .NET 10 runtime and the thirteen pinned readers, so it reads the same
artifacts as the Desktop.

### One container per case

The default deployment above serves every case from one container. For isolation, run the
driver: it creates a container for each case that is opened, mounts that case's volume and
nothing else, and removes the container and the volume when the case is erased. The
destruction certificate is written outside the volumes.

```mermaid
flowchart LR
    B[Browser] --> D[Driver<br/>lists, opens, erases]
    D -->|/case/id1/| C1[Case container 1<br/>volume: case 1]
    D -->|/case/id2/| C2[Case container 2<br/>volume: case 2]
    D -.->|docker API| E[(Docker engine)]
    D --> P[(Certificates<br/>outside the volumes)]
```

```bash
docker network create fireblade-cases 2>/dev/null || true
docker run -d --name fireblade-driver -p 127.0.0.1:8080:8080 --network fireblade-cases \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /srv/fireblade/volumes:/data/volumes \
    -v /srv/fireblade/certificates:/data/certificates \
    ghcr.io/23r0534zxt/fireblade-driver:latest \
    python -m fireblade.web.agency serve \
      --image ghcr.io/23r0534zxt/fireblade:latest \
      --volumes /data/volumes --host-volumes /srv/fireblade/volumes \
      --certificates /data/certificates --host-certificates /srv/fireblade/certificates \
      --host 0.0.0.0 --port 8080
```

From a clone: `docker compose -f deploy/host/docker-compose.driver.yml up -d --build`. The driver
mounts the Docker socket, which is root on the machine: run it only where that is acceptable.
Deployment notes and the upgrade recipe: [deploy/host](deploy/host/README.md).

### What you can do

- **Import** a file, a folder (sent from the browser), a mounted volume or a disk image. Every
  file is hashed, copied into the case and read by the matching reader; the Imports tab says
  which files were read, by which reader, and why one was not.
- **Investigate a table**: per-column filters, grouping, multi-column sort, pinned and derived
  columns, bookmarks, row and cell notes, colour rules and visual formats, saved views. Source
  values are never rewritten.
- **Build a timeline** across analyses from the dates the analyst designates, with the rows that
  carry no usable date counted rather than dropped.
- **Hunt indicators** (IPs, domains, URLs, hashes) across every analysis of a case.
- **Detect**: Hayabusa rules run locally over parsed EVTX; findings are grouped, mapped to
  ATT&CK and drawn as an attack graph.
- **Track the work**: actions, machines and accounts, indicators.
- **Report**: an investigation report and a client report, as HTML or PDF.
- **Keep or move a case**: portable `.fireblade` packages with verified hashes, history and
  recovery, and a verified erasure with a certificate.

Long commands (import, scan, timeline, detection, report, package) run as jobs with a progress
bar, the engine's own messages, and a Stop.

### Limits

| | |
| --- | --- |
| `SRUDB.dat` (SRUM) | `SrumECmd` needs Windows' ESE libraries. The Host says so; import the CSV the Desktop produced. |
| Assistant | The local analyst assistant exists in the Desktop only. |
| Language | English. |
| Erasure | Overwriting files cannot be guaranteed on SSDs, copy-on-write or journaled file systems; the certificate states the method used, not a physical guarantee. |
| Access control | None. Do not expose the Host to a network. |
| Tested at scale | A 31 574-row EVTX and a 333-file collection. No claim is made beyond that. |

The full statement of what is and is not verified: [docs/host/STATUS.md](docs/host/STATUS.md).
Reader by reader, with the rows each wrote: [docs/host/LINUX-READERS.md](docs/host/LINUX-READERS.md).

## Desktop

The Windows edition is frozen: version 0.7.9 is its last build and receives no changes.

**[Download Fireblade 0.7.9 — Windows x64](https://github.com/23R0534ZXT/fireblade/releases/download/v0.7.9/Fireblade-0.7.9-win64.zip)** · [Release notes and SHA-256](https://github.com/23R0534ZXT/fireblade/releases/tag/v0.7.9)

Unzip and run `Fireblade.exe`; Python, Qt, the parsers and the .NET readers are inside the
folder. The executable is unsigned: Windows may show a SmartScreen prompt (*More info* →
*Run anyway*), and Smart App Control on a fresh Windows 11 may refuse it. Verify the download
against the SHA-256 in the release notes. Documentation: [docs/desktop](docs/desktop).

![The Desktop workspace](docs/assets/fireblade-workspace.png)

Sample data: the
[sample collection](https://github.com/23R0534ZXT/fireblade/releases/download/test-pack-v2/Fireblade-Sample-Collection-2026-11-18.zip)
(a Windows 11 machine: 183 event logs, Amcache, 60 Prefetch entries, 251 scheduled tasks), the
[discovery pack](https://github.com/23R0534ZXT/fireblade/releases/download/test-pack-v1/Fireblade-Test-Pack-v1.zip)
and the [raw artifact pack](https://github.com/23R0534ZXT/fireblade/releases/download/raw-artifacts-v1/Fireblade-Raw-Artifacts-v1.zip).

## Roadmap

**Server** is the Host for several analysts working at once, several of them on the same case while
others work on other cases: an application that manages cases and their containers, role-based
access control, an audit log of every action, HTTPS, and a secure erasure that stops the case
container, removes it and wipes its data. Several analysts on one case means one service per case
container that serves all of them, with each analyst's marks, notes and views attributed to them. The design is in
[docs/host/HANDOFF-DOCKER.md](docs/host/HANDOFF-DOCKER.md). Nothing of it is implemented yet.

Planned for the Host: per-case encrypted volumes, so that erasing a case means destroying its key.

## Repository

```
src/fireblade/
  core/        the engine every edition runs: cases, readers, grid, timeline, reports
  web/         the Host: FastAPI service, per-case driver, browser client in static/
  ui/          the Desktop (Qt); frozen, not imported by the Host
  runtime/     bootstrap and resources
  validation/  the Windows qualification harness
config/        the pinned readers and profiles
deploy/host/   building and running the Host
docs/          desktop, host, user guides, development notes
tests/         core, web (including real-browser tests), runtime, ui, fixtures
```

## Build and test

```bash
python -m venv .venv && . .venv/bin/activate
python -m pip install -e '.[dev,web,browser]'
python -m scripts.dev_check          # version, ruff, client JavaScript, full suite
```

The browser tests in `tests/web/test_browser*.py` drive the client with a real mouse; they need
Playwright and a Chromium (`FIREBLADE_CHROMIUM` names one it did not download) and are skipped
without them. Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

- [Host status and what is verified](docs/host/STATUS.md) · [Host audit against the Desktop](docs/host/HOST-AUDIT.md)
- [Desktop](docs/desktop) · [user guides](docs/guides) · [architecture](docs/development/ARCHITECTURE.md)
- [Release notes](docs/development/RELEASE-NOTES.md) · [Timeline Explorer comparison](docs/development/BENCHMARK-0.4.0.md)

## Known limits

- **Detections assist, they do not conclude**: an alert is a lead for an analyst to verify.
- **An analysis workspace, not an acquisition tool**: no disk imaging, carving, decryption or OCR.
- **.NET plugins run with your rights**: load only assemblies you trust.
- **Paths beyond 260 characters** on Windows need `LongPathsEnabled=1`.

## License

Code under [MIT](LICENSE). Bundled tools and dependencies keep their own licences, including
AGPL components; notices are in [licenses/THIRD_PARTY.md](licenses/THIRD_PARTY.md).
