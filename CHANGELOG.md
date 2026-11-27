# Changelog

All notable changes to Fireblade are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/); the case format on disk is the compatibility promise.
The full notes of each release are in [docs/development/RELEASE-NOTES.md](docs/development/RELEASE-NOTES.md).

## [Unreleased]

### Added
- Host analysts can nest grouping levels by dragging column headers, reorder them in the grouping
  dialog, and use the bookmark column to group marked and unmarked rows.
- The Host column manager can find columns by name, count hidden columns, and hide columns that
  are empty across the entire analysis.

### Fixed
- Host refreshes open grids when the import layout changes, persists restored column visibility,
  opens the retried analysis, and retains column settings when recovering an earlier session.
- Timeline CSV exports apply the active filters. Timeline, Hayabusa, and graph results follow the
  open case even when an older request finishes late.
- The timeline can index an analysis while its grid is open. Action results follow the active case
  and the selected scope, and late progress responses stay with their original task.
- The container ships PDF text extraction, the per-case driver forwards grid query parameters,
  and key controls stay accessible in narrower browser windows.
- Host menus and context menus stay within the viewport. Compact workspaces put Artifacts in a
  drawer, keep controls reachable at high interface zoom, and resize relocated panels from their
  actual dividers.
- Opening another case clears the previous case’s IOC and import results. Late case and import
  responses can no longer replace the current selection.

## [0.9.4] — 2026-11-26

### Changed
- **The layout step names the family it is merging and counts families** (see 0.9.3 notes below for the
  related import fixes): "[3/40] Registre — Disk import · 5,247 records written…" instead of counters that
  restart for each family.

## [0.9.3] — 2026-11-26

