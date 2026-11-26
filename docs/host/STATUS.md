# Fireblade Host — status and what is verified

The Host edition is functional and is developed in the open, with browser tests that drive the
client with a real mouse. It does not yet have what the Desktop edition has: a qualification run
on the target platform, a deployment other than Docker, and a compatibility promise for its HTTP
API. This page says which is which, so that nobody relies on more than has been verified.

## What you can rely on

- **The analysis is the desktop's.** The Host imports and reads evidence through the
  same `src/fireblade/core`: same parsers, same case format, same filters, same
  timeline, same reports. A case opened in the Host is the case the desktop wrote.
- **Nothing is uploaded.** The container sends nothing about you or your cases. Its only
  outbound request is the check for a newer release (GitHub's public releases API, at most every
  six hours), which `FIREBLADE_UPDATE_CHECK=off` removes; otherwise the only peer is your browser.
- **The evidence is read, never modified.** Sources are copied into the case and
  hashed; the readers only read.
- **A long command tells you what it is doing** and can be stopped at a checkpoint.

## What you cannot rely on

- **The HTTP API.** It may change name, shape or status code between two releases. Only the
  case format on disk is a compatibility promise.
- **Access control.** There is none: the Host is for the analyst's own machine and must listen
  on it alone (`-p 127.0.0.1:8080:8080`). Collaboration, accounts and an audit log belong to the
  planned Server edition.
- **Erasure as a physical guarantee.** The Host overwrites the case's files in several passes
  and writes a certificate stating the method. On an SSD, a copy-on-write or a journaled file
  system that is not a guarantee that the bytes are gone from the medium; the plan for it is a
  per-case encrypted volume whose key is destroyed.
- **Performance at scale.** The measured runs are small: a 31 574-row EVTX and a 333-file
  collection. No claim is made beyond them.
- **Support.** There is none. The repository is the documentation.

## What is verified, and how

| | |
| --- | --- |
| Imports | every reader exercised on real artifacts, through the page, from the raw reference pack and the Windows 11 sample collection; `SrumECmd` cannot run on Linux, and `SRUDB.dat` is read by Fireblade's own reader instead ([LINUX-READERS.md](LINUX-READERS.md)) |
| Screens | the nine tabs and about fifty dialogs compared with the Desktop ([HOST-AUDIT.md](HOST-AUDIT.md)) |
| Engine and service | the suite shared with the Desktop plus the Host's own tests: about 1 600 tests |
| Client | `tests/web/test_browser*.py` drive the page with a real mouse: every menu command and every shortcut, every dialog's buttons kept on screen, dialogs moved and resized, splitters, filters, grouping, bookmarks, views, colour rules, derived columns, global search, indicator hunt, timeline, actions, reports, export, portable round trip, case creation to erasure |
| One container per case | the driver's decisions are tested against a fake Docker; the page behind the driver (prefix, reports, export, erasure) is tested in a browser with the real case service. A real Docker daemon is not part of the automated tests |
| Language | English everywhere the Host speaks; a test fails on any report sentence, refusal or column name left in French |
| Detection | Hayabusa 4.3.1 run through the page on the Windows 11 sample (183 event logs, 613 alerts), with the attack graph, the alert context and both reports built from it |
| Not exercised | a real Docker daemon, and any collection larger than the ones named in the README's limits |

## Why it exists

The same engine behind HTTP is how an analyst works a case without a Windows session, and the
route to the Server edition: one container per case, isolated and erasable as one object.
