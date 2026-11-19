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

## Consequences for the code

`core/collection.py` currently launches `<Tool>.exe`. Under Linux the same
arguments go to `dotnet <Tool>.dll`. That is one branch in the launcher, not a
change to the parsers, the column profiles or the tests: the CSV is the contract.

## Still to measure

AmcacheParser, AppCompatCacheParser, PECmd, MFTECmd, RECmd, LECmd, JLECmd,
SrumECmd, WxTCmd, RBCmd, RecentFileCacheParser, SQLECmd, Hayabusa (Linux build),
and our own shellbags host (needs a `linux-x64` target).
