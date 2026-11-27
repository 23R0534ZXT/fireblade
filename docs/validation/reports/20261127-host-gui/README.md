# Host GUI review — 27 November 2026

## Revision and limits

Work resumes from `codex/host-gui-review`, `10efc9f242cbe1494ee83faeb1ec08ca4ba2f37b`.
The checkout originally supplied was `work` at `9e224c6`; it was clean and was preserved.
No push, merge or release is authorised or performed.

The previous session's four `/workspace/shared/downloads` attachments were absent. Its Git commits
and the repository's Host audit, parity, architecture and recette documentation were read instead.
The named Superpowers, Autonomous Senior Engineer, Kagarasu Engineering and Playwright Interactive
skills were absent from the exposed catalogues and accessible skill directories. The installed
Cloud environment runtime and Cloud desktop skills were applied. Shared desktop control failed
with `the gaas-browser node_repl sandbox cannot be disabled`; Chromium through Playwright works.

The production Dockerfile cannot build from its .NET base images here: the SDK layer redirects
to `westus.data.mcr.microsoft.com`, refused by the network policy. A domain addition was not
approved. The first qualification image therefore used only the Python requirements and Host/core
sources. It does not qualify external readers.

A complete alternative was subsequently retrieved through the allowed GHCR registry: published
Host 0.9.4 at `sha256:dcf00d578e08903edde1df0364036b5a60ae4c15b255f208ba122fd9fed5d10f`
(OCI source revision `9e224c6e391b0c06f4482f2dc9410c4cd816372f`). A second Dockerfile overlays the
current branch's core, runtime, web, version and project metadata, preserving the published .NET
readers, Shellbags and Hayabusa. `kagarasu:qualified-host` is the resulting complete qualification
image. Both Dockerfiles are delivered. This is **not** a clean rebuild of the production Dockerfile;
the recipe and reader tests below identify which image they use. No network settings were changed.

## Architecture used for the changes

- `core`: DuckDB cases, string-preserving imports, views/conditions/sort/group compilation,
  annotations, case workspace, forensic parsers, timeline index, exports and provenance.
- `web/service.py`: case lifecycle, engine access, views, imports, timeline and job coordination.
- `web/server.py`: FastAPI contracts, uploads/downloads and static application serving.
- `web/static/app.js`, `index.html`, `app.css`, `windows.js`: stateful desktop browser workspace,
  menus and dialogs, paged grids, source tree, timelines, hunting, tracking and window geometry.
- `web/agency.py`: optional Docker driver; distinct from the single-container Host used here.
- `ui`: historical Qt Desktop, untouched. Existing architecture documents still call it the
  reference; this review follows the user's direction to develop Host.

## Reproduced defects and changes

| Defect | Reproduction and cause | Result and regression contract |
| --- | --- | --- |
| Wheel zoom grows stronger after refreshes | Repeated chart redraws append wheel listeners to the same node. An identical wheel gesture changes the span from 42 to 3 buckets in the failing test. | Replace the handler on redraw; preserve the pointer's bucket offset after zoom. Same gesture has the same effect after redraws. |
| Selected event loses its highlight | Select a row, then zoom. The DOM is rebuilt without restoring the selection, while the source-row command retains the old identifier. | Restore the highlight when the event remains on the page; clear selection and disable source-row opening when filtered out. |
| Hiding every source brings all events back | An empty selected-source list becomes `sources=`; the HTTP parser treats the empty string as no restriction. The export shares that parser. | Omitted sources mean all; explicitly empty sources mean none. Browser regression checks zero events, header-only CSV and restoration of all sources. |
| Slow source-row reads replace a newer event | Open one row, close its dialog, open another, then release the first delayed response. | Only the latest request for the current case may update the visible source-row dialog; late errors are ignored too. |
| A completely undated inventory offers a 1970 range | Null extent is formatted as epoch zero. | Explain that a date column must be chosen; do not open a misleading date prompt. |

The timeline now separates **Time range…**, **Centred range…**, **Clear time range**, and **Fit
chart**. A visible range label remains available even with zero matching events. Fitting a chart
keeps the time filter, and clearing the time filter restores the event count. Source-row opening
moves beside event pagination; removing its separate toolbar gives the graph and rows more room.
The visual identity, compact controls and existing chart remain intact.

