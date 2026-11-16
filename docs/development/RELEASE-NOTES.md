# Fireblade 0.4.1 — a 10 GiB collection, and what it found

This version does not come from an idea: it comes from the final acceptance run of 0.4.0 on a real
Linux collection of **9.74 GiB / 259 files**, imported through the interface, plus a laboratory disk
with two partitions analyzed as a physical drive, as a mounted volume and as a RAW image.

## Notes: a report that no longer forgets the analysis

- A row carrying **both** a row note and a cell note was enough to make the report fail: the
  sub-query meant to read "the" note returned two rows, DuckDB refused, the whole analysis was set
  aside and the report announced **0 findings**. Fixed in the three places that queried bookmarks
  without telling the row note apart (`column_id = -1`): report, timeline and computed-note column.
- The report cites row notes again when a cell on the same row is annotated.

## Every analysis carries its file name

- A Linux collection imports one intermediate CSV per log: the 34 analyses were therefore all called
  "Linux — journaux-fireblade.csv", both in the tab bar and in the navigation tree. Each analysis now
  records **the evidence path** (relative to the collection): `var/log/nginx/access.log`,
  `var/log/auth.log`, `Windows/Prefetch/KAPE.pf`…
- The displayed provenance, the report's SHA-256 digest and the section titles follow the same path;
  the working CSV is kept beside it (`working_path`) for audit.

## Readable group rows

- A group row ("Remote address: 203.0.113.7 (12 345)") spans the full width of the grid instead of
  being truncated to the width of the identifier column.

## Import: a budget computed from the file, not discovered by failing

- A CSV insert in one transaction cannot spill to disk: with the default budget (128 MB), a 3 GB
  table failed, the retry loop quadrupled the budget, and **every attempt re-read the whole file** —
  four passes for a single import, with an unchanged message. The first attempt now starts from a
  budget derived from the file size (size + 25% + 64 MB), capped at half the physical memory.
- Measured on the delivered collection, 259 files / 9.74 GiB: report `complete`, **246 analyses**, no
  missing file, in **50 min 49 s** on this machine. The memory budget is no longer what stops the
  import; the text reader, one line at a time in Python, sets the pace. That is the subject of the
  next version, and it is measured before it is announced.

## An engine blocked by Windows stops and explains itself

- On a machine where **Smart App Control** is active, RECmd's plugin DLLs are refused (`0x800711C7`).
  The engine then stayed alive, the collection waited **an hour** and Windows put up about a hundred
  "Part of this application has been blocked" windows.
- Fireblade now reads the engine's journal while it runs: as soon as a library is refused by the
  policy, the process is stopped and the collection report says what to do (allow the engine in
  Windows Security, or turn Smart App Control off), instead of waiting.

## Physical disk: the guard no longer asks for administrator rights

- The "the case is not on the analyzed disk" check opened `\\.\C:` for reading, which requires
  elevation: every non-administrator analyst saw the analysis of a physical disk refused with "use an
  acquired image".
- The check now queries the volume extents **without requesting access**, which works without
  elevation. When Windows still refuses to open the source disk, the message says exactly why and
  how to continue (restart as administrator, or analyze a `.raw` / `.E01` image).

## Interface

- **34 labels** left in French in English mode are translated: `Width`, `None`, `Columns`, `Font`,
  `Light` / `Dark`, `Grid and copy`, `Resources`, `Appearance`, `Order`, `By artifact`,
  `Simple list`, `Source date`, `Rows`, `Outputs`, `Export`, `Filter a date`, `Today`,
  `This month`, `Apply the filters`, `Highlight occurrences…`, `Clear images`,
  `Thresholds in percent`, and the Linux headers `Folder`, `Process`, `Source address`,
  `Destination address`, `Source port`, `Destination port`, `Remote port`, `Target user`,
  `Command`, `Path`, `Status`, `Bytes`, `Event`, `Detail`, `Fields`, `Line`, `End of line`,
  `Plain text`, `Method`, `Remote address`, `Protocol`, `Read`, `Timestamp`, `Host`,
  `UTC timestamp`, `Correlation key`.
