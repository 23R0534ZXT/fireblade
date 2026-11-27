# Host GUI review — continued qualification, 27 November 2026

This pass continues the [first review](README.md), on `codex/host-gui-review` after `a785e34`.
All commits remain local. No push, merge, release or `main` modification was performed.
The same installed Cloud runtime/desktop skills and the same Playwright fallback apply.
Evidence is in `/workspace/shared/downloads/kagarasu-gui-review-continued/`.

## Defects reproduced and corrected

| Problem | Cause and correction | Verification |
| --- | --- | --- |
| Removing every priority sort leaves the grid sorted | The dialog emptied the priority array but retained the active sort. Clear both. | Actual before/after grid: `alice,bob,carol` becomes original `bob,alice,carol`; no sorted header remains. |
| Client reports ignore selected content options | The background task omitted analyst/findings/coverage arguments. Forward them to the report generator. | Downloaded report content and exclusions checked through the GUI and service tests. |
| Late malformed quoted CSV silently loses evidence | DuckDB accepts 100000 valid rows and drops a final unterminated quoted record outside its sample. Detect quotes during the existing hash pass and validate quoted records before ingesting them. Use a bounded Python delimiter sample, including with a 64 MB engine budget. | The same 100001-record fixture previously appeared successful; now import fails with diagnostics and creates no analysis. Valid quoted/delimited imports and low-memory export pass. |
| Large constrained imports unexpectedly use the native transaction path | Automatic file-based budget inflation raised the streaming threshold; changing only the threshold did not solve it. Preserve the explicit constrained budget for huge inputs; select streaming at the corresponding threshold. | Real 3.04 GB import, counts, filters, paging and source hash verified; performance tradeoff below. |
| Empty/failed imports report misleading success | Zero-byte previews were accepted; confirmation overwrote failures with `0 file(s) imported`; partly read folders counted failed runs as read. Reject empty previews, disable confirmation when every preview fails, preserve outcomes and count actual produced analyses. | GUI tests: empty file, late invalid UTF-8, late malformed quotes, one valid plus one failed file. Header-only tables remain supported. |
| Interrupting IOC hunting promises unpublished partial results | Core cancellation rolls back the current hunt. The message incorrectly promised partial results. Explain that the incomplete hunt is discarded and previous saved hunts remain. | Interrupt a running hunt over 500000 rows through the GUI; no incomplete result is published. |
| Generated exports accumulate, including failed downloads | Temporary files lacked response cleanup; translation failure could retain the output and `.part` file. Clean on transfer completion/disconnection and failed generation. | Success, simulated write failure, disconnected client, and real full `/tmp` tests. |
| Changing layout can close or reopen an analysis during an active read | A row response continued painting after its connection closed. Other grid endpoints could also reopen the database during reorganization. Serialize analysis access and lifecycle changes per case, using a reentrant gate; skip busy cases during cache eviction without holding the global job lock while waiting. | Deterministic concurrency regressions, independent-case access with a full cache, and the million-row Docker GUI layout sweep with HTTP error tracking. |

Expression, condition, summary and palette controls now have usable accessible labels. The
unused hidden import input was removed. The existing desktop visual identity and density remain.

## Additional functional coverage

The GUI tests now verify resource/date/copy/pin preferences and reload persistence; client
fields; expression/condition logic; rule colors, fonts, import/export and global scope; top-25%
statistics against a known 12-row population; report limits, findings and coverage switches;
custom coverage plan; summary hiding; IOC result pagination/limits; collection retry filters;
subtabs; cancellation; selected Timeline correlations and a report containing exactly two selected
events and its chart. Hayabusa tests actually edit/save/reload/reset YAML and open an original EVTX
event through its cell context menu. The prior full application inventory remains in the first report.

`control-coverage.txt` records **444/444 distinct static control keys touched** across actual
browser events. The previous inventory had 445; the unreachable duplicate file input was removed.
The coverage collector stores actual CDP script hashes and aggregates previous event evidence.
This is reachability/event coverage, not proof of every option combination, native OS color/file
picker, or forensic result. Assertions, exports and expected counts supply result verification.

## Large volume, failures and persistence

The deterministic generator produces **1000000 rows / 3043888920 bytes** with 20 hosts, five IPs
and a 3000-character payload. SHA-256:
`09ae46979e04b104da433e428f81102e08e28bbe5cc8ac7b7d63dea75557f4a6`.
The GUI verifies exactly 200000 rows for `192.0.2.1`, including a second page. Two-level grouping
by Host/SourceIp yields 20 groups of 50000; the downloaded group counts total 1000000.
The three layout modes each retain 1000000 rows, with no observed JavaScript or HTTP errors.
The final sweep takes 99.26 s for artifact families, 100.72 s for the combined grid, and 1.19 s
for individual files. Screenshots are actual 1920×1080 browser captures.