The IOC summary now fits a short list instead of reserving 34% of the workspace for empty space.
A long list keeps its scroll area and height cap. A desktop browser contract checks four indicators
and then a real 120-indicator hunt, with more room retained for evidence details in both cases.

## Reproduce the browser qualification

The shared browser fixture now accepts an explicit image, starts a container for each service
fixture, mounts only that fixture's temporary parent (case and sibling evidence paths), publishes
only on loopback and removes the container on completion. The test process's UID/GID avoids
root-owned temporary case files. `--plugins` points into the same writable temporary volume;
changing the parent Python process environment cannot reconfigure an already running container.
Without the variable the existing in-process test mode is kept.

```bash
docker build -t kagarasu:qualification .
FIREBLADE_TEST_IMAGE=kagarasu:qualification \
FIREBLADE_CHROMIUM=/usr/bin/chromium \
FIREBLADE_SCREENSHOTS=/tmp/kagarasu-captures \
FIREBLADE_JS_COVERAGE=/tmp/kagarasu-coverage \
.venv/bin/python -m pytest tests/web/test_browser*.py tests/web/test_parity_grid.py -q
```

Screenshots record the final state of successful shared-fixture browser scenarios; they do not
prove that every captured control was exercised. `scripts.audit.controls` measures touched
controls separately. Neither event coverage nor line coverage proves forensic correctness.
JUnit files, scenario assertions, count comparisons and downloaded outputs supply that evidence.

## Validation evidence

Evidence is delivered in `/workspace/shared/downloads/kagarasu-gui-review/`, including JUnit XML,
raw logs, a consolidated test inventory, provenance, expected counts, screenshots and Dockerfiles.
The screenshots come from running containers. Before/after Timeline views are available at
1920×1080, 2560×1440 and 3840×2160; the IOC before/after pair is at 1920×1080. Desktop light/dark
sweeps and real EVTX/Hayabusa/graph views supplement the scenario captures.

| Check | Observed result | Scope |
| --- | --- | --- |
| Core and non-web baseline | 1389 passed, 49 skipped | Initial optional/platform exclusions retained in raw XML |
| PDF tests after installing the declared optional dependency | 25 passed | Clears 11 of those skips; 14 other cases were already passed |
| Browser groups against Python Host images | 80 passed / 12 skipped; 128 passed; 199 passed / 2 failed | First group lacked host-side pypdf; two plugin tests needed a writable container plugin folder |
| Browser retry after prerequisite/harness correction | Imports + IOC: 22 passed; plugins: 2 passed | Clears the 12 skipped cases and both plugin failures; includes the new IOC layout contract |
| Final Timeline contracts against Docker | 21 passed | Wheel, selection, range, empty sources, exports, undated rows, late source reads |
| Import contracts on complete qualification image | 7 passed | Includes cancellation, folder upload, workbook sheet and CSV preview |
| Web service/contracts | 250 passed | API, persistence, errors, formatting, lifecycle and regression tests |
| Complete qualification image | 14 passed | Actual readers, EVTX context, Hayabusa detection and graph |
| Strict native recipe | 32 checks passed | CatScale folder/archive, 100000-row volume, exports, upload preview |
| Strict complete recipe | 47 checks passed | Adds public EVTX, Shellbags, WebCache, detection and graph |
| Formatting, lint and client syntax | Passed | Ruff check/format, Node syntax, git whitespace check |

Consolidation by unique test ID gives **2087 passed, 24 skipped, no unresolved failure** across
2111 distinct test cases. This is a union of baseline and targeted verification, **not one green
monolithic test run**. `results-consolidated.json` names its inputs and `test-inventory.tsv` gives
every test's latest result and report. Raw failed/skipped runs remain available. An initial local
Web run was interrupted in favour of the Docker runs; it is not counted as a successful suite.
Its cancellation failure read an intermediate row-count status during case reload; the browser
contract now waits for the actual cancellation outcome. The complete-image import rerun passes.

The 24 remaining skips require actual .NET compatibility helpers/fixtures, a Windows-specific
integration or encoder, a real SRUM sample, or the pre-existing 3 GiB dataset. They are listed in
the inventory; they are not counted as successful coverage. These differ from the 14 complete
Host-image tests above, which do run with the published image's readers.

### Business workflows exercised