- The import report statuses (`Complete`, `To verify`…) go through the translation table.

## Verification

- New tests: row note and cell note in the same report, analysis label, import budget computed from
  the file size, journal of an engine blocked by Windows.
- The three disk paths are exercised on a laboratory disk (512 MB VHD, NTFS + FAT32): physical disk
  `\\.\PhysicalDriveN`, mounted volume, RAW image. Same result on all three: 14 entries, 40 analyses,
  16 extracted artifacts, `$MFT` and `$Boot` included, one access denied on
  `System Volume Information` explicitly listed.


# Fireblade 0.4.0 — reading what the collection had not recognized

## Import report: act in place

- An unrecognized, failed or set-aside file stays in the report with its row, its reason and its digest, and the analyst can act on it without leaving Fireblade.
- **View the file**: text preview, cp1252 fallback when the file is not UTF-8, hexadecimal display for a binary. An unreadable file shows a message, never an error.
- **Copy the unprocessed files…**: copies the files without analysis into a chosen folder, tree layout preserved, **copy and never move**; the evidence stays where it was seized.
- **Export the list…**: UTF-8 CSV of what the table shows, filters included.
- **Set aside from the report** / **Reinstate**: reversible decision, saved with the collection, and removed from the work counters.
- **Delete…**: refused when the SHA-256 digest no longer matches the one recorded during collection; the deletion is traced in the report.
- A plain-language **Reason** column, counters including the set-aside files, decisions recorded in `collection.json`.

## Re-running a file with the reader of your choice

- **Re-run with a reader…** analyzes the selected file with the chosen reader, imports it like any other source and opens the resulting analysis.
- Four readers: **text** (one line at a time), **saved HTML page** (visible text and links, no browser and no dependency), **PDF (text layer)**, **CSV/TSV table**.
- The file is only read, never modified. The digest taken at read time becomes the reference: a later read is refused if the file changed. A file absent from the collection adds its row to the report instead of being refused.
- A binary is never read as text, and a file with no readable line says why instead of producing an empty analysis.

## Collection window: two questions, not three

The screen that opens before a parse offered three mixed choices: "progressive results", "by
artifact" and "unified view". The first two did not answer the same question, and the recommended
choice was the least explicit.

It now asks the two questions separately, in English like the rest of the interface: a
**"Keep working while the folder is parsed"** checkbox — you keep working while the folder is read,
each analyzed file opening in its own grid — then the **result**, with
**"By artifact — recommended"** (one tab per artifact family, all listed in the navigation tree,
each grid keeping its columns) and **"Unified view"** (a single grid, grouped by artifact, fixed
grouping).

A merged view needs the whole folder, so the layout choice is greyed out while the box is ticked,
with the reason written underneath.

## Workspace: the same bars in every mode

- **Timeline only** now hides only the docks. The top bars and the tab strip (Analyses, Imports, Cases, Timeline, IOC, EVTX) stay in place: that was the way back, and it disappeared with the mode.
- Choosing another tab leaves the mode, instead of leaving the window half undressed.
- **Analysis** re-attaches a detached timeline created by "Analysis + timeline": the modes no longer mix.
- Leaving a mode no longer breaks when a panel was deleted in the meantime; "Restore the panels" puts the tab strip back too.
- The case badge, top right, breathes: 12 px on the left, 24 on the right, right-aligned, so a long name no longer touches the window edge.

## Splash screen: redrawn

- The old splash pasted a 320×426 video into the right half and hid its seams with gradients: soft, pixelated, heavier than the application it announces.
- The new one is entirely drawn: a word centred on an axis, a sheet of warm light, an amber rule, a signature, the version, a progress line and drifting dust — deterministic, identical on every launch.
- It lasts 6.5 s instead of 10: enough to breathe without holding up the launch.
- Four tests look at it the way an eye would: the frame lights up, the lit pixels are balanced around the centre, the last frame returns to black, and the duration stays bounded.

