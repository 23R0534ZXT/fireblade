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

### Shellbags — works (since 0.8.4)

Fireblade's own Shellbags host (`src/fireblade/shellbags_host`) is managed .NET like the
other readers. The image publishes it in a build stage (`dotnet publish -r win-x64
--self-contained false`: the target only names the lock file, the assemblies are portable) and
the runtime of the final image runs it. Measured on the test pack's `UsrClass.dat`, a dirty hive
without transaction logs: **523 decoded rows**, the count the pack states and the Windows run
gives. The file stays in *attention* for the same reason as on Windows — RECmd refuses to read
a dirty hive without its logs — and the Shellbags analysis is there beside that sentence.

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

### SRUDB.dat — read natively (since 0.8.4)

`SrumECmd` refuses to start outside Windows (it loads the Windows ESE library). On Linux the
collection hands `SRUDB.dat` to `fireblade.core.srum`, which reads it with `dissect.database`:
one CSV per provider table of the database (application resource use, network usage and
connections, energy, push notifications, application timeline…), the application and the user
resolved through `SruDbIdMapTable`, the timestamp read as a date. Measured on two real
`SRUDB.dat` of the Raw Artifacts pack (Windows 10): 618 rows in the *SRUM* family.

The columns are the database's own: they are **not** SrumECmd's column names, nothing the
database does not say is decoded, and the table is named in a `SRUM_Table` column. An analyst who
needs SrumECmd's exact output still exports it with the desktop collector and imports the CSV.