| Area | Checked behavior | Primary browser contracts |
| --- | --- | --- |
| Analyses and grids | Sorting and priority, nested groups, bookmark groups, drag/reorder, filter combinations, date filters, summaries, empty/hidden/restored columns, selection and notes, pagination, layouts and saved views | `test_parity_grid`, `test_browser_layouts`, `test_browser_commands`, `test_browser_remaining`, `test_browser_effects` |
| Artifacts and workspace | Tree organization/search, open/close/reorder analyses, row/cell details, panel sizing, geometry, keyboard menus and settings persistence | `test_browser_workspace`, `test_browser`, `test_browser_rightclick`, `test_browser_parity_more` |
| Cases | Create/edit, save/history, archive/restore, portable export/import, guarded erasure and certificate | `test_browser_cases`, `test_browser_lifecycle`, `test_browser_portable`, `test_browser_destroy` |
| Imports | File/folder upload, preview, delimiter, workbook sheet, report/retry, set-aside, deletion refusal and cancellation | `test_browser_import`, `test_browser_imports_tab`, complete-image reader tests |
| Timeline | Correlation, date choices, lanes, selection, zoom/pan/overview, period filtering, pagination, exports and source evidence | `test_browser_timeline` |
| IOC hunting | Defanging/normalization, known counts, filters, scope, saved hunts, selection, pagination, exports and source rows | `test_browser_ioc_hunt`, `test_browser_tracking`, `test_browser_scenario` |
| Hayabusa | Real detection, findings counts, clock/heat/chain views, rules, bookmarking, EVTX context and original event | `tests/image/test_image_detection`, `test_browser_findings` |
| Attack graph | Cards/edges tied to evidence, selection, zoom, free nodes, ATT&CK layer and PNG exports | `test_browser_graph`, complete-image detection tests |
| Actions, reports and preferences | CRUD, statuses and filters, CSV, client/mission data, HTML/PDF and report options, themes, scale and stored configuration | `test_browser_tracking`, `test_browser_commands`, `test_report_options`, `test_browser` |

A separate desktop sweep hunted `192.0.2.1` in 700 known events: **140 expected matching fields,
140 observed details**, no page error. Hiding all timeline sources yielded zero events and a
header-only CSV; showing all restored 700. Recreating the container with its retained volume kept
700 rows, the selected bookmark and its exact note. The original CSV SHA-256 stayed identical.
The same case was reopened again after switching to the complete-reader qualification image.

### Visual and interaction audit

The menu tour recorded 97 states at 1920×1080, with no JavaScript page error. Its 72 lint findings
are **not 72 product bugs**: 63 compare open popup menus against the controls deliberately behind
them, and 9 instances concern missing accessible labels on generated expression/color controls.
The latter remain a documented accessibility follow-up. The two refused requests were read back:
no annotations to export, and EVTX context requested on an ordinary CSV row. Both returned their
specific explanations; neither represents a failed evidence read. The tour and the semantic
browser assertions serve different purposes.

The browser event inventory records **373 of 445 static control keys touched**. The remaining
72 keys are listed in `control-coverage.txt`; some duplicate alternate entry points or hidden
inputs, but they are not claimed as tested. The menu tour and separate complete-image tests are
not included in that counter. This pass is substantial functional coverage, not proof that every
button, native file-picker behavior or possible feature combination has been qualified.

The old V8 recorder hashed scripts from the mutable checkout rather than the code loaded in the
browser. This is wrong when a Docker image serves an earlier revision. It now hashes the exact
CDP script source and drops unidentifiable scripts. The proof deliberately serves an older image
and checks that its recorded hash differs from the checkout and matches the image. Historical
JavaScript line-coverage percentages from the broad run are provisional and are excluded from
qualification claims. Control-event records do not depend on those byte offsets.

## Remaining qualification work

- A clean production Dockerfile rebuild and full multi-container driver qualification.
- The 72 untouched static control keys and missing accessible labels identified above.
- Multi-gigabyte GUI workloads, memory ceilings and long running investigations. The 100000-row
  recipe took 12.1 seconds in the complete image; that observation is not a universal benchmark.
- Crash, disk-full, interrupted-write and malformed-artifact campaigns beyond the existing tests.
- A sustained human review of all feature combinations and native drag/file-dialog behavior.

No push, merge or release was performed. The code changes are local commits on the requested
branch. The retained live Host uses the complete qualification image, with synthetic/public data.