## PDF: the text layer, and nothing else

- Text extracted page by page through `pypdf`, in the same shape as the other sources: one line at a time, with the page number; the timestamp is kept only when it opens the line.
- **No OCR**, a deliberate decision: a PDF without a text layer is reported as "PDF without a text layer" and counted with the warnings, instead of producing empty lines that would look like an analysis of the page.
- A damaged page does not take its neighbours with it: the page number is noted and the reading continues.
- Without `pypdf`, Fireblade starts normally, the PDF reader is greyed out in the choice window with the reason. The extension is pinned in `requirements/runtime.txt`, so it is present in the published executable.

## Import: no amount of memory is a prerequisite

Fireblade is built to run on a modest VM and to stay usable where a conventional tool stutters. A
collection that fell over with "Out of Memory" broke exactly that promise.

- A collection gets **all** the configured memory budget (it was halved), and the shipping default goes from 128 MB to **1 GB**.
- An import short of memory **retries with a larger budget** (×4, at least +256 MB) and continues while there is room, up to **half the physical RAM**. The cap is what avoids swapping the analyst's whole desktop.
- The **line-by-line** path — the one that takes over when the native reader cannot hold the file — now has its own memory guard: it no longer dies on the same error it was meant to replace.
- Measured on the real readers: a log of **1.35 GB, 1.2 million lines, 30 columns** imports in **39 s with a 64 MB budget**, first and last row intact. The test suite holds that case, a file larger than the budget, line by line.
- When room really runs out (a file larger than half the RAM), the failure is explained in a window, with both remedies, instead of being retried forever.

## A file larger than memory: commit by chunk

A 100 GB export did not die from the reader but from the transaction: DuckDB keeps uncommitted rows
out of the checkpoint, so no budget could suffice for a file that had to enter in one go. Above a
threshold (2 GiB, and eight times the budget), the import **commits each written chunk** and gives
the memory back before reading the next. Below it, nothing changes: a small file still arrives in one
go, atomically.

Measured on the real readers:

- 1 GB, 21.3 million lines, 64 MB budget: **64 s**, and the process never exceeded **103 MB** of resident memory, sampled every 250 ms from outside;
- 4 GB, 30 columns, 128 MB budget: **223 s**, 2.6 million lines, last row intact.

## Import: a single pass over the file

A file larger than the read step was cut into temporary chunks of a few megabytes, each re-read then
inserted. It is now read **in a single pass** while it fits in one transaction, the columns being
named by position (`c0`, `c1`, …) as everywhere else in the application. Above the transaction
threshold, and when memory runs short, the chunked path takes over.

- Measured on the same 3.65 GB / 32 million row file, 1 GB budget: **69 s instead of 148 s**, and **59 s** replayed warm (62 MB/s against 24).
- The other sizes follow: 0.8 s instead of 1.2 s (28 MB), 2.4 instead of 5.1 (112 MB), 7.9 instead of 19.7 (453 MB), 33.4 instead of 74.3 (1.82 GB).
- Memory does not move: peak of **1077 MB** measured from outside, budget at 1 GB.
- Cancellation is still honoured during the read: DuckDB's interrupt is converted into a cancellation, and a test cuts in the middle of the pass to check it.

## Threads: automatic by default

Both thread settings in Preferences → Resources accept **Automatic**, and that is the shipped value.

- "Automatic" means the machine, capped at **eight files at a time** — the point where the shared disk stops paying (48 files: 3.4 s on one thread, 1.2 s on four, 1.0 s on eight).
- The value is resolved **before** reaching the engine: DuckDB refuses `SET threads=0`, and an import that received it failed with no visible message. One place decides, and every call that talks to the engine goes through it.
- Choosing an effort level always writes explicit values: the slider keeps describing what it does.
- When a folder is cancelled, what was already finished is published: the stop is seen by the thread that holds the report, not only by the workers — a file finished before the request never raises.

