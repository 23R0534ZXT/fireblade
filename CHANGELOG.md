# Changelog

All notable changes to Fireblade are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/); the case format on disk is the compatibility promise.
The full notes of each release are in [docs/development/RELEASE-NOTES.md](docs/development/RELEASE-NOTES.md).

## [Unreleased]

## [0.8.4] — 2026-11-25

Every control was pressed again and judged by what it leaves on screen, on the real image with a real
pack and real collections. Most of what follows is what that found.

### Added
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

[Unreleased]: https://github.com/23R0534ZXT/fireblade/compare/v0.8.3...HEAD
[0.8.3]: https://github.com/23R0534ZXT/fireblade/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/23R0534ZXT/fireblade/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/23R0534ZXT/fireblade/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/23R0534ZXT/fireblade/releases/tag/v0.8.0
