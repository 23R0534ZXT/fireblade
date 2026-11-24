# Recette of the Host

A forensic tool is trusted for what it can account for: every file it was given, every row it read,
and what it did not. This page says how the Host is put to that test, what each level proves, and
what is still missing for an investigation that cannot afford a mistake.

## What "correct" means here

1. **Accounted for.** Every file of a source has a line in the import report, read or not, with the
   reason when it was not.
2. **Counted.** A family of rows has the count the reader was measured to produce on that input, and
   the same count as the Desktop on the same file.
3. **Unaltered.** Evidence is read, never modified: the bytes of a source before and after are the
   same, and a value shown is the value in the file.
4. **Reproducible.** The same input gives the same case, today and next year, on any machine.
5. **Honest when it cannot.** A reader that cannot run says so, with the reason, and the report counts
   the file as not read; it never reports a smaller number as if it were the whole.

## The levels

| Level | What it exercises | Where | Status |
| --- | --- | --- | --- |
| 0 — engine | parsers, filters, expressions, timeline, rules, case files | `tests/core` | automated, in CI |
| 1 — service | every route of the Host on a real case | `tests/web` | automated, in CI |
| 2 — browser | the page, with a real mouse: menus, shortcuts, dialogs, grid, timeline, hunt, reports, export, portable case, erasure, the page behind the per-case driver | `tests/web/test_browser*.py` | automated, in CI |
| 3 — image and pack | the **real image** (its .NET readers included) imports the **test pack** built from pinned public artifacts, and the counts are compared with `RESULTATS-ATTENDUS.json` | `scripts/recette/host_recette.py`, job *Recette on the real image* | automated in CI; expectations being calibrated |
| 4 — against the Desktop | the same files through the Desktop and the Host, compared cell by cell | `docs/host/LINUX-READERS.md` for six readers | partly manual; to automate |
| 5 — scale | a 3 GiB / 2.4 M-row CSV, a 15 GiB engine run, 320 analyses | `scripts/benchmarks`, `docs/validation/reports` | automated on Windows; to run against the Host image |
| 6 — failure | a truncated archive, a corrupt hive, an unreadable file, a full disk, a container killed during an import | — | **to write** |
| 7 — integrity | hash of every source before and after an import; sources mounted read-only; certificate checked against what was erased | — | **to write** |
| 8 — security | origin checks, hostile page, path escapes, crafted evidence | — | later, see `SECURITY.md` |

## Level 3 in detail

The pack is built by `scripts/test_pack/package.py` from artifacts pinned by SHA-256 in
`config/forensic-qa-fixtures.json` and `config/forensic-toolchain.json`, plus a synthetic CatScale
collection. It is imported **one source at a time**, as its own guide says (the extracted CatScale
folder and its archive are the same collection: importing both reads every row twice, which the
first run of this recette showed).

| Scenario | Source in the pack | Compared with |
| --- | --- | --- |
| catscale-folder | `02-Linux-CatScale/01-Dossier-extrait` | rows per family counted by the parser |
| catscale-archive | `02-Linux-CatScale/02-Archive` | the same counts, through the archive reader |
| volume | `02-Linux-CatScale/03-Volume` | `volume_rows` |
| exports | `03-Exports` | `exports_rows` per readable file |
| windows-evtx | `01-Windows/01-Collecte-principale/EvtxECmd` | `evtx_events` |
| windows-shellbags | `01-Windows/02-Shellbags` | `shellbags` (a documented limit of the Linux edition) |
| windows-webcache | `01-Windows/03-WebCache` | `webcache_rows_including_metadata` |

Every scenario also checks the three things an import owes: it ends, every file has a line in the
report, and nothing is in error. Those three fail the run; the count comparisons are reported as
`pass`, `fail`, `known-limit` or `info` (measured, not yet pinned) until the first runs on the real
artifacts have calibrated them, after which `--strict` makes them fail too.

```bash
python -m scripts.test_pack.package --out artifacts/pack --volume-rows 2000
python -m scripts.recette.host_recette --pack artifacts/pack/Fireblade-Test-Pack-v1 \
    --image fireblade:ci --report artifacts/recette.json
```

`tests/recette` runs the same harness against an in-process service on the part of the pack that
needs no network (CatScale, volume, exports), so the harness itself is tested on every change.

## What the recette has already found

- The Host read each CatScale family twice when the extracted folder and its archive were imported
  together (an input error, now a scenario of its own).
- Analyses organised into families were named in French (`Persistance.csv`); they read in English.

## What is missing

1. **Level 4 for all thirteen readers**, not six: a golden file per reader, produced by the Desktop
   on the pack and compared with the Host's, so that "same as the Desktop" is a test and not a claim.
2. **Levels 6 and 7**, the ones a long investigation depends on: failure injection and the
   integrity of the evidence before and after.
3. **Readers without a sample**: MFT, `$Recycle.Bin`, shellbags, SQLECmd, RecentFileCache, SRUM
   (which cannot run on Linux). Each needs a public artifact pinned by hash.
4. **Hayabusa** on the pack's EVTX: at least two alerts are expected (`hayabusa_minimum_alerts`).
5. **A recette on a real disk image** through *Analyze a disk*.
6. **Long runs**: a many-gigabyte collection imported through the container, with the memory it
   holds, and an import interrupted and resumed.
