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

The production Dockerfile cannot build here: its .NET SDK layer redirects to
`westus.data.mcr.microsoft.com`, refused by the network policy. The requested domain addition was
not approved. The temporary qualification image uses the same Python requirements and Host/core
sources but **does not contain .NET readers, Shellbags or Hayabusa**. Its Dockerfile is delivered
with the evidence. Native Python paths are exercised in Docker; this is not qualification of the
complete production image. Public Windows fixtures were downloaded by the pinned test-pack builder;
their external-reader paths remain blocked, rather than being counted as passed.

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
| A completely undated inventory offers a 1970 range | Null extent is formatted as epoch zero. | Explain that a date column must be chosen; do not open a misleading date prompt. |

The timeline now separates **Time range…**, **Centred range…**, **Clear time range**, and **Fit
chart**. A visible range label remains available even with zero matching events. Fitting a chart
keeps the time filter, and clearing the time filter restores the event count. Source-row opening
moves beside event pagination; removing its separate toolbar gives the graph and rows more room.
The visual identity, compact controls and existing chart remain intact.

## Reproduce the browser qualification

The shared browser fixture now accepts an explicit image, starts a container for each service
fixture, mounts only that fixture's temporary parent (case and sibling evidence paths), publishes
only on loopback and removes the container on completion. The test process's UID/GID avoids
root-owned temporary case files. Without the variable the existing in-process test mode is kept.

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

Evidence is delivered in `/workspace/shared/downloads/kagarasu-gui-review/` with before/after
Timeline screenshots at 1920×1080, 2560×1440 and 3840×2160. The initial screenshots captured during
the progress modal are superseded by the `timeline-before-*` captures taken after completion.

- New zoom/selection regressions: both fail before the fix and pass after it.
- Timeline suite after the first UI changes: 18 passed in-process and 18 passed against Docker.
- Undated inventory and range-reset contracts: 2 passed against Docker.
- All-sources-hidden contract: fails before the HTTP fix and passes after it in-process.
- Core/non-web suite: 1389 passed, 49 skipped. Platform and optional-dependency skips remain skips.
- Strict native test pack (CatScale folder/archive, 100000-row volume, tabular exports, upload
  preview/confirmation): passed against Docker. Detailed counts are in `native-recette.json`.
- Broader browser/service suites and interaction coverage: running; results to be recorded below.

## Coverage still requiring the full production image or additional work

External Windows readers and actual Hayabusa detection, production-image lifecycle and driver
qualification, multi-gigabyte stress tests, crash/full-disk failure injection, and a human visual
review of every possible control combination remain outside the evidence above. Existing browser
scenarios for alert presentation and attack graphs use known synthetic alert rows; they do not
validate the detection engine. No claim of exhaustive certification is made.
