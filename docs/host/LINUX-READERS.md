# The artifact readers under Linux

The thirteen readers are Windows tools, but the pinned versions are managed .NET
and target `net10.0` as well as `net472`. A Linux container runs the `net10.0`
build with the plain .NET runtime — no Wine, no Windows.

This file records what was measured, tool by tool. A reader counts as working
only when, on the same input, it produces the same rows and the same columns as
the Windows run.

## Method

1. Same tool version on both sides (Eric Zimmerman publishes the `.NET 10`
   build at `https://download.ericzimmermanstools.com/net10/<Tool>.zip`).
2. Same input file, copied unchanged (here `C:\Windows\System32\winevt\Logs\System.evtx`).
3. Run on Linux:
   `docker run --rm -v /opt/ez:/ez mcr.microsoft.com/dotnet/runtime:10.0 dotnet /ez/EvtxECmd/EvtxeCmd/EvtxECmd.dll -f /ez/samples/System.evtx --csv /ez/out`
4. Compare the two CSVs cell by cell, not by file size: identical output can
   still differ in line endings or by the recorded source path.

## Measured

### EvtxECmd 2026.10.2 — works

| | Windows (`net472` build) | Linux (.NET 10 runtime) |
| --- | --- | --- |
| rows | 1 327 | 1 327 |
| columns | 28 | 28 |
| header | identical | identical |
| cells differing | — | `SourceFile` only (the input path, `/ez/samples/System.evtx` instead of `C:\Users\fb\samples\System.evtx`) |

Byte-level note: same CRLF, same UTF-8 BOM. The 10 616-byte difference between
the two files is exactly the longer Windows path repeated on every row.

### Measured on real artifacts from the test VM (Linux, .NET 10 runtime)

| tool | input | rows | verdict |
| --- | --- | --- | --- |
| EvtxECmd 2026.10.2 | `System.evtx` (1.1 MB) | 1 327 | identical to Windows but the source path |
| PECmd 2026.10.3 | 316 `.pf` files | 1 046 | parses |
| AppCompatCacheParser 2026.10.1 | `SYSTEM` hive (reg save) | 239 | parses |
| JLECmd 2026.10.6 | 5 jump lists | 8 | parses |
| LECmd 2026.10.4 | 2 `.lnk` files | 2 | parses |
| WxTCmd 2026.10.1 | `ActivitiesCache.db` | 4 activities, 8 package ids | parses |

All twelve `net10.0` builds start and print their help under the Linux runtime.
Not yet measured: MFTECmd, SrumECmd, RBCmd, AmcacheParser, RecentFileCacheParser —
their inputs (`$MFT`, `SRUDB.dat`, `$Recycle.Bin`, `Amcache.hve`, `RecentFileCache.bcf`)
are locked on a running Windows and need a shadow copy or a disk image;
SQLECmd and RECmd were not driven with their final arguments yet.

## Consequences for the code

`core/collection.py` already ran every tool through a .NET host:
`ToolPack.command()` returned `[dotnet/dotnet.exe, <Tool>.dll]`. The only change
needed was the host itself — `dotnet.exe` next to the pack on Windows, the
distribution `dotnet` on Linux — in `ToolPack.dotnet()`. The arguments
(`-f <source> --csv <out>`) are untouched, so the parsers, the column profiles
and the tests see the same CSV. Covered by `tests/core/test_toolpack_host.py`.

## Still to measure

AmcacheParser, AppCompatCacheParser, PECmd, MFTECmd, RECmd, LECmd, JLECmd,
SrumECmd, WxTCmd, RBCmd, RecentFileCacheParser, SQLECmd, Hayabusa (Linux build),
and our own shellbags host (needs a `linux-x64` target).


## The whole sample tree, imported by the Host (22/11)

The 333 files of the test VM's `samples` folder were copied into the container and
imported in one run (`organization=artifacts`), then read back through the import
report.

| | files | |
| --- | --- | --- |
| complete | 327 | read by the pinned tool, one analysis per family |
| duplicate | 2 | same bytes as another file, read once |
| attention | 2 | a jump list with no destination — `No destination in this jump list` |
| attention | 1 | `SRUDB.dat` — see below |
| unsupported | 1 | a console log, not evidence |

Rows written, family by family: EVTX 1 327 · Amcache 509 · Registre 10 610 ·
AppCompatCache 239 · Jump lists 8 · Prefetch 1 362 · Windows Timeline 12 · LNK 2 ·
exported CSV 1 327. The EVTX and AppCompatCache counts are the ones the Windows
column of the table above measured, on the same files.

### SRUDB.dat is the one family Linux cannot read

`SrumECmd` refuses to start outside Windows:

```
Non-Windows platforms not supported due to the need to load ESE specific Windows libraries! Exiting...
```

That is not a Fireblade defect and not a missing mount: the engine loads a Windows
ESE library. The collection used to report `Moteur terminé avec le code 1`, which
told the analyst nothing. It now reports, in the window's language:

> This reader needs the Windows ESE libraries: it cannot read this file on Linux.
> Import the CSV the desktop edition produced.

Two ways forward, both honest:

1. **Export with the desktop collector** (Windows), then import its SRUM CSV — works today.
2. **A native reader with `dissect.esedb`**, already a dependency and already used for
   WebCache. Measured on this very file: `SruDbIdMapTable` (2 413 ids) and the usage
   tables (`{DA73FB89…}` 11 020 rows, `{5C8CF1C7…}` 11 210, `{D10CA2FE…}` 4 800, …)
   are readable under Linux. The network and application tables carry their payload in
   a `BinaryData` blob, so a faithful reader means decoding those layouts — a project
   of its own, not a mount. Until then the row is reported, not silently dropped.