## Effort: a slider computed for the machine

The Imports tab carries a single control: four levels, a bar that grows with what the import takes
and goes from green to amber then red, and a readable sentence — "Fast · 15 threads · 4.0 GB of
31.8 GB".

- The values are not a fixed table: each level is a **fraction of the machine** read at startup (cores, then physical RAM through the kernel, with no dependency).
- Light takes a quarter of the cores and 512 MB; Maximum takes everything and caps at two thirds of the RAM, where red begins.
- A level never promises more than the machine has, and a thread count typed by hand is bounded and described the same way.
- Choosing a level writes the parsing threads, the query threads and the memory budget in one gesture: parse and analysis stop contradicting each other, and the choice survives a restart.

## Compared with Timeline Explorer, measured on the same machine

Timeline Explorer 2026.10.0 installed, both tools measured on the same files, from 28 MB to 3.65 GB
(32 million rows), on a Core i7-12700K with 31.8 GB of RAM.

| File | Fireblade | Timeline Explorer | Fireblade memory | TLE memory |
| --- | --- | --- | --- | --- |
| 28 MB | **1.2 s** | 10.9 s | ≤ 1.1 GB | 0.37 GB |
| 453 MB | 19.7 s | **17.1 s** | ≤ 1.1 GB | 2.2 GB |
| 1.82 GB | 74.3 s | **51.8 s** | ≤ 1.1 GB | 7.6 GB |
| 3.65 GB | 147.8 s | **108.3 s** | 1.1 GB | **15.3 GB** |

Timeline Explorer is 1.4× faster on the big files — that is true and it is not the axis that matters
here. It loads the whole file into memory, at **4.2 times its size**: 15.3 GB for a 3.65 GB file, and
its own window warns that the stated limit is 14 GB, that is close to 60 GB of RAM. On an 8 GB VM,
the practical ceiling is a file of a little under 2 GB, whatever time you give it.

Fireblade stays at **its budget** (1.1 GB measured, 2.2 GB when set to 8 GB) and imports without
changing behaviour, which is the subject of this version.

The detail, the method, the raw numbers and the limits of the comparison are in
`docs/development/BENCHMARK-0.4.0.md`; the measurement scripts are in `bench/`.

## Verification gate

- The suite runs in **UTF-8**: fixtures wrote their CSV without `encoding=`, so in the local code page, while the code reads UTF-8 and CI is UTF-8. That was 25 failures out of 25 with nothing to do with the product.
- A `%TEMP%\pytest-of-…` folder left by an earlier run is purged: Windows reused the old folder without correcting its spelling, `resolve()` returned the case stored on disk and the paths differed by one capital. Those were the 7 remaining failures.
- The test that verifies the core does not load Qt now keeps the interpreter's packages instead of losing them by replacing `PYTHONPATH`: it failed on an environment detail, not on a Qt leak.

## What the reading must accept

A text file does not always arrive in clean UTF-8. Three families were found by probing real files,
and each was read wrongly:

- **UTF-16 with a BOM** — a redirected PowerShell output, a file saved as "Unicode" by Notepad: the file was refused as binary, or displayed with a NUL character between every letter.
- **UTF-8 BOM** — the invisible character stayed at the head of the first line and stopped the date being read when it opened the file.
- **HTML page in cp1252** — saved on a French machine, it lost its accents.

The reader now follows the order: requested encoding, BOM, charset declared by the page, UTF-8,
cp1252. And a file larger than the read limit says so (line and byte counts) instead of producing an
analysis that looks complete.

## Verification

- Full suite: **1406 passed, 28 skipped**, Qt Windows platform, real window built, ruff clean.
- Probes on real files: 46 checks on text, HTML page, PDF (including one of three pages and one encrypted) and a collection tree — 46 out of 46; a 100,000-line log imported in 1.5 s.
- No failure left. The failure families encountered came from the gate and its modal-window watchdog, never from the product.


