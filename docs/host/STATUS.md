# Kagarasu Host — status and what is verified

Kagarasu Host is the maintained edition. The [0.15.0 GUI qualification](../validation/reports/20261127-host-0150/README.md)
records the workflows exercised for this release. The [0.10.0 real-collection qualification](../validation/reports/20261127-host-gui/REAL_COLLECTION.md)
measured 2,674 source files, 1,386,061 rows and a 12,559-column combined grid. The historical
Desktop edition is frozen at 0.7.9. The HTTP API is internal and may evolve.

## What you can rely on

- **The analysis is the desktop's.** The Host imports and reads evidence through the
  same `src/fireblade/core`: same parser foundation, filters, timeline and reports. Host opens historical Desktop cases;
  sparse combined analyses introduced in Host require the current Host.
- **Local by default.** The default configuration keeps case data on the analyst’s machine. Its
  outbound release check contacts GitHub at most every
  six hours. `FIREBLADE_UPDATE_CHECK=off` disables it. An optional private inference service
  receives the selected draft only when the analyst requests a rewrite.
- **The evidence is read, never modified.** Sources are copied into the case and
  hashed; the readers only read.
- **A long command tells you what it is doing** and can be stopped at a checkpoint.
- **Import storage planning.** Folder and disk previews compare available case
  storage with an estimate. Reader output, layout rebuilding and other writes can
  change the final peak. The figure comes from the case filesystem, so a VMware
  deployment also needs a check of the physical volume or datastore that backs it.
  See [storage for imports](../../deploy/host/README.md#storage-for-imports).

## What you cannot rely on

- **The HTTP API.** It may change name, shape or status code between two releases. Only the
  case format on disk is a compatibility promise.
- **Access control.** There is none: the Host is for the analyst's own machine and must listen
  on it alone (`-p 127.0.0.1:8080:8080`). Collaboration, accounts and an audit log belong to the
  planned Server edition.
- **Erasure as a physical guarantee.** The Host offers quick deletion and multi-pass overwriting,
  and writes a certificate stating the method. Deleted data can remain recoverable. SSDs,
  copy-on-write and journaled filesystems can also retain copies after overwriting.
  A future per-case encrypted volume would support erasure by destroying its key.
- **Unbounded scale or instant layout changes.** The latest measured collection has 1,386,061
  rows and 12,559 data columns. Layout rebuilding takes minutes; hardware, source formats and
  query shape affect performance. Fixed analysis-count ceilings have been removed, with
  resource budgets and validation retained.
- **Support.** There is none. The repository is the documentation.

## What is verified, and how

| | |
| --- | --- |
| Imports | every reader exercised on real artifacts, through the page, from the raw reference pack and the Windows 11 sample collection; `SrumECmd` cannot run on Linux, and `SRUDB.dat` is read by Fireblade's own reader instead ([LINUX-READERS.md](LINUX-READERS.md)) |
| Screens | the nine tabs and about fifty dialogs compared with the Desktop ([HOST-AUDIT.md](HOST-AUDIT.md)) |
| Engine and service | Historical qualification recorded 1,342 passes and 23 skips. Subsequent targeted runs cover time fields, reader diagnostics and viewport regressions. The versioned reports give the scope of each run. |
| Client | `tests/web/test_browser*.py` drive the page with a real mouse: every menu command and every shortcut, every dialog's buttons kept on screen, dialogs moved and resized, splitters, filters, grouping, bookmarks, views, colour rules, derived columns, global search, indicator hunt, timeline, actions, reports, export, portable round trip, case creation to erasure |
| One container per case | In 0.15.0, Chromium drove two drivers on separate private networks sharing one rootless Docker daemon. The review created a case, imported two CSV records, reconciled the second driver, reopened the first case, then verified quick erasure and the external HTML and DOCX certificates. Mock-Docker regressions cover upgrades and legacy-container recognition. |
| Language | English interface and standard reports. The investigation DOCX and follow-up workbook retain the French headings of their reference models |
| Detection | Hayabusa 4.3.1 run through the page on the Windows 11 sample (183 event logs, 613 alerts), with the attack graph, the alert context and both reports built from it |
| Docker qualification | The real-collection report covers imports, layout rebuilding and persistence after container recreation. The 0.15.0 GUI report records the per-case driver checks. |

## Why it exists

The same engine behind HTTP is how an analyst works a case without a Windows session, and the
route to the Server edition: one container per case, isolated and erasable as one object.
