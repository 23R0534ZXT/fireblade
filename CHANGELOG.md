# Changelog

All notable changes to Fireblade are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/); the case format on disk is the compatibility promise.
The full notes of each release are in [docs/development/RELEASE-NOTES.md](docs/development/RELEASE-NOTES.md).

## [Unreleased]

### Added
- Continuous integration for the Host on Linux: formatting, linting, the full suite including the
  real-browser tests, and a smoke test of the images.
- `SECURITY.md`, `CODEOWNERS`, `CONTRIBUTING.md` in English, a pull request template, an
  `.editorconfig` and a `pre-commit` configuration.

### Changed
- The Windows workflow, for the frozen Desktop, runs by hand only; the Host is checked by its own workflow.
- The code base is formatted with `ruff format`, and `ruff check` enforces a real rule set instead
  of syntax errors only.

## [0.8.2] — not yet tagged

### Added
- Dialogs can be moved and resized, and the artifact tree and row details have splitters.
- `FIREBLADE_UPDATE_CHECK=off` switches the check for a newer release off.
- Browser tests drive the Host with a real mouse, including behind the per-case driver.

### Changed
- Reports, the destruction certificate, diagnostics and refusals are in English; columns generated
  by a Fireblade reader are named in English on screen and in CSV exports.
- Menu entries that opened the same window are one command each, and announced shortcuts exist.
- The update band gives one line to run.
- Save case saves, and leaves a recovery point.

### Fixed
- No menu command could be run with a mouse.
- Exporting the portable case failed once an analysis had been opened.
- Reports opened in a blocked pop-up and, behind the driver, outside the case's prefix.
- Analysis > Detection rules opened the colour-rule editor; the owner "third-party" was refused;
  Group by this column answered 500; an empty attack graph was an error.
- A Common Log Format date with its offset was left undated; Windows paths recorded by a case
  written on Windows showed in full under Linux.

## [0.8.1] — 2026-11-23
Update band, folders sent from the browser, certificate folder chosen by the analyst.

## [0.8.0] — 2026-11-23
One container per case, driven by a small driver; erasing a case removes its container and volume.

[Unreleased]: https://github.com/23R0534ZXT/fireblade/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/23R0534ZXT/fireblade/commits/main
[0.8.1]: https://github.com/23R0534ZXT/fireblade/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/23R0534ZXT/fireblade/releases/tag/v0.8.0