# Fireblade 0.3.1 — the whole interface in English and in French

## Language

- The interface is translated **in full**, and no longer only the menus and toolbars: dialogs, column manager, preferences, IOC hunt, coverage, timeline, table headers, drop-down lists, tooltips, input texts and status messages.
- **Model headers** (coverage, rules, IOC hunt, results), the navigation **tree nodes**, **table cells** and **theme names** are translated too: they are not widgets, they have their own pass.
- The **built-in guides** (full tutorial, user guide, timeline and backups, IOC hunt, coverage) exist in English and open according to the chosen language, as do the help window titles.
- **Condition cards and the AND / OR / NOT filter**: operators ("Contains", "Starts with", "Number ≥", "Date equals"…), connectors, buttons ("All conditions", "At least one", "+ Condition", "Collapse/Expand") and the sentence that reads the filter are translated.
- **Selection notes**: on a selection of rows, the menu offers "Add a note to the selection…" as long as none carries one, then "Edit the selection note…". The window opens pre-filled when all rows share the same note, and the replacement is explicit.
- **Cell notes**: a right click on a value offers "Add a note to the cell…", then "Edit the cell note…" once the note is written. The cell takes a green background, the note can be read in the window and in the tooltip. A row note (bookmark) and cell notes coexist; removing the bookmark does not delete the cell notes. Analyses opened before this version are migrated on opening, without loss.
- **Double click on a cell**: it shows the value as text, JSON or XML (choice in the window), instead of opening the note editor. The bookmark and its note stay reachable through the Edit menu and a click in the first column. The buttons of the colouring and sort rule windows ("Add", "Delete", "Move up", "Move down") are translated.
- A **menu opened as a popup** is now translated: its tree was never walked.
- Messages **assembled by concatenation** (`"Filter reading: " + value`) are handled as templates: the fixed text and the value are translated separately, then recomposed.
- **Texts computed at display time** go through the same table: counters ("2 case(s) shown"), task endings, displayed errors, verified archive message. The table accepts templates (`Analysis missing: {}`) whose values are reinserted at display time, and the most specific entry always wins.
- Translation applies **when each window opens** and **when the code writes the text**: a list filled afterwards, a refreshed counter or a late error are covered, without touching each window's code.
- **French stays complete**: the original labels are remembered by the language layer, and switching back to French loses nothing, including when a text had been replaced in the meantime.
- **From 0.3.2, only English is worked on**: new labels are written directly in English and the French already translated is no longer maintained (it stays displayable, with no guarantee of follow-up).
- Six strings deliberately stay as they are: sample file names (`évidence.csv`, `résumés.csv`, `fonctions étendues.csv`) and two synthetic TLE expressions. They are data, not interface.

## Fixes

- A tab title no longer accumulates escape ampersands from one language change to the next: `Chronologie & corrélations` ended up displayed as `Timeline &&&& correlations`.
- A language switch no longer rewrites tab titles when the text has not changed, which caused a clear slowdown on a loaded workspace.

## Verification

- Measured coverage: `scripts/i18n_inventory.py` lists every French string able to reach a screen. **946 of 954 are translated**, the eight remaining are data.
- Two guard tests: a new untranslated string fails the suite, and the list of leftovers can only shrink.
- A test builds the real window in English and checks no French word remains visible.
- A sweep of the real window and eleven dialog windows in English finds **no French text left**.
- Full suite: **1327 tests passed**, 31 skipped, no error, Qt Windows platform.

# Fireblade 0.3.0 — English interface, grouping and a readable timeline

## Language

- The interface opens **in English**; **French** stays available in **Preferences → Language**. The choice is saved.
- The translation covers menus, toolbars, tabs, buttons, headers, filters and input texts. Texts computed at display time (counters, "no active case") stay in French for now.
- An untranslated label displays as is, never empty and never replaced by a technical key.

