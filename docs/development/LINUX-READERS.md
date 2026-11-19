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
