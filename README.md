# Kogarasu Host

[![Release](https://img.shields.io/github/v/release/23R0534ZXT/kogarasu)](https://github.com/23R0534ZXT/kogarasu/releases/latest)
[![Host validation](https://github.com/23R0534ZXT/kogarasu/actions/workflows/host.yml/badge.svg?branch=main)](https://github.com/23R0534ZXT/kogarasu/actions/workflows/host.yml)
[![Container build](https://github.com/23R0534ZXT/kogarasu/actions/workflows/containers.yml/badge.svg?branch=main)](https://github.com/23R0534ZXT/kogarasu/actions/workflows/containers.yml)

Kogarasu Host is a local forensic investigation workspace for incident responders.
Read Windows artifacts, Linux logs, disk images and tabular exports in one case.
A finding can take you back to its source row, file and reader. Bookmarks, notes and
row marks stay attached to those records when you regroup a collection or export the case.

[Quick start](#quick-start) · [Investigation workflow](#investigation-workflow) · [Deployment](deploy/host/README.md) · [Reader coverage](docs/host/LINUX-READERS.md) · [Qualification](#qualification-and-scope) · [Release notes](docs/development/RELEASE-NOTES.md)

![An analyst reviews a High-marked service installation (Windows Event ID 7045) in the synthetic Northwind case](docs/assets/host/host-workspace.png)

## Quick start

On a workstation running Docker with Linux containers, start the stable release with one command.
Host serves one local analyst. The loopback binding keeps the interface on that workstation.

```bash
docker run --pull always -d --name kogarasu --restart unless-stopped -p 127.0.0.1:8080:8080 -v "$HOME/kogarasu-cases:/data/cases" -v kogarasu-plugins:/data/plugins ghcr.io/23r0534zxt/kogarasu:latest
```

Open <http://localhost:8080>. Case folders are under `$HOME/kogarasu-cases`. Docker keeps
presentation plug-ins in the named volume `kogarasu-plugins`. On Linux, use `sudo docker`
if your account requires it. On Windows PowerShell, use `"${HOME}/kogarasu-cases:/data/cases"`
for the case mount. Check the running version and status at <http://localhost:8080/health>.

### Try a first case

1. Save [demo.csv](examples/demo.csv) with GitHub’s **Download raw file** control. On the
   Host start screen, select **New case…**, enter a name and choose **Create**.
2. Select **Import evidence → Import a file… → Choose a file…**. Open the CSV, inspect the
   preview and select **Import**. The **Analyses** grid contains 80 records from `WS-LAB-01`.
3. In **Analyses**, leave the search scope on **This grid**, enter `Interactive logon` and
   press Enter. The grid shows 20 matching events. Open **Row details** to inspect the
   fields of a selected record.

For a larger exercise, the [Windows 11 sample collection](https://github.com/23R0534ZXT/kogarasu/releases/download/test-pack-v2/Fireblade-Sample-Collection-2026-11-18.zip)
contains 183 event logs, Amcache, 60 Prefetch entries and 251 scheduled tasks.
Additional fixtures are available in the [discovery pack](https://github.com/23R0534ZXT/kogarasu/releases/download/test-pack-v1/Fireblade-Test-Pack-v1.zip)
and [raw artifact pack](https://github.com/23R0534ZXT/kogarasu/releases/download/raw-artifacts-v1/Fireblade-Raw-Artifacts-v1.zip).

### Operate the container

| Task | Action |
| --- | --- |
| Check startup | Run `docker logs kogarasu` and check the version reported by `/health`. |
| Stop or resume | Run `docker stop kogarasu` or `docker start kogarasu`. |
| Upgrade | Pull the new image, stop and remove your existing container, then repeat the quick start using its case directory and plug-in volume. See the [rename migration](deploy/host/README.md#upgrading-from-kagarasu) for deployments created before 0.15.1. |
| Select a version | The `:latest` tag follows stable releases. Use a published version tag for a repeatable deployment or `:edge` to follow `main`. |
| Work offline | Pull the image while connected. Then replace `--pull always` with `--pull never` and add `-e FIREBLADE_UPDATE_CHECK=off` before the image name. The image includes the readers and .NET 10 runtime. |

The optional update notice checks GitHub's public releases API and caches the result for
six hours. The release notes identify the changes to review before an upgrade. [Published releases](https://github.com/23R0534ZXT/kogarasu/releases)

## One container per case

The quick start keeps the analyst's cases in one library and supports searches across cases.
For isolated storage, the optional driver opens each case in its own container and mounts
only that case's volume there. The driver manages the Docker socket and stores destruction
certificates outside the case volumes. Use the [driver deployment and upgrade guide](deploy/host/README.md#one-container-per-case)
for the Compose configuration, mounts and release tags.

## Investigation workflow

1. **Open a case and import evidence.** Choose **Import evidence** to import a file,
   parse a folder, or analyze a mounted volume or disk image. **Imports** shows the files
   accounted for, their readers and any partial or unread results. Host reads independent
   files in parallel within the configured resources and applies detected profiles in one
   session save. Choose a grid per file, per artifact family or one combined grid. Changing
   layouts retains the source records and their annotations.
2. **Investigate and tag records.** Filter and group the grid, bookmark rows or add notes.
   Click the leftmost row control to cycle through High, Medium, Low and False positive.
   The star in the column header lets you customize the cycle. Shift-click toggles the
   row bookmark. Right-click a row to record an observation with its date, machine,
   tags, confidence and verdict.
   From an IP cell, hunt across the case or declare an indicator with its source record.
   Save a session to reopen its analysis tabs, active grid, filters and column display.
3. **Reconstruct the sequence.** Use the **Timeline** for cross-analysis chronology,
   **IOC hunting** for indicator matches, and the **Attack graph** for Hayabusa findings,
   ATT&CK mappings, saved tags and row marks. In **Actions & tracking → Investigation log**,
   filter tags, inspect timed connections, and correlate process creation, file creation and
   network records with an explicit process identity on the same host. The correlation
   view opens the exact source rows and reports its scan cap when reached. Tagged temporal
   associations are leads for review.
4. **Track and report.** Record actions, owners, machines and accounts. View actions in
   the current case, across the same client or across the library. Export the incident
   intake form (DOCX), six-sheet follow-up workbook (XLSX), or editable investigation
   report (DOCX). For a read-only deliverable, generate an investigation or client
   report as HTML or PDF.
5. **Close or hand off the case.** **Close case** leaves the case available in the library.
   For handoff, export a portable case with verified hashes. To remove a case,
   **Quick erase** deletes its files. The DoD modes overwrite
   the files and verify the last pass before deletion. Both produce HTML and editable Word
   records outside the case. Deletion frees space in the case filesystem once the files
   are closed and have no remaining links. A VMware snapshot or growing virtual disk can
   retain its size on the physical host. See [erasure limits](docs/host/STATUS.md).

## Investigation layouts

Choose **one grid per file**, **one grid per artifact family**, or **one combined grid**
from the collection settings. A combined grid retains the original fields, source provenance
and a common event clock. **Row details** shows the source file and reader. Right-click a merged
analysis in **Artifacts** to list its source files and select one to narrow the grid. Row marks
and notes follow their source records when the layout changes.

- **Columns and scrolling.** Open **Grid preferences** to reorder, pin or hide columns and
  save the layout for the artifact family. Use **Hide empty** for columns that contain no
  values or **Hidden columns** to restore individual fields. The button in each column
  header lists values and counts for checkbox filtering. **Continuous scroll** loads bounded
  row windows as you scroll. Wide grids also load columns as they enter view.
- **RECmd.** Use **RECmd…** next to **Group…** to sort by category, group by category,
  rule and hive, or review results by collected file. Row details distinguish the hive
  read by RECmd from the imported export and show the batch name when identifiable.
- **Search and navigation.** In **Analyses**, choose **This grid**, **In this case** or
  **Across cases** before searching. Case results show matching fields and link to the
  source row. **Across cases** is available in the single-container deployment.
  **Back** restores the previous workspace view. Grouped views retain a path back to
  their parent groups. Press **Ctrl+K** to find a command by name or shortcut, use the
  arrow keys to select a result and press **Enter** to run it.
- **Timeline.** The UTC chart legend lets you toggle individual data sources. Shortcut (LNK)
  details distinguish the timestamps of the shortcut file from target metadata embedded in
  it. Choose **Use in timeline** next to the timestamp that fits the question you are investigating.

Background jobs expose progress, parser messages and a Stop control where cancellation is
supported. See [Host status and verified coverage](docs/host/STATUS.md).

## Import source and resources

**Import evidence** opens a source chooser for files, folders and disks. **Parse a folder**
and **Analyse a disk or image** offer a slider for the number of workers. The recommendation
and upper limit use the resources available to Host, including Docker CPU and memory limits.
Green shows lighter resource use and red shows the upper range. The choice applies to
that job. Preferences set the default for other imports.

<details>
<summary>Import workflow screenshots</summary>

![Import evidence chooser with file, folder and disk options](docs/assets/host/host-import-source.png)

![Folder import with the recommended three workers selected](docs/assets/host/host-import-folder-workers.png)

![Disk analysis with the maximum four workers selected](docs/assets/host/host-import-disk-workers.png)

</details>

Folder and disk dialogs show the space available in the case filesystem and the
recommended free space before analysis. For a folder selected in the browser,
the first estimate includes room for the uploaded copy. Host refreshes the
estimate once the folder is staged. For disk images, the estimate uses the
logical image size when available. Actual storage use depends on the readers
and analysis layouts.

In VMware, check the physical host's volume or datastore as well. The free
space displayed by Host comes from inside the guest. VMware must also have
room to grow the VMDK and any snapshots. See [storage planning](deploy/host/README.md#storage-for-imports).

## Explore an E01 image

Mount the directory containing the image and all its segments read-only by adding
`-v /path/to/images:/evidence:ro` to the Docker command. With a case open, choose
**Import evidence**, select **Analyse a disk or image…**, then **Explore disk images…**.
Enter the container path, such as `/evidence/disk.E01`. Select a file system, navigate directories, preview bytes and
collect selected files. The case records the original image, partition, path, available
timestamps and the SHA-256 of the extracted copy. Interactive collection supports files
up to 2 GiB. **Analyse a disk…** runs the artifact readers across mounted evidence,
including accessible NTFS `$Extend` entries and the `$UsnJrnl:$J` stream.

## Document templates and local inference

The Office exports include layouts based on the French reference documents. Mount your
organization's templates privately and set the matching path inside the container.

| Export | Environment variable |
| --- | --- |
| Follow-up workbook with the six expected sheets | `FIREBLADE_TRACKING_TEMPLATE` |
| Investigation report | `FIREBLADE_REPORT_TEMPLATE` |
| Incident intake form | `FIREBLADE_IR_TEMPLATE` |
| Destruction certificate | `FIREBLADE_DESTRUCTION_TEMPLATE` |

Use a blank workbook for the tracking template. Word exports reuse the template's styles
and page setup with case-generated content. With one container per case, the driver writes
the erasure certificate, so configure its destruction template on the driver.

The optional **Suggest rewrite** command sends the selected draft to an explicitly
configured private OpenAI-compatible inference service. Set `FIREBLADE_REWRITE_URL`
to its chat-completions URL and `FIREBLADE_REWRITE_MODEL` to the model name. The analyst
reviews the suggestion before saving. Host rejects changes to recognized identifiers and
time literals. By default only the optional GitHub release
check makes an outbound request. Disable it with `FIREBLADE_UPDATE_CHECK=off`.

## Qualification and scope

The [0.15.0 GUI qualification report](docs/validation/reports/20261127-host-0150/README.md) records the browser workflows exercised before the 0.15.1 rename.

The 0.10.0 Docker GUI qualification imported **2,674 source files** into **1,386,061 rows**
and **1,478 source analyses**. The three layouts retained the same row total.

| Layout | Result |
| --- | --- |
| One grid per file | 1,478 grids |
| One grid per artifact family | 56 grids |
| One combined grid | 1 grid with 12,559 data columns |

The review checked source counts, 66,308 original values, independent EVTX counts, filtered
CSV and Excel exports, IOC matches, timeline behavior, notes across layouts and persistence
after container recreation. Layout rebuilding took several minutes on the qualified case.
The evidence and customer Office templates remain private. See the [0.10.0 qualification report](docs/validation/reports/20261127-host-gui/REAL_COLLECTION.md).

The 0.10.1 qualification covers the new investigation workflows and synthetic FAT and NTFS
E01 fixtures. Its 320-file synthetic import comparison measured 34.8 s to 12.4 s in the
per-file layout and 28.3 s to 24.6 s in the combined layout. Timings depend on the evidence,
layout, hardware and available resources. See the [0.10.1 qualification](docs/validation/reports/20261127-host-0101/README.md).

## Host limits

| Area | Scope |
| --- | --- |
| `SRUDB.dat` (SRUM) | The native reader exposes the database's columns. Import a Desktop-produced CSV for the exact `SrumECmd` output. |
| Analyst assistance | Desktop contains its historical analyst assistant. Host offers the explicitly configured draft rewrite command documented above. |
| Interface language | English. |
| Erasure | Quick erase performs filesystem deletion. DoD modes verify the final overwrite. SSDs, journaling filesystems and snapshots can retain copies. |
| Access control | Local, single-analyst operation. Bind the Docker port to loopback. |
| Acquisition | Host reads supported images and artifacts. Use dedicated tools for disk imaging, carving, decryption and OCR. |
| Detections | Treat alerts and inferred links as leads and verify them against the original records. |
| Plug-ins and paths | .NET plug-ins run with the user's rights. Windows paths beyond 260 characters may require `LongPathsEnabled=1`. |

[Host status](docs/host/STATUS.md) · [Reader coverage](docs/host/LINUX-READERS.md)

## Editions

| | **Host** | **Desktop** | **Server** |
| --- | --- | --- | --- |
| Status | **maintained** | frozen at 0.7.9 | planned |
| Runs on | a Linux container, in a browser | Windows x64 | planned Linux Docker deployment |
| Users | one analyst, on their own machine | one analyst | several analysts at once, on the same case or on different ones |
| Cases | persistent case folders; optional container per case | files on disk | one container per case |
| Access control | none — local use only | none | accounts, roles, audit log |

Host and Desktop share the analysis engine and reader toolchain. Host opens Desktop case
folders. Open newer Host workspaces, including sparse combined analyses, with a current
Host release. The Server edition is a planned collaboration deployment. See the
[Server roadmap](#roadmap).

## Desktop

Fireblade 0.7.9 is the final Windows Desktop release.

**[Download Fireblade 0.7.9 — Windows x64](https://github.com/23R0534ZXT/kogarasu/releases/download/v0.7.9/Fireblade-0.7.9-win64.zip)** · [Release notes and SHA-256](https://github.com/23R0534ZXT/kogarasu/releases/tag/v0.7.9)

Unzip and run `Fireblade.exe`; Python, Qt, the parsers and the .NET readers are inside the
folder. Windows SmartScreen or Smart App Control may block the unsigned executable. Verify
the download against the SHA-256 in the release notes. See the [Desktop documentation](docs/desktop).

![The Desktop workspace](docs/assets/fireblade-workspace.png)

## Roadmap

The planned **Server** edition would add shared case work, per-case containers, role-based
access, an audit log and HTTPS. Its design attributes marks, notes and views to the analyst
working in each case. A separate Host design proposes per-case encrypted volumes with
erasure by key destruction. See the [Docker architecture handoff](docs/host/HANDOFF-DOCKER.md).

## Repository

The Python package retains its historical name, `fireblade`.

```text
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

## Develop

For Host development on Linux, use Python 3.12, Node.js for the JavaScript syntax check,
and Chromium for browser tests. From the repository root, install the development dependencies
and run the same format, lint and test checks as the Host workflow.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,web,browser,pdf]'
python -m playwright install --with-deps chromium
python -m ruff format --check src scripts tests
python -m ruff check src scripts tests
for file in src/fireblade/web/static/*.js; do node --check "$file" || exit 1; done
QT_QPA_PLATFORM=offscreen python -m pytest tests -q --ignore=tests/windows --ignore=tests/ui
```

For a targeted run, `tests/web/test_browser_lifecycle.py` exercises case creation,
import, save and erasure on temporary data. Set `FIREBLADE_CHROMIUM` to use a locally
installed browser. Image-specific checks use the Docker image and reference pack described in
the [Host workflow](.github/workflows/host.yml). [Contribution guide](CONTRIBUTING.md)

## Documentation

- [Host status and verified coverage](docs/host/STATUS.md) · [Host audit against Desktop](docs/host/HOST-AUDIT.md)
- [Host deployment](deploy/host/README.md) · [Linux reader coverage](docs/host/LINUX-READERS.md)
- [Desktop documentation](docs/desktop) · [User guides](docs/guides)
- [Architecture](docs/development/ARCHITECTURE.md) · [Timeline Explorer comparison](docs/development/BENCHMARK-0.4.0.md)
- [Release notes](docs/development/RELEASE-NOTES.md) · [Changelog](CHANGELOG.md)

## License

Kogarasu is distributed under the [MIT license](LICENSE). Bundled readers and third-party
dependencies retain their [respective licenses](licenses/THIRD_PARTY.md).