## Organizing the analysis

- **Grouping bar** redesigned: numbered levels, a header dropped at the exact position, one `×` per level, and a **Clear all** button.
- **Column manager** in two panes: hidden columns on the left, order on the right, plus the width and pinning of the chosen column. The whole is remembered per artifact format.
- **Command palette** (`Ctrl+Shift+K`): every menu entry behind one field, including those without a button.

## Search

- The cross-artifact search now shows **the events found** — four real rows under the table — and the rest of the volume, instead of a simple counter per file.

## Timeline

- The bars carry **volume**: their height reflects the number of events in the time slice.
- The **tracks fill** the available height instead of floating in a band, and the source label is centred.
- The action bar stays visible in **Timeline only** mode.

## Fixes

- **Empty window at launch**: the saved layout replayed the timeline mode before a case existed, hiding tabs and bars. That mode is no longer replayed at startup.
- **"Parse a folder" bar**: it stayed hidden until a visit to Workspace → Analysis; it is visible and usable from the launch screen.
- **Ghost after a drag**: grouping applies after the drag ends, and the header receives the button release; no more greyed column left on screen.
- **Open button**: a refused case change now shows its reason instead of doing nothing.
- **Tabs**: an `&` in a title no longer displays as an underline.
- The version is displayed at the bottom right of the status bar and of the launch screen.

## Verification

- Full suite: **1287 tests passed**, 31 skipped, no error, Qt Windows platform.
- The suite can no longer freeze on a modal window: a watchdog rejects any box left open and names it.

# Fireblade 0.2.3 — a reliable timeline and recovery

- **Date column**: an explicit UTC column (`UTC timestamp`, `TimestampUtc`) now wins over the raw column it comes from. Linux logs, whose syslog timestamp has neither a year nor a zone, are no longer indexed on the wrong column.
- **Index time zone**: dates without a zone are read as **UTC** in the timeline, as at import. The same folder therefore produces the same chronological order from one machine to another; only test models or clock settings can move it.
- **Computed columns**: the proposed date is resolved against the analysis's real schema, derived columns included. A computed UTC column is therefore usable automatically, and a guessed index is no longer saved as a choice: the timeline settings saved by 0.2.2 are reset once.
- **Profile dates**: a `VisitTime` declaration recognizes a `Visit Time` export. The analyses concerned no longer open without a time column.
- **Separate date and time**: an export that writes `date` and `time` in two columns (IIS, W3C, some timelines) is now indexed on the two columns combined, not on the date alone at midnight. The choice stays editable in **Sources and dates…**.
- **Artifact detection**: the most specific profile wins over a narrower profile it encompasses. 18 catalogue entries — including `HayabusaVerbose`, `HayabusaSuperVerbose`, `ChainsawPersistence` and nine RECmd profiles — were never selected and now are. A declaration saved on a single tab-separated line (`MsftMft`) is split into columns.
- **Profile rules**: category colours no longer replace the profile rules. Hayabusa severity thresholds get their colours back.
- **Interrupted export**: an interruption during verification removes the temporary file. A new export to the same target is no longer refused for good.
- **Robustness**: a group path deeper than the view's groupings produces an explicit message, and a trailing empty row in a parser CSV no longer cancels the whole file.

# Fireblade 0.2.2 — a modular analysis workspace

- Artifact tree: direct family / folder / list choice, recognized families and analysis count.
- Global search by default in the open artifacts; results panel, hiding of empty results and jump to the source.
- Panels that can be detached, docked and resized; Analysis, Timeline only and side-by-side layouts; local saving of the layout.
- Column order and width saved automatically per format after moving headers.
- Highlighting of occurrences only; support for Unicode characters outside the BMP.
- Enlarged timeline, compact controls, quick periods and detection of Time / Timestamp columns; built on opening.
- Persistent resources: memory, query threads and import/parsing threads. Collections stay sequential; external engines keep their own options.
- Rule creation targeting a cell from the right click. Rules reachable from the workspace bar; creation of custom JSON profiles from the current artifact; access to the .NET readers.