### Changed
- **The layout step says where it is**: the progress shows the family being merged ("[3/40] Registre — Disk
  import · 5,247 records written…") and counts families (3/40) instead of staying on "1236/1236" while the
  record counters start again for each family, which looked like a loop.
- **Faster layout step**: merging a collection by family no longer opens each analysis twice (the columns are
  read from what the import already recorded): 1245 files, 121 s → 80 s in the same test.

### Fixed
- **A collection of 1000+ files no longer stalls at 99 % in a huge merged table.** When "one grid per file"
  would make more than 1000 grids, files with exactly the same columns are now merged into one grid (1245
  files of 300 shapes make 300 grids, no row lost, no wider table); only if there are still too many
  shapes does it fall back to one grid per artifact family, then to one grid.
- **"One grid per artifact family" on a family with thousands of columns no longer stalls at 99 %.** A family
  whose merged table would pass 3000 columns (a thousand files of many shapes) is laid out as one grid per
  shape — files with exactly the same columns — and the import says so.
- **Timeline**: overlapping reads (a search typed while a window loads) no longer let a slower, older answer
  repaint an older state: only the latest read paints.

### Changed
- **SRUM on Linux reads like SrumECmd**: the providers SrumECmd also writes come out with its columns, its
  order and its names (`Id`, `Timestamp`, `ExeInfo`, `Sid`, `BytesReceived`…), so the profiles and searches
  apply to either reader's tables. The user name behind a SID, the description and timestamp of an
  executable and the network profile name stay empty rather than guessed. Other tables are unchanged.

## [0.9.2] — 2026-11-26

### Added
- **The disk is checked before an import starts**: the size and file count of the source against the free
  space where the case is stored. An import that cannot fit is refused with the figures (nothing is written);
  a tight disk starts and says so in the log.
- **An import cut short keeps what it wrote.** If the disk fills (or the run crashes) after some analyses
  were written, they are added to the case and the message says why the rest is missing; if none was
  written, the message says "Nothing was imported".

### Fixed
- **More grids than a case can open no longer ends with an empty Analyses tab.** "One grid per file" on
  more than 1000 files read everything, then the case refused the 1000+ grids and showed nothing. The
  collection is now laid out by artifact family (or as a single grid if that is still too many) from the
  grids it already wrote, and the import says so. "One grid per file" after the fact is refused with the
  reason when it would not fit; the layout selector changes the layout of what is already imported.
- **Timeline**: one request at a time reads or replaces the index ("Connection already closed").
- **An import of a very wide file no longer spins at 99 %.** Merging a family of a big collection
  gives thousands of columns; the native CSV reader exceeded its memory budget and the import fell
  back to row-by-row inserts (hours). It is now read natively with a budget that follows the width
  (one thread, at most three times the configured memory), in seconds; the fallback stays as the last
  resort. The layout step reports its progress and honours a stop between analyses.

## [0.8.8] — 2026-11-26

### Added — parity with the desktop (found by replaying its commands on the Host)
- **Sorts compare as the type they are given** (text, number, ISO date), per key, as the desktop's sort type does:
  100 now comes after 9 when the column is sorted as numbers. A saved view keeps the type.
- **The export is the desktop's export**: the filtered, sorted, visible columns (no provenance columns),
  the group counts, and the bookmarks-and-notes export with their notes. A refusal is said in the status line.
- **Group footers and global summaries**: where each summary's footer is shown, the totals line, the group
  footer mode. **Saved views** keep the whole view: expression, typed sorts, summaries, totals, footers, order,
  highlight.
- **The IOC hunt is the core's hunt**: indicators normalised (a defanged address is read as an address) with their
  fields and rows counts, details with source date and excerpt, pages of 250, "All IOCs", Interrupt, a detail
  limit, saved hunts replayed from their store, a double-click on a detail opens its source row, an export in
  English with a verified receipt. Importing a list fills the box; the hunt is a gesture of its own.
- **Timeline**: Correlate, Exact value, Bookmarks, a preset duration (15 min – 7 days), sliding arrows; Build /
  refresh reads the analyses again; the rows without a date start included, as in the desktop.
- **Investigation report options**: the filters each analysis saved, only the selected rows, the timeline's chart,
  the findings limit, and the last coverage check.
- **Client and mission** (client, reference, sector, contact, contract, lead, dates, notes), the findings level
  filter, the expected families of the coverage check (and Interrupt), the text filter expression, Reset the view.
- **Preferences**: custom date format, row-details position (bottom / right / top), copy on right-click (Shift opens
  the menu), default pinning, auto-profile, memory and threads. The date columns are written by the core's own
  functions, and the recognised profile (with its derived columns) is applied when a table is imported.
- **Columns**: reorder them (earlier / later), give each a width, and the order is kept with the analysis and in the
  layout file. **The Artifacts tree** groups by collection and artifact family, or lists by collection, folds and
  unfolds, and sits on the right or on the left.
- **Colour rules** carry the rest of the desktop's rule: italic, underline, strike-out, font and size, which parts
  they apply (background, text colour, font), stop at the first match, the statistic's options, the axis.
- **Import report**: tick files (all / none) and read them with one reader; filters for the files imported and the
  duplicates. The cell menu offers to edit the note of a selection that already has one.
- **Every command of the desktop's menus is accounted for**: `docs/host/desktop-menu-map.json` lists the 126
  commands read from the real window against the Host's page (or the reason a browser has none), and a test keeps
  the map and the window in step.
- The files read only by the generic reader stay on the retry list, so a reader the analyst names can read them
  better.

### Fixed
- Filtering or excluding on a cell **appends** to the column's filters, as the desktop does.
- The search text is highlighted with the highlight text.

## [0.8.7] — 2026-11-26

### Fixed
- **A new case opens at once**, as in the desktop, instead of waiting in the Cases list.
- **The attack graph places techniques on the kill chain.** Hayabusa 4 writes tactics in short form
  (`Exec ¦ DefImpair`); only the full names were recognised, so no technique ever had a tactic.
- **The PDF keeps the report's structure.** Bold headings, real table columns with the header
  repeated on every page, summary tiles in reading order, page numbers, and `→` is no longer a `?`.
  The client report names each analysis by its file instead of a path on the server.
- **IOC hunt:** a line the parser rejects (`backdoor` is not a domain) is listed as "not searched"
  with its reason, not shown as "no hit"; the hunt covers the whole case by default, like the desktop.
- **Folder import:** the preview counts every file (it stopped at 200), and the message says how many
  files were imported rather than "1".
- **Names:** "Linux — journaux" is "Linux — logs"; Prefetch tables are "Prefetch" and "Prefetch
  timeline" rather than "PECmd_Output"; two files of one name are told apart by their folder, not "(2)".
  Exported files are named after the case and the analysis.
- **Global search** runs on Enter, and on a case of hundreds of analyses it is a job with progress and
  a Stop (it was one silent request, quadratic in the number of analyses).
- **Detection:** reopening a case no longer says "No detection run yet" above its findings.
- **Imports:** transaction logs beside a hive are no longer counted as "not read"; the failure reason
  of an engine says "log", not "journal".
- The toolbar scrolls in a narrow window, long names in the artifacts tree are cut with an ellipsis,
  and "Collection coverage" no longer causes a 400 when no check has been kept yet.
- **A portable case keeps the names of its files.** The package renamed every source `0000.pf`,
  `0003.db`…, so the imported case showed those numbers as analysis names; sources now travel under
  their own name (a name Windows would refuse falls back to its number), and the download is named
  after the case.
- **Disk analysis** speaks English while it works, and a path that does not exist is refused with a
  plain message instead of an internal "RawLoader" one.
- **Coverage check** names each finding by its analysis (it showed internal file names), and the
  About box no longer says the import "is not wired yet".
- **History** lists each recorded state by what it holds ("Case state — 482 analyses, status open")
  rather than by a hash file name; the file name is in the tooltip.
- **Detection rules** no longer lists the engine's 13 field-mapping files (no level, not rules).
- **The timeline's event summary** leaves out the path of the evidence file and Fireblade's own
  columns, and reads the payload and provider of an event.
- The disk workspace folder is `Disks`, not `Disques`.
- `scripts/fetch_readers.py` counted the Hayabusa rules without looking in sub-folders ("0 rule(s)").

## [0.8.6] — 2026-11-25

### Added
- **The attack graph proves what it shows.** Every card and every link opens its evidence: what it
  represents, how Fireblade got it (the column or the record it was read from), and the alert groups
  behind it with the row identifiers of the alert analysis. A row chip shows the exact line the
  detection engine wrote, and "Show in the grid" opens those alerts. What the analyst entered by hand
  (a machine, an indicator, a free node) says so and shows its record. The graph is redrawn in
  columns along the attack chain, with badges that carry each link's alert count.
- **The cell right-click menu is complete.** Added the desktop's cell note, bookmark / note, note on
  the selection, "search every analysis for this value" and "correlate this value across the case".

- **Parity with the desktop's menus.** Found by walking every command of the desktop window (126) against
  the Host: the text filter expression (`Contains([User], 'a') And [ID] >= 10`, parsed by the desktop's
  own parser), Reset the view, and the Hayabusa sources pointer.

### Fixed
- **Filtering on a cell appends, as the desktop does.** Excluding two values of one column now keeps both
  exclusions; the Host used to replace the first. Found by replaying the same commands on the desktop window and
  on the Host (`tests/web/test_parity_grid.py`: 35 commands compared row for row).
- CatScale family names ("Utilisateurs", "Processus et réseau"…) are English in the Artifact column
  and in the timeline; the reasons of a file read by two missing engines are translated; the severity
  counts of the findings tab are spaced and coloured.

## [0.8.5] — 2026-11-25

### Added
- **Everything a collection holds is read.** A file no dedicated reader owns used to end as "No reader
  recognised this file" — 1 900 of 2 600 files of an offline collector. It is now read as what it is:
  a SQLite database (every table), Firefox's compressed JSON and any JSON (flattened), a text file
  (one row per line), and the binaries — executables, libraries, opaque data — in one *Files inventory*
  (size, dates, SHA-256 and, for a PE, machine, compile time, subsystem, signature present). A database
  no SQLECmd map knows is read table by table. The desktop is unchanged.

### Changed
- **The layout select (one grid per file, per artifact family, one grid for everything) changes the
  view of the case.** It only applied to the next import and did nothing on what was already
  imported: it now lays the existing imports out again, without reading them again.
- The EVTX detection tab is gone: it ran the very detection the Hayabusa findings tab runs. The
  findings screen says how many event logs the case holds.

### Fixed
- **The sort arrow and the "sorted" highlight were drawn on the column to the left of the one clicked**
  (the data was sorted by the right column, the header said otherwise).

## [0.8.4] — 2026-11-25

Every control was pressed again and judged by what it leaves on screen, on the real image with a real
pack and real collections. Most of what follows is what that found.

### Added
- **Archives inside a folder are opened.** A `/var/log` with sub-folders and, here and there, a zip, a tar,
  a `.tar.gz`/`.tgz`/`.tar.bz2`/`.tar.xz` — even an archive inside an archive — is read whole: each
  archive is unpacked into the collection's own work folder (the evidence is never written to), its
  members join the inventory, and the Imports tab names them `archive!/path/inside`. Links, devices and
  names that climb out of the archive are refused and reported; a bomb stops at a size bound.
- **SRUDB.dat is read on Linux** (native reader; SrumECmd cannot start outside Windows).
- **Shellbags is read in the image** (523 rows on the pack's hive, the count it states).
- **A comparison icon left of every column filter** (contains, does not contain, equals, differs,
  starts, ends, regular expression, number comparisons, empty, not empty).
- The derived-column window offers every date format of the core, a separate time column, and a
  free time zone with the Windows and IANA names.
- Browser tests that press the controls and read the result: every named date window against the
  calendar, group intervals, summaries, date formats and zones, every colour-rule operator, bar,
  scale, icon and statistic, the findings table, and — in CI — the real image driven in a browser
  (readers, Hayabusa, findings, graph and Navigator layer, rules window, alert context).

### Fixed
- **Colour rules painted every other row**, and their comparisons were a private copy of the core's
  (equals ignored case, regex/dates/text fell back to "contains", "does not contain" meant
  "differs"). The core's own evaluator now decides, statistics are the core's ("highest/lowest
  values", not frequencies), and a shared rule keeps its visual format and statistic.
- **The Hayabusa findings table had lost Show and Mark**, unreachable behind a table that replaced it.
- **A stopped import said "Import complete"** or "format not recognised"; it now says it was stopped,
  and a stop that arrives first is honoured.
- The derived-column time zone was ignored; an unknown zone left an analysis that failed on every page.
- "Clear the filters" left the advanced filter and the bookmarks-only switch; the toolbar had a
  second implementation of it. Row height's group-header height and wrap/fit did nothing distinct.
- Filters accepted eleven of the core's twenty-four comparisons.
- A file that could not be read said "the format was not recognised" and gave a French reason; it now
  says how many files could not be read and why, in English. Columns an organised collection adds and
  the alert-context analysis are named in English.
- The File menu repeated the Profiles and plugins window.

## [0.8.3] — 2026-11-24

### Fixed
- **A file chosen in the Import dialog could not be imported in the image**: the service ran as an
  unprivileged user with `HOME=/root`, so the profile detection answered `Permission denied`. The
  Profiles and plugins window and the Preferences answered 500 for the same reason.
- Several tables written from one file (registry hive, SQLite database, WebCache) all showed the
  file's name in the tree; each now carries the table's own name.
- The page no longer takes the analyst back from the tab they chose while the case list loads.
- `/favicon.ico` answered 404.

### Added
- A recette scenario that imports a file the way the dialog does; it fails on 0.8.2.

## [0.8.2] — 2026-11-24

### Added
- Dialogs can be moved and resized; the artifact tree and row details have splitters.
- `FIREBLADE_UPDATE_CHECK=off` switches the check for a newer release off.
- A recette that puts a pack of known content through the real image and compares the counts
  (`scripts/recette`, `docs/host/RECETTE.md`); first measurements: 13/13 EVTX events, 1612/1612
  WebCache rows.
- Browser tests that drive the Host with a real mouse, including behind the per-case driver.
- A Linux CI workflow for the Host: formatting, lint, the suite, the case and driver images, the recette.
- `SECURITY.md`, `CODEOWNERS`, `CONTRIBUTING.md` in English, a pull request template,
  `.editorconfig` and a `pre-commit` configuration.

### Changed
- Reports, the destruction certificate, diagnostics and refusals are in English; columns generated
  by a Fireblade reader and the analyses it organises are named in English.
- Menu entries that opened the same window are one command each, and announced shortcuts exist.
- The update band gives one line to run; the start command says that Fireblade is starting.
- Save case saves, and leaves a recovery point.
- The code base is formatted with `ruff format`, and `ruff check` enforces a real rule set.
- The Windows workflow, for the frozen Desktop, runs by hand only.

### Fixed
- **The published per-case driver image could not start** (from 0.8.1): its Dockerfile did not copy
  the modules the driver imports.
- No menu command could be run with a mouse.
- Exporting the portable case failed once an analysis had been opened.
- Reports opened in a blocked pop-up and, behind the driver, outside the case's prefix.
- Analysis > Detection rules opened the colour-rule editor; the owner "third-party" was refused;
  Group by this column answered 500; an empty attack graph was an error.
- A Common Log Format date with its offset was left undated; Windows paths recorded by a case
  written on Windows showed in full under Linux.
- `python-multipart` was missing from the development requirements.

## [0.8.1] — 2026-11-23
Update band, folders sent from the browser, certificate folder chosen by the analyst.

## [0.8.0] — 2026-11-23
One container per case, driven by a small driver; erasing a case removes its container and volume.

[Unreleased]: https://github.com/23R0534ZXT/kagarasu/compare/v0.8.3...HEAD
[0.8.3]: https://github.com/23R0534ZXT/kagarasu/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/23R0534ZXT/kagarasu/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/23R0534ZXT/kagarasu/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/23R0534ZXT/kagarasu/releases/tag/v0.8.0