| Measurement | Original path | Constrained streaming path |
| --- | ---: | ---: |
| Import wall time | 35.27 s | 190.69 s |
| Peak sampled process RSS | 4556240 KiB | 1416740 KiB |
| Rows after import | 1000000 | 1000000 |
| Filtered rows | 200000 | 200000 |
| Source hash after operations | unchanged | unchanged |

These are single-workload observations with concurrent qualification activity, not a general
benchmark or a strict memory ceiling. Explicit budgets up to 512 MB trade speed for lower RSS:
about 69% less sampled RSS here, about 5.4 times slower. Default/larger budgets retain the original
native threshold. An intermediate threshold-only experiment did not reduce RSS and was rejected;
its raw results remain available.

A SIGKILL during parsing followed by container recreation preserves a baseline 10-row case and
publishes no analysis from the interrupted import. A separate GUI save/recreation check retains
700 rows and the exact bookmark note. The source hashes remain unchanged. The full-disk experiment
uses an isolated 64 MB `/tmp` tmpfs: a 2060905-byte export succeeds, a second fails explicitly with
ENOSPC after filling the tmpfs, leaves no temporary exports, then produces identical bytes after
space is freed; all 2000 source rows remain accessible.

Repeated large layout changes are expensive (temporary disk use and materialized intermediate
results); this pass qualifies correctness and concurrency, not instant reorganization or bounded
historical storage. No performance claim is made for arbitrary forensic collections.

## Verified results

Consolidation gives **2121 passed, 24 skipped, no unresolved failure**, over all **2145 current
collected test IDs**. This is a union of baseline and targeted reruns, not one monolithic run.

| Verification | Result | Evidence |
| --- | --- | --- |
| Non-web/core after constrained-import correction | 1402 passed, 24 skipped | `recovered-core.xml` |
| Web contracts and additional browser/desktop contracts after lifecycle protection | 307 passed | `lifecycle-api-verified.xml` |
| Final route tests, including positional/default/keyword access and concurrency | 79 passed | `routes-lifecycle-final.xml` |
| Focused lifecycle races and independent busy cases | 7 passed | `lifecycle-concurrency.xml` |
| GUI Timeline/IOC/import/deep-report regressions on complete Docker Host | 53 passed | `final-gui-regressions.xml` |
| GUI import outcomes/final controls/sort on Docker | 15 passed | `final-docker.xml` |
| Complete-image reader, detection and source-event tests | 16 passed | `lifecycle-image.xml` |
| Final delivery-image GUI review/workspace/control rerun | 32 passed | `delivery-browser.xml` |
| Final delivery-image reader/detection rerun | 16 passed | `delivery-image.xml` |
| Strict native/reader recipe | 47 checks passed | `final-recette.json` |
| Large-volume layouts and group export | 3 modes, 1000000 rows, 20 exact groups, zero observed HTTP/JS errors | `million-grid-modes.json`, Docker log, CSV and captures |
| Full temporary disk and recovery | Explicit ENOSPC, no retained partial output, identical export after recovery | `disk-full.json` |
| Lint, format, client syntax, whitespace | Passed | final quality log |

Counts overlap; they must not be added. The consolidated inventory identifies each unique case.
The final delivery-image browser and reader reruns are also included in the delivered inventory.
The continuation adds 154 actual screenshots; the first archive retains its 572 captures.

## Evidence and reproducibility

`results-consolidated.json` and `test-inventory.tsv` identify the latest verified result by unique
test ID. Raw unsuccessful runs are retained separately: delimiter validation initially exceeded
low-memory limits (fixed), a test workspace ran out of disk (excluded and rerun), the first layout
sweep missed HTTP errors (superseded by explicit response tracking), and disconnected-response
qualification needed its own event-loop thread when Playwright already owned the main loop.
Temporary synthetic pytest workspaces and unused qualification images were cleaned after retaining
reports. No user investigation was removed.

The complete qualification image overlays branch sources on the same pinned GHCR Host 0.9.4
base documented in the first report, retaining .NET readers and Hayabusa. The compact one-COPY
Dockerfile and build instructions are included with evidence. This does not resolve the network
restriction preventing a clean production Dockerfile rebuild. The optional agency Docker driver,
Windows-only helpers and remaining platform-specific skipped cases are not certified here.

Before/after captures: `sort-before-1920.png`, `sort-after-1920.png`,
`truncated-before-1920.png`, `truncated-after-1920.png`. Large-volume captures:
`streaming-large-million-rows.png`, `streaming-large-filter-200000.png`,
`million-layout-{artifacts,combined,files}.png`, `million-two-level-groups.png`.
Generator, scenario scripts, expected counts, JUnit reports, raw logs, manifests and the local
patch/commit list accompany the archive. The first archive is preserved unchanged.