# Fireblade 0.2.1 — progressive imports, menus and integrity

## Adding data from Analysis

The case home page and the grid offer the three entries directly: data file, folder to parse and
disk. The **Case** menu manages investigations and their backups; **Analysis** gathers the data and
the investigation tools; **Detection** gives access to Hayabusa and to IOCs; **Export** gathers the
outputs. Display options are grouped by columns, groups, views, colours and navigation.

The parsing report stays in **Imports**. The Hayabusa threshold and launch have a separate
**EVTX detection** screen; the IOC hunt keeps its own space. Diagnostics are consulted on demand in
**Help → Check imports and diagnostics…**, without a permanent main tab.

## Folders processed in the background

- Selection of several folders with **Ctrl/Shift** in the picker. They are processed one after another in the same case; Stop also cancels the folders still waiting.

- Folders use the same background processing as disks. One import runs at a time; the grid stays usable and the Stop button keeps the finished results.
- By default, each closed and verified result appears progressively, without changing the analysis already being consulted.
- Grouping by artifact or into a single grid stays available; their results appear once the grouping is finished.
- The added analyses are attached to the case and find their place again when it is reopened.

## Small machines and startup

- Default setting: **one thread and 128 MiB per DuckDB database**. Background parsing gets half the configured budget, with a minimum of 64 MiB, and one thread.
- Results are merged in batches of sixteen; intermediate backups are spaced out and the receiving timer stops when idle.
- These budgets do not cap all the RAM of Python, Qt or the external engines. The user configuration keeps priority.
- **10-second** startup animation: real fire on a dark background, progressive lighting and appearance of the logo, which can be disabled in the organization preferences. Playback stays local and silent, without caching every image.

## Eight audit findings fixed

- Walking real NTFS images without the Dissect adapter's `is_junction` error.
- Copying the SQLite WAL/SHM/journal companions; rejecting a group of files changing during its copy.
- DuckDB analyses received opened without SQL access to external files; validation of stored objects and refusal of hostile views/metadata.
- Results from a source whose integrity failed removed from published collection sessions.
- IDNA updated to **3.15** and early length check of domains.
- Common export protection: raw evidence, companions, analyses, internal case files and aliases by file identity.
- Export of Hayabusa sources protected and atomic, keeping the previous destination if it fails.
- Fireblade/TLE sessions and global rules can no longer overwrite the case metadata.

## Validation and limits

The EXE publication is conditional on the Windows Python 3.11/3.12/3.13 tests, the build and the
standalone run, the native readers, UNC/long paths, the visual checks, the scenario above 3 GiB and
the 320 analyses. The digest of the published executable and its commit appear at the end of these
notes.

The Linux tests include the audit regressions, the three folder import organizations, queries during
parsing, reopening the case and the menu walks. A 250,000-line folder trial also kept the source and
the processing of Qt events, with the 128/64 MiB DuckDB budgets; its measurements do not qualify
every virtual machine.

Fireblade remains an unsigned prototype. Disks are read to extract the supported artifacts: no full
acquisition, decryption, carving or recovery of deleted files. Formats and devices not exercised are
not qualified by these results.

## Memory and storage

- If the native CSV reader reaches its budget, the import resumes in a fresh transaction with row batches bound by parameters. Wide pages are read in batches of columns. The memory budget is not raised automatically.
- **Cases → Archive and free the space** creates a verified portable archive, keeps a reference in the catalogue, then removes the local files. External evidence stays intact. Restoration starts from the catalogue.
- Closed databases are archived directly after checkpoint, without a second full copy on disk. The case's companion files are kept in the archive.
- The README is now in English and presents the capabilities, the limits and the procedures in a structured way.
