# What "beta of a beta" means here

The desktop edition has releases, a signed Windows build, a qualification suite and a
version number that means something. The Host edition has none of that yet. Saying
"beta" alone would already be generous, so the repository says it twice.

## What you can rely on

- **The analysis is the desktop's.** The Host imports and reads evidence through the
  same `src/fireblade/core`: same parsers, same case format, same filters, same
  timeline, same reports. A case opened in the Host is the case the desktop wrote.
- **Nothing is uploaded.** The container talks to no outside service; the only network
  peer is your browser.
- **The evidence is read, never modified.** Sources are copied into the case and
  hashed; the readers only read.
- **A long command tells you what it is doing** and can be stopped at a checkpoint.

## What you cannot rely on

- **The HTTP API.** It may change name, shape or status code between two commits, with
  no deprecation window.
- **The interface's details.** A screen that exists today may move tomorrow; the
  parity page tracks the intent, not a contract.
- **The deployment.** The image is published at `ghcr.io/23r0534zxt/fireblade`, with a
  version tag per release. There is still no upgrade path: pulling a new tag replaces the
  service, and the case format on disk is the only compatibility promise.
- **Performance at scale.** The measured runs are honest but small: a 31 574-row EVTX,
  a 333-file collection. No claim is made beyond them.
- **Support.** There is none. If it breaks, the repository is the documentation.

## What is measured, and what is not

| | |
| --- | --- |
| Imports | 13 readers exercised on real artifacts; SRUM fails on Linux and says why ([LINUX-READERS.md](LINUX-READERS.md)) |
| Screens | the nine tabs and ~50 dialogs walked screen by screen against the desktop ([HOST-AUDIT.md](HOST-AUDIT.md)) |
| Tests | the shared core and the Host service are covered by the same suite as the desktop; the client has contract tests, not a browser test |
| Readers without a sample | MFT, `$Recycle.Bin`, shellbags, SQLECmd, RecentFileCache, WebCache |

## Why it exists anyway

Because the same engine behind HTTP is how a small team shares one case without
shipping a Windows session to every analyst, and because the comparison forced the
desktop's own defects into the open: the seven fixed after the recette are listed in
[HOST-AUDIT.md](HOST-AUDIT.md), and three of them were in the client the desktop's
tests never load.

It now has a versioned image, its own release notes and a driver that gives each case its
container. It becomes something else the day a browser test runs in CI — that day is not
today.
