# Fireblade 0.9.0 — the Host, checked in a real browser

Each change below was found by driving the Host with a real mouse in a real browser, on a case
of Linux logs, and comes with the test that would have caught it.

## Commands that did not work, and now do

- **No menu command ran when clicked.** The page closed every menu on mouse-down, so the item
  was gone before the click reached it; only a script calling `click()` worked. Presses inside a
  menu now reach their item, and the menu closes once the command is chosen.
- **Save case** answered "A name is required": it ran the handler of the new-case dialog, and
  the dialog rewrote the label of the menu entry it shared an action with. They are two commands
  now. Save case writes the session again, which leaves a recovery point in History, and says how
  many are kept.
- **Export the portable case** failed as soon as an analysis had been looked at, with
  "Can't open a connection to same database file with a different configuration". The grid's
  connection is released first. The case now makes the trip (export, download, import as a new
  case) with its analyses and its bookmarks.
- **Analysis > Detection rules…** opened the colour-rule editor; it opens the Hayabusa rules.
- **Choosing "third-party" as an action's owner** was refused by the core ("Action owner must be
  one of…"); the owner list now speaks the core's vocabulary, and vendor and unassigned are in it.
- **Group by this column** on the row menu answered with a 500 and a stack trace (a group key was
  sent where a row id belongs). A missing or null number is now a 400 with a sentence.
- **Reports** were opened with `window.open` after a long wait, which a browser takes for a
  pop-up, and which pointed outside the case's prefix behind the per-case driver. The dialog
  comes back with the result as links that carry the prefix, and says when nothing was selected.
- **An empty attack graph** was an HTTP 400 and a red status line; it is an empty graph with what
  to do next. Only exporting one is refused.

## Windows and panes

- Every dialog is moved by its title bar and resized from its corner, and always stays inside
  the page, including a dialog that fills in after it opens (the preferences used to push their
  Close button below the screen).
- The artifact tree and the row details are resized from splitters; a double click resets them.
  Geometry is kept across reloads.

## One command, one name

- Import evidence and Import a file opened the same dialog; Parse a folder was that dialog with a
  preset; Text expression and the AND / OR / NOT editor opened the same window; Save the view and
  Load a view the same list; Open an analysis sat in two menus. Each is one command under one name.
  The toolbar offers Analyze a disk, as the Desktop's does.
- The menus announced a dozen shortcuts and the page bound three, one of them to two commands.
  It binds the ones a page may own — Ctrl+O, Ctrl+Shift+I, Ctrl+S, Ctrl+F, Ctrl+K, Ctrl+Shift+E,
  Ctrl+C on a selection, F1 — and announces only those.
- The detection tab is no longer named after an assistant the Host does not have.

## English everywhere

- The client report, the investigation report and the destruction certificate were handed out
  with a French body under an English title. They are English, through one door
  (`web/english.py`): sentences are translated, values inside them are kept, and nothing inside
  `<pre>`, `<code>` or free text in a table is rewritten — that is where the evidence is.
- The coverage diagnostics and their exports, the progress of long commands and every HTTP
  refusal are English; 240 refusals of the core's parsers, importers and case files were
  translated, and a test fails on any new one that is not.
- The columns a Fireblade reader generates (the Linux logs) read in English on screen, in dialogs
  and in the CSV export. The headers of a file the analyst brought are never touched.
  Expressions and derived columns accept the names on screen.

## Linux logs

- nginx and Apache dates (`01/Nov/2026:10:00:00 +0200`) carry their offset and are normalised to
  UTC; a whole access log read "0 dated" on the timeline before. A date with no offset or no year
  is still never guessed.
- A case written on Windows records `C:\…` paths; read in the Linux container, they showed in full
  as labels and in the reports. They are read the same on both.

## Tests

- `tests/web/test_browser*.py` drive the client with a real mouse: every menu command and
  shortcut, every dialog's buttons kept on screen, the windows and splitters, the grid, views,
  colour rules, derived columns, search, the indicator hunt, the timeline, actions, reports,
  export, the portable round trip, a case from creation to erasure, and the page behind the
  per-case driver. They are skipped without Playwright and a Chromium.
- The suite no longer depends on a system `dotnet`.

## Documentation

- A new README; the "beta of a beta" wording is replaced by `docs/host/STATUS.md`, which says what
  is verified and how, and what cannot be relied on (no access control; software erasure is not a
  physical guarantee on SSDs).

# Fireblade 0.8.1 — an update that reaches the cases

## Upgrading is a pull and a restart

- The driver compares the image id of every case container with the image it is configured
  with. A container built from another image is stopped, removed and rebuilt on the next
  open, and the stale ones are swept when the driver starts — the volume keeps the case, and
  nothing is migrated.
- `--image` now defaults to the published case image, and the compose passes it: a driver
  deployment no longer needs a locally built `fireblade:host` under another name.
- `deploy/host/README.md` gains the upgrade recipe: pull both tags, recreate the driver with
  the same `--image` tag, open the cases.

## A collection can be sent as a folder

- **Import a folder…** (Case menu, `Ctrl+Shift+I`): the browser hands over a directory, every
  file keeps its relative path under the case's `evidence/`, and the folder is then previewed
  and imported exactly as a folder on the server. A collection is a tree — the readers look
  for what its subfolders hold — and until now only single files could cross the browser.

## The certificate goes where the analyst says

- The erase dialog asks for the folder the certificate is written to, outside the case, with
  the service's own default filled in. A document nobody can find was not written.
- Under the driver, the folder is the one mounted from the host: the dialog shows it and
  says it cannot be moved from there, since a path typed in a case would point inside the
  container.

## The client says when a newer release exists

- A band across the window, at most one per version: the release you run, the one available
  and the command to paste, with a Copy and the release notes. Dismissing it is remembered.
- The check is cached for six hours and a failed request is reported as a failure, never as
  "up to date"; `/api/version` carries the answer and `/health` repeats it.
- Nothing updates itself. Watchtower does, from the labels it already knows, and the driver
  rebuilds the case containers from the new image on the next open.

## Verified on this machine

- A driver started on a locally built case image, then restarted on the published one: at
  start-up the stale case container was removed, the case folder untouched, and opening the
  case rebuilt the container from the new image.

# Fireblade 0.8.0 — one container per case

## The Host gives each case its own container

- Opening a case creates a container that mounts that case's volume and nothing else: the
  case, its exports, its archives and its certificate annexes live in one folder, and the
  container sees no other case. A small driver — its own image, no Qt, no .NET, no readers —
  lists the cases, creates them, opens them and proxies `/case/<id>/` to the right container.
- The client knows the prefix: every path it asks for goes through one function, so a case
  served under `/case/<id>/` works exactly as before. With no prefix the single-container
  Host behaves unchanged.
- The number of running containers is capped (`--max-open`, three by default): the least
  recently used one is stopped, not destroyed, so reopening it is instant.
- A container whose case is gone is removed when the driver starts; a folder that is not a
  case is reported on the page and never deleted.

## Erasing a case erases everything it left behind

- Destroying a case now also destroys what it left outside its folder: the portable packages
  in `exports/`, the archives, and the annex holding the certificate's photos. The dialog says
  how many files that is before the analyst commits, and the result counts them.
- The certificate still carries its photos: they are read before the annex is destroyed, so
  the annex disappears and the document keeps its evidence.
- In the Host client, a case is **erased**, not archived: one button, one verb. The duplicate
  menu entries ("Destroy the evidence", "Delete the case") are one entry again.

## A fresh Host starts on a folder it can write

- Mounting a cases folder from the host hands the container a directory owned by whoever
  created it — usually root — while the service runs as uid 10001, so "New case" failed
  with `Permission denied`. The image now takes ownership of `/data/cases` and
  `/data/plugins` once at startup, then drops to 10001 before the service starts.

## Verified on this machine

- Two cases opened at once: two containers, each serving its own case only, no mixing.
- Erasing one of them, three DoD passes: its container, volume, folder, portable package and
  archive gone, the certificate written outside at `/srv/fbcertificates`, the other case still
  open in its container and still readable.
- The one-container Host, reinstalled from the same tree, still serves its nine cases.

# Fireblade 0.7.9 — deleting a case, and imports that say what they did

## Deleting a case destroys it, not just its tabs

- File menu, "Delete the case…": the analyst picks three or seven DoD 5220.22-M passes, names
  an operator and a witness, says where the certificate goes, and types the case name to arm
  the run. Fireblade then overwrites **every file the case holds** — copied evidence, analyses,
  tracking, sessions, register history — verifies the last pass, deletes the files, removes the
  folders and finally the case folder itself.
- The certificate cannot live inside the case, since that folder is what disappears: the dialog
  asks for a destination outside and refuses one inside, and the PDF/HTML is written before the
  folder is removed.
- A file that cannot be deleted keeps the case folder: nothing is left half-gone without a
  trace, and the dialog says how many files survived and why.
- The certificate stays readable when a case holds dozens of files: the summary table lists
  file, size and verdict on one line each, and the full path, the timing and both SHA-256
  values go to an appendix written as paragraphs, which no longer breaks a row across pages.

## An import that names what it did, per artefact

- A log with no event is no longer imported as an empty grid: EvtxECmd's header-only CSV is
  recognised, the entry says "Empty log: no entry", and the history shows it as not imported.
- A file carrying the `.evtx` extension without the format signature says "Unreadable EVTX: no
  signature" instead of passing for an empty log.
- A parser that dies after writing part of its CSV keeps what it wrote: the row is marked
  "complete with warnings" with the parser's own message, instead of losing the whole file.

## Verified on this machine

- Real logs: `Security.evtx` (30 749 events) and `Windows PowerShell.evtx` imported and
  readable; `HardwareEvents.evtx` named empty; a fake `.evtx` named unreadable.
- Three families in one import: two Prefetch, two shortcuts and one event log — 7 analyses,
  30 753 rows, no file left unsupported.
- The case destruction ran on a test case: every file overwritten and removed, the folder gone,
  the certificate written outside.

# Fireblade 0.7.8 — the import in full, and rules you can change

## An import history, file by file

- The Imports panel gains "History…": every file of the import with its state — imported,
  duplicate, not imported — its reader, and the reason when there is one. The list filters
  to imported, not imported or duplicates, and each row can be ticked.
- Ticked files can be retried with another reader, which is the answer to "these EVTX were
  not imported": the reason is written next to each one, and another attempt is one click.
- A row whose file resembles another (same name, same size, different content) says so: the
  two are distinct evidence, and both are imported.

## Duplicates are content, never resemblance

- Two files are a duplicate only when their SHA-256 matches: the same bytes, read once. A
  file that merely looks like another keeps its place in the case, and the history names the
  file it resembles instead of hiding it.

## Hayabusa rules you can read, adjust and switch off

- The Hayabusa panel gains "Detection rules…": the rules of the pack, searchable, with their
  title, level and state; the selected rule opens as text, and saving validates that it still
  carries what Hayabusa needs (title, logsource, detection).
- A saved rule is an override in your own rules folder — the delivered pack is never
  written. A rule can be switched off without deleting anything, and restored to the pack's
  version in one click.
- The next analysis runs on a merged folder: the pack's rules, minus the ones switched off,
  plus your overrides, linked so the cost is nil.

# Fireblade 0.7.7 — "what launched this?", a filter operator, and names that say something

(shipped inside 0.7.8; no 0.7.7 archive was published)

## From a row to what started the process

- Right-clicking a row that carries a process — a PowerShell script block, a Sysmon image, a
  4688 new process — offers "What launched powershell.exe?". The timeline opens with that
  process searched across **every analysis of the case**, narrowed to half an hour before the
  event and two minutes after it, and the line under the results says what was searched, on
  which host and around which instant.
- Nothing is concluded for the analyst: the rows the artefacts recorded come back, with the
  parent process columns they carry, and the reading stays theirs.
- The anchor is read the way a practitioner reads a row: by column name (Image, NewProcessName,
  ScriptBlockText, CommandLine…) and, when there is none, by what the value looks like.

## A filter operator under every column

- The box under a column header now starts with a glyph (∈, =, ≠, ^, $, .*, >, ≤…): clicking it
  offers the whole operator list — contains, does not contain, exact, starts, ends, regex,
  empty, numeric and date comparisons, named expression. The filter is applied with the operator
  chosen, without leaving the grid.

## Artefact names instead of parser file names

- A parser CSV is named by what it holds: `amcache.csv` reads "Amcache", an EvtxECmd export
  reads "Event logs", and a bare `export.csv` takes its family or its folder instead of its
  own meaningless name. The file stem stays when it adds something.

## Verified

- Real window, four analyses: the pivot from a 4104 row found two events across the case,
  including the Sysmon process-creation row that carried the same command line, and the
  window line named the host and the instant.
- The operator glyph applied an exact filter (`=`) instead of the implicit "contains".
- The tree showed "Amcache" and "PowerShell" where it used to show `amcache.csv` and a bare
  file name, and no longer showed `export.csv`.

# Fireblade 0.7.6 — a closed tab keeps its analysis, a column hides with a cross, and the graph leaves as an ATT&CK layer

## Closing a grid no longer loses the file

- Closing a tab used to remove the analysis from the navigation tree, so the only way back
  was to import the folder again. Closing now closes the tab and nothing else: the analysis
  stays in the case, listed in the tree, greyed out and marked "closed tab".
- Double-clicking it brings the tab back with its saved view, columns and filters. The
  Ctrl+Shift+T shortcut, which reopened the last closed tab, takes the same path.
- The case remembers what was closed: switching cases or restarting keeps the analysis in
  the tree. A case whose every tab is closed is still a case, not an empty window.

## A cross on every column header

- Each column header carries a small cross on its right: it hides that column, exactly as
  the column manager does. It is not drawn on a column too narrow to hold it.

## Verified

- Three files imported as three tabs; one closed by hand: two tabs left, the third listed in
  the tree with its "closed tab" mark; double-clicking it restored the third tab.
- The cross of the `EventId` header hid that column on the real window, and the other
  headers kept theirs.
- Sessions written before this version still open, and a session holding only closed
  analyses is accepted.

## The attack graph as a MITRE ATT&CK Navigator layer

- The graph tab now exports the case as a Navigator layer (`.json`), the format the official
  ATT&CK Navigator opens. Each technique the findings declare becomes an entry: its
  identifier, the tactic the rule named, the hosts an alert attributed it to, and a score
  equal to the number of those hosts — so the colour says how widely a technique spread.
- Nothing invented: a node without an ATT&CK identifier (`Txxxx` or `Txxxx.yyy`) is never
  written, and a graph without techniques says so instead of producing an empty file.
- The case name travels in the layer metadata, so two layers opened side by side stay
  distinguishable.

# Fireblade 0.7.4 — the import says where it stands

An import of a hundred and nineteen files gave nothing to watch for twenty minutes: rows
appeared one grid at a time, and with a merged layout nothing appeared at all until the
end. The window looked asleep while it was working.

## A percentage, and what it counts

- The Imports panel now carries a bar and one line: files done out of the total, the file
  being read, the rows a parser reported, the estimated time left, and the percentage.
- Files are weighted by their size, not their number: a 4 GB image counts far more than a
  2 KB text file, so the percentage follows the reading and not the file count.
- The file in progress adds a partial share, estimated from the speed of the files already
  finished, and is never counted as complete before it is. The bar stops at 99 % until the
  last analysis is published — it does not sit at 100 % while the merge is still running.
- During the family merge the line names the step ("Merging the artifact families") and the
  percentage stays where the reading left it instead of jumping to the end.
- A cancelled import stops where it really stopped, and the line disappears once the report
  is complete.

## Verified

- Forty files read on the real window: 0 % → 7,5 → 18 → … → 98 → 99 (merge) → 100, thirteen
  samples, the file being read named at every step, and the merged grid alone at the end.
- The line is shown while the import runs and hidden when it is over, including after a
  cancel; rows are only displayed when a parser actually counted them.

# Fireblade 0.7.3 — one grid per artifact family, and it is what you get

Choosing "by artifact" on a real collection left the per-file grids on screen: 128 EVTX
files were still 128 tabs, and the merged grid was nowhere. The folder had been read
progressively — every file published its own analysis as it finished — and the merged
results were added on top of them instead of replacing them. An analyst who asked for one
grid got a hundred and twenty-eight, which is the opposite of the point.

## Three layouts, named by what you get

- **One grid per file** — results appear as the folder is parsed. Each source keeps its own
  grid; the window stays usable during a long parse.
- **One grid per artifact family** — recommended, and the default. All EVTX in one grid, all
  MFT in another, all Amcache in another. The source file is kept as a column, so no
  provenance is lost, and the parse finishes before the grids open.
- **One grid for everything** — a single grid holding every artifact, grouped by family. The
  grouping is fixed: it cannot be removed, and the columns of all sources are merged.

The progressive checkbox is gone: it was a second decision hidden inside a layout. A layout
now says what happens, and the per-file behaviour belongs to the first one.

## What changed under it

- A merged layout now removes the per-file analyses it was built from, so the case holds the
  grids the analyst asked for and nothing else.
- A family that cannot be merged — out of memory on a very large merge — stays as its
  original analyses, and the reason is written in the Imports report instead of disappearing.

## Verified

- Three layouts on the real window, same folder of four sources: 4 grids, then 2 (all CSV in
  one), then 1 holding every row with its grouping.
- The 128-file case, at scale: 128 analyses of 20 000 rows merged into a single EVTX grid,
  2 560 000 rows, 353 MB, in 44 s, no memory failure.

# Fireblade 0.7.2 — the IOC hunt no longer freezes the window

- Starting a hunt built its reader — which opens every analysis of the case — on the
  interface thread. On a case with dozens of analyses the window stopped responding for
  minutes, before any progress could be shown, and the run looked like a hang. The reader
  is now built in the worker thread like the hunt itself; `launch()` returns at once, the
  button stays disabled while the hunt runs, and interrupting still reaches the reader.
- A test holds the rule: with a reader that takes 0.8 s to construct, `launch()` returns in
  under 0.4 s and the hunt still completes.

# Fireblade 0.7.1 — the assistant knows the whole case

0.7.0 gave the case a workspace, a graph, a report and a certificate. This patch fixes
what the first evening with a real multi-source case showed.

## The assistant no longer mistakes one analysis for the case

- When a case holds several analyses, the brief handed to the model names them — file and
  row count — and says that the rows it read come from the analysis open in the window. A
  question about `iis.log` while `hayabusa-alerts.csv` is on screen gets an answer that
  knows the other one exists, instead of a confident answer about the wrong source.

## A corrupt workspace is reported once, in the panel

- An unreadable `workspace.json` used to open an error dialog on every case switch. The
  tracking panel now keeps the message on its own status line, the rest of the window
  keeps working, and the file can be repaired or restored.

## The Linux stress benchmark checks what it reads again

- It hooked `csv.DictWriter` and looked for the old French row labels, while `linux_logs`
  writes through `csv.writer` with `Structured`/`Raw`. It validated nothing and its count
  stayed at zero, which turned the CI step red the first time the file was touched. It now
  validates every row: 1 GiB of records at 53 MiB/s, 1 024 records verified, 79 MB peak
  memory, and the persisted collection check passes.

## Release housekeeping

- An early archive published as "Fireblade 0.7.0 — archive (old numbering)" was renamed:
  its title blocked the real 0.7.0 through the release guard, which refuses a version whose
  name already exists.

# Fireblade 0.7.0 — the case becomes something you can hand over

The analysis was already readable. What an engagement needs next is the paperwork: who
owes which action, what the attack looked like, what the client receives, and what
happens to the evidence once the mission is over. This version adds those four surfaces
and stops treating every disk image as a raw file.

## Actions, indicators and machines, tracked in the case

- A new **Actions & suivi** tab holds the tracking table, with exactly the columns used on
  the client side: **Date · Priorité · État de l'action · Type d'action · Intervenant ·
  Détails**. A row is edited in place, closed with one click, reopened, or deleted.
- The table reads one case or **every case**, and the global view adds the Case and Client
  columns: one company with several machines, several companies in the same window, one
  list.
- The same tab records the **indicators** (normalised by the same code the IOC hunt uses)
  and the **machines and accounts** of the case. Indicators can be imported from a text,
  CSV or TSV list; duplicates are refused rather than silently merged.
- Everything is stored in `<case>/workspace.json` — atomic write, revision check, 8 MiB
  bound, strict validation. The portable-case archive already carries that file.
- **Exporter le suivi…** writes the visible table as a semicolon CSV with a BOM, which
  opens in Excel without an import step.

## The attack graph, tagged by the analyst

- A new **Attack graph** tab lays the case out along the kill chain: hosts on the left,
  techniques in the column of the tactic they declare, the indicator nodes beside them.
  It is built from the Hayabusa findings, the tracked indicators and the declared
  machines — nothing is inferred that the data does not say.
- A node is dragged, tagged with any label (the MITRE tactics are offered, a free label is
  accepted), and the tags are stored in the case. A rebuild keeps them, matched by node
  identifier, so a new Hayabusa run does not lose the work.
- The canvas is exported as PNG and embedded in the client report.

## A report for the client, not for the analyst

- **Fichier → Rapport client…** produces one document — HTML or PDF — with the cover and
  confidentiality line, the executive summary and severity counts, the scope and the
  machines, the evidence inventory with the SHA-256 taken at import, the timeline windows,
  the detailed findings, the attack graph, the tracked indicators, the action table, the
  destruction record, and the method and limits.
- A section with no data says so instead of disappearing: a report that omits the
  indicators looks like a report that found none.

## Destroying evidence, and proving it

- **Fichier → Détruire des preuves…** overwrites the selected files of the case with the
  **DoD 5220.22-M** scheme in **3 or 7 passes**, reads the file back to verify the last
  pass, then removes it. The scheme, the pass count, the operator, the witness and the
  reason are recorded.
- The **procès-verbal** (HTML and PDF) lists every file with its size, its SHA-256 before
  the first pass and the SHA-256 of the read-back, the state of each file, the signatures,
  and the photographic annex — the photos are copied into the case and fingerprinted, and
  a modified photo is left out of the document rather than silently included.
- The certificate states what such an overwrite can and cannot prove: logical blocks are
  rewritten, but flash wear levelling, copy-on-write filesystems and journals may keep
  physical copies. It is a record of the operation, not a NIST SP 800-88 certification.
- The case's own record — `case.json`, `workspace.json`, the session, the history — is
  never listed for destruction and is refused if a path points at it.

## Disk images: E01, and split sets

- An `.E01` segment is read through Dissect's EWF container; the fixture published by
  `dissect.evidence` is now part of the test data and is opened by the suite.
- A **split acquisition** (`E01`, `E02`, …) is collected in order and handed to Dissect as
  one disk. A missing segment is a refusal, not a shorter disk: reading only the first
  part would truncate the evidence silently.
- The "no filesystem" error now names the case it found — container recognised, no usable
  partition — instead of a generic failure.

## The assistant proposes the next question

- The assistant answers well when it is asked well, and a 2B model asked "what next"
  invents a priority. Three **guided questions** now sit under the question box, read from
  the case itself: the worst finding and its host, the benign explanation that would fit it,
  the busiest host, a lateral-movement question when more than one host is involved, the
  first tracked indicator, an open action's machine.
- A click only fills the box; nothing is sent until the analyst presses Ask. A case with no
  finding gets the three questions that make sense on an empty case.

## Log formats an incident actually hands over

- **IIS / W3C** logs are parsed with their `#Fields:` declaration: date, time, verb, URI,
  status, client address, user and agent become columns, and the four `#Software`/`#Version`
  comment lines are recorded as declarations instead of inflating the raw line count.
- **Windows Event Viewer CSV** keeps quoted commas, a BOM and CRLF; **AmcacheParser CSV**
  loses its BOM before the first header; **TSV** keeps its columns.
- **JSON Lines** (journald, Sysmon JSON) are recognised field by field, **PowerShell
  transcripts** in UTF-16 and **cp1252** logs keep their accents.
- An empty file is refused with a reason instead of becoming an empty analysis the case
  has to carry and every report has to skip.

## A portable case that carries what the case knows

- The portable archive now includes the workspace, the destruction records and the
  assistant conversations (`include_extra_files`). Before, a portable case reopened as an
  empty shell: the actions, the indicators and the conversations stayed on the machine.
- An imported case keeps those files under `case-extra/`, which is the archive's existing
  layout; the workspace and the destruction records are now read and written there, so the
  certificate's photographs still resolve after the move.
- Importing an indicator list writes the workspace once, not once per indicator: 3 000
  indicators in a single save.

## Measured strain

- A 512 MiB evidence file destroyed with the three-pass scheme: 13.2 s (three passes plus
  the read-back), certificate written.
- 800 findings over 120 hosts: 324 graph nodes, layout and SVG in 0.01 s.
- 300 findings in a client report: 0.1 MB of HTML, under a second.
- 2 000 actions and 5 000 indicators: a 2.85 MB workspace, saved in 0.31 s and loaded in
  0.08 s.

## What this version still does not claim

- The E01 fixture has no filesystem: the container is qualified, the reading of NTFS or
  FAT *inside* an E01 still needs an image acquired from a real medium.
- The 8B assistant model has still not been measured, for lack of a GPU here.
- On flash storage, overwriting is not physical sanitisation; the certificate says so.

# Fireblade 0.6.1 — the assistant works the case like an analyst

0.6.0 taught the assistant to read a case. This version teaches it a method: the same
first pass every time, then its own lookups, then an answer that separates what was seen
from what it deduces — and a conversation that belongs to the case instead of the window.

## A conversation the case keeps

- Every turn is written to `assistant/conversation-<date>.jsonl` **inside the case**, at
  the moment it happens. Close the window, reopen the case next week: the exchange is
  there, in the panel's conversation list, and the next question continues it.
- `New` starts a fresh thread without losing the previous one. A half-written answer
  costs one line, never the conversation.
- The list is read from the case folder, so a conversation can be replayed on another
  machine that has the case — nothing is stored in the application profile.

## A method, not a prompt

The assistant now follows a written method: turn the question into the decision it feeds;
keep observation and inference in different sentences; never read a timestamp alone; name
the benign explanation that fits the same rows; say what is missing and which artifact
would settle it. The answer starts with the verdict, then the evidence, then the
explanation it could not rule out, then one next check.

## It always looks first, then it digs

- **The first pass is not left to the model.** Every question reads the case the same way
  — what it contains, its detections, the minutes around the worst of them, and that same
  window in time order. A small model asked "what next" before it has seen the detections
  opens the wrong door.
- **Then it chooses up to two more lookups itself**, from a menu that now includes the
  moves an analyst actually makes: `around` (the minutes around a detection), `sequence`
  (the same window in order), `entity` (everything one host, account, path or binary
  touches), `rare` (the values that appear once, where hunting starts), `stats` (a column
  at a glance), `timeline` (where the activity sits).
- An empty lookup stops the digging instead of feeding the model a blank page.

## It analyses, it never acts

- Every lookup is a read. The lookup layer refuses any statement that is not a `SELECT`,
  a `PRAGMA` or a `DESCRIBE`, before it reaches DuckDB, and the method says it in the
  prompt: this assistant changes nothing in a case.
- Verified on the real window: the analysis file is byte-identical after a full
  question/answer/next-question cycle, SHA-256 compared before and after.

## What it still is

A local model, 2B or 4B by default. It reads, it correlates, it names its evidence and it
admits what it cannot settle — but a chain of five deductions is still an answer to check.
The method and the lookups are what make it useful; the model is the ceiling.
# Fireblade 0.6.0 — the assistant reads the case, and the dial answers the click

The local assistant was a single question about a single finding: forty rows in, a
JSON object out, no memory of what you asked before and no way to look anything up.
This version makes it a conversation, and it gives it the case.

## A conversation, not a form

- The question box is a **transcript**: your question, then the answer, then the next
  question with the previous exchange still in front of you.
- **Nothing needs to be selected.** Ask about the whole case — how many hosts, what
  happened around ten o'clock, which detections matter — and the assistant reads the
  case to answer.
- It answers **in the language you wrote in**. Ask in French and the answer is French;
  a file path, a rule name or a timestamp stays exactly as the case spells it.

## It looks before it speaks

- Four bounded lookups, and no SQL of its own: **overview** (hosts, sources, time span,
  counts), **search** (events matching a word, a host or an event id), **findings** (the
  detections, most severe first), **artifact** (one artifact kind at a time).
- The turn is two model calls: one that picks the lookup, one that writes the answer from
  what came back. The transcript says what was read — `Read: search (25 row(s))`.
- A lookup that finds nothing, or a case imported without the column the question needs,
  says so instead of inventing a host or a time.

## The dial answers the click

- A ray of the **Clock** view is four pixels wide and its tip was a sixteen-pixel square:
  clicking the line itself did nothing. The whole ray now answers, along its length and a
  little either side, and hovering it names the finding it stands for.
- A slice that holds several findings opens the **most severe** of them, not whichever
  was drawn first.

## One table per artifact family

- The layout choice was greyed out whenever the parse was set to publish files as they
  arrive, which left one usable choice on screen: a collection of a hundred EVTX files
  became a hundred tabs.
- **By artifact** is now reachable in that situation and picking it stops the streaming:
  the parse finishes, then Security logs land in one table, AppX in another, Amcache,
  Prefetch, MFT and the rest each in their own.

## What this is not

- The bundled model is a 2B model on CPU: it reads, it compares, it answers plainly, and
  it is slow. It is not a reasoning engine, and an answer that needs a chain of five
  deductions is still an answer to check.
- Nothing is downloaded unless you ask for it, and the assistant stays optional.
# Fireblade 0.5.2 — an archive Windows can open

0.5.1 shipped as a folder, and one file inside it carried a path long enough to stop
Windows Explorer at 260 characters: the download could not be extracted by
double-clicking it. This patch fixes the archive and nothing else.

## The rules tree is flattened

- The Sigma rule set was nested `sigma/sysmon/emerging-threats/2023/Exploits/CVE-.../`,
  which is twelve folders deep before the rule name starts. Hayabusa reads a rule by its
  content, never by its folder, so the tree is now two levels deep (`rules/hayabusa`,
  `rules/sigma`) and every rule keeps its bytes and its file name.
- Anything still above the limit — a plugin, a parser fixture — is renamed with a short
  stable suffix, and the build refuses to finish if a single entry is still too long.
- The rename map is written to `shortened-paths.json` beside the tools, so a rule named
  in a report can still be found.

## What did not change

- No behaviour, no interface, no import: 0.5.2 is 0.5.1 with a working archive.
- Every entry of the published archive is now under 160 characters, which leaves room
  for an extraction folder of about a hundred characters.

# Fireblade 0.5.1 — an import that never loses a file in silence

Every other screen in Fireblade is worth what the import put behind it, and one file
that vanished without a reason is enough to make a report indefensible. This version
rebuilds the import around one rule: whatever happens to a file, its row says what
happened, and the operation itself leaves a record that survives the window.

## One operation, several sources

- The Imports picker now takes **files and folders in one list** — a KAPE output, three
  EVTX copied to the desktop and a folder of Linux logs are one import, with one report,
  one journal and one working folder. Each item can be removed before starting; a path
  added twice is kept once.
- The sources are read in the order they were given, and every one of them gets a row.
  A folder inside another selected folder is not read twice.

## Resume where it stopped

- **`Resume an import…`** notices an operation that was stopped, or never finished, and
  offers to continue it instead of pretending the collection is done: `N file(s) never
  read. Continue it now?`
- What is already read is kept — its analyses stay on disk and are not imported again.
  Only the rows that are still pending, interrupted, or whose analysis file disappeared
  are read again.
- A **merged layout** (one tab per artifact, or one unified grid) is derived, not stored:
  a resume rebuilds it from the analyses it merged, instead of trusting a table that may
  be the file that went missing.

## Nothing counted twice

- Duplicate detection is done on the **SHA-256 of the source file**, the only identifier an
  examiner can defend. Inside one operation, two copies of the same export are read once:
  the second row is `Duplicate`, and its reason names the copy that was read.
- Across imports of the same case, an index beside the collections
  (`Collectes/import-index.json`) records what was already read, so re-selecting a folder
  by mistake produces a report instead of a second set of tabs: `Already imported from
  <path> (<collection>)`.
- A duplicate is neither a success nor a failure: it has its own filter in the table, its
  own count in the summary, and it never becomes a tab.
- **A disk collection is the exception, and on purpose**: two partitions holding the same
  bytes are two artefacts at two locations, and the report keeps both — deduplicating them
  would erase where one of them was found.

## A proof after the write

- Each analysis is **opened again read-only and counted**: the number of events actually on
  disk is compared with the number recorded at import. The verdict is stored per analysis
  and summarised in the report — `Verification: 214 checked · 0 failed` — and a mismatch is
  a line in the journal, with both numbers.
- A database that cannot be opened, or a file that is gone, is a result too (`unreadable`,
  `missing`), not an exception during the next click.

## A journal for every file

- Every operation writes **`journal.jsonl`** next to `collection.json`: one JSON object per
  event, with a UTC timestamp, the seconds since the operation started, and what happened.
  The operation's start and end, the inventory, one line per file (status, reason, seconds,
  analyses written), each duplicate, each memory-budget retry, the organisation step and the
  verification are all there.
- The file is written line by line and flushed as it goes, so an operation that dies still
  explains itself; and if the journal cannot be written at all, the report says
  `Journal incomplet : <reason>` instead of passing for a complete record.

## One bad file costs one row

- A reader that raises — a parser that crashes, a file locked by another program, a bug in
  a format nobody tested — now marks **that row** as `error` with its message. The
  operation carries on with the other files, and the report's status is not turned into a
  failure by one file.
- The same isolation applies to the workers: an exception that escapes a parsing worker is
  recorded on its own row instead of unwinding the merge loop and ending a collection that
  had already read two thousand files.

## The tree says what the evidence is

- A source saved under a long collection path used to appear as that path of which a narrow
  panel showed only the beginning. The tree and the collection list now show the **type of
  evidence**: `Event logs · Security`, `Amcache`, `Browser history`, `Browser cookies`,
  `Prefetch`, `MFT`, `NTUSER.DAT`, `Jump lists`, `Shellbags`, `SRUM`, `PowerShell history`.
- When Fireblade does not recognise a file, the label is **the folder it was found in**, with
  the plumbing (`Saved_Files`, `C:`, `Users`, `AppData`, a profile name) skipped. Two entries
  that would read the same are separated by the file name, then by a number. The full path is
  never lost: it is the tooltip, and the report keeps it.
- Existing collections are renamed the same way when they are displayed, so an older case
  reads like a new one.

## A launch that costs the ident and nothing else

- **The application is now a folder, zipped once**, instead of a single executable that
  unpacked itself at every launch. Measured on the same four-core VM, three runs each: the
  0.5.0 executable took **41 to 50 s** to answer `--help`, because a onefile build
  re-extracts ~280 MB into `%TEMP%` at every start while Defender scans each extracted DLL.
  The folder build answers the same command in **0.6 to 0.9 s**, and after the unzip there is
  nothing left to extract. The download is the same size as before (280 MB) and the folder
  takes 510 MB on disk once.
- **The 6.5 s ident is kept** — it is the product's signature — but it is now the *floor* of
  a launch, not an addition: its clock starts with the process, so the window's 0.32 s build
  happens inside it. A build slower than the ident is shown at once, never waited on twice.
- The verification still proves the promise: it copies the folder into an empty directory,
  strips `PATH`, `PYTHONPATH` and `QT_PLUGIN_PATH`, moves `TEMP` and `LOCALAPPDATA`, and runs
  the exe's own 47 checks there. A missing DLL fails the build, not a tester's machine.

## The assistant is optional, and says so

- Nothing is downloaded unless the analyst clicks **Set up the local model…**. The tab used
  to describe a missing install as a fault ("no model file yet, put the GGUF in…"); it now
  says the feature is optional, that a finding is explained from the data alone, where the
  model *would* live, and that nothing is fetched without a click.

## Counts that add up

- `report['summary']` is computed once, from the rows the table shows: one number per state,
  the number of files, and the number of analyses. The tab's summary line quotes it, counts
  duplicates separately, and adds the verification line, so the sentence at the top and the
  rows underneath can no longer disagree.

## What was tested

- Thirteen core tests on synthetic evidence: mixed sources, a file no reader knows, a
  duplicate inside one operation, a duplicate across two imports of one case, a reader that
  raises, a cancelled operation resumed, a resume whose analysis vanished, the journal's
  completeness, an analysis that lost a row, a journal that cannot be written, retries.
- The picker and the single-operation gesture in the interface suite: one report for a
  folder, a second folder and a loose file, and a cancel that leaves one collection and no
  queued work.
- The full gate, and the acceptance run on the Windows test VM.

## What this version does not do

- It does not merge two collections of one case into a single report; each import keeps its
  own folder, journal and report.
- The duplicate index is per case, by digest: the same evidence imported into two different
  cases is read twice, which is what those two cases asked for.

# Fireblade 0.5.0 — the Hayabusa findings map, and a local assistant that answers

An analyst should not read 35 000 alerts one by one, and a small local model should never
be the thing that decides what is true. This version does the first, and lets the second
help without being trusted.

## A new tab: Hayabusa + AI

- The alerts of a Hayabusa analysis are **grouped in DuckDB**: one rule on one host, one
  burst. Three identical alerts three minutes apart are one finding with a count, not
  three rows. Grouping runs as a window function over the events table, so a collection
  with millions of rows never has to fit in memory; a grouping that fails falls back to
  the in-memory path and says so in the header.
- Findings are gathered into **time windows**, ordered by the clock, so a chain reads as
  a chain.
- **Three painted views**, one selector. The day is a **polar histogram**: one ray per ten
  minutes, its length the number of alerts in that slice, its colour the worst severity in
  it, so a quiet morning is a row of short ticks and the incident is a spike. The heat map
  gives one row per rule over time; the chain shows the events of the selected finding and,
  once the assistant has answered, the links it asserted.
- The views follow the window's own theme, light or dark, and use the same severity
  colours as the rest of Fireblade.
- A finding whose timestamp cannot be read is **counted and reported**, never silently
  dropped.

## The local assistant

- **Optional, installed once.** `Set up the local model…` downloads the CPU build of
  llama.cpp (pinned tag) and the MiniCPM5-2B weights (Q4_K_M, 1.5 GB, digest checked),
  then writes `assistant.json` beside the user's cases. Fireblade works identically
  without it, and the tab still explains a finding from the data alone.
- **Before it speaks, it checks the machine**: weights present, engine present, memory
  available. A missing piece is a sentence, not a stack trace.
- **Explain this finding** sends a bounded evidence pack — the finding, its events
  numbered `[evt n]`, the other findings of the same window, and what could not be
  established — and asks for JSON: summary, facts with the events they rest on, links
  between events, and what is missing.
- **The answer is verified before display.** A fact that cites no event, or an event that
  is not in the pack, is dropped with its reason; a link is kept only when both ends
  exist. A well-formed answer is not a true one.
- **The prompt says which numbers exist.** Telling the model that the valid event numbers
  run from 1 to N raised the facts kept from 1.3 to 1.5 per finding and cut the dropped
  ones by about half; a worked example in the prompt made answers shorter and *worse*, so
  it is not used.
- **Links are drawn**, not described: the chain view shows the arrows the model asserted,
  labelled with the event numbers they join.
- **One question at a time**, with the elapsed seconds on screen; asking twice says so
  instead of queueing a second call against the same engine. An answer belongs to its
  finding and comes back when you return to it.
- **An engine that dies is restarted once.** On a machine of eight gigabytes the server did
  exit mid-answer; the socket is then refused, and the call is retried on a fresh engine
  instead of leaving a dead feature behind.
- Measured on the four-core, eight-gigabyte test VM, no GPU: **25 to 45 s** for one
  explanation (six findings, mean 28 s), **29 s** for a follow-up question, and the engine
  stays loaded between questions. An answer that is cut off at the token budget is reported
  as cut off, not as malformed.

## What this version does not do

- No fine-tuning; the model is used as shipped, with the prompt this version ships.
- No multi-hop investigation: the assistant explains one finding and answers questions
  about it, it does not drive the analysis.
- The evidence pack is bounded at 40 events; a finding with more occurrences says how many
  were not read.
- The .NET forensic pack is unchanged: this version adds no new artefact parser.

# Fireblade 0.4.2 — eight times less time on the same collection

The 0.4.1 acceptance run measured what a Linux collection costs: 50 min 49 s for
9.74 GiB. The same folder is now read in **6 min 0 s**, with the same 246 analyses
and the same status breakdown. Nothing was added "to go faster": the three causes
were first measured, then removed.

## The reader read on a single core, without saying so

- Eight import threads did not give eight cores: the log reader is pure Python, and
  the GIL serializes them. Measured on two 250 MB logs: **28.3 s for the first,
  50.8 s for both run in parallel, that is 1.11x**.
- Each file is now read **in its own process** (eight interpreters sharing the
  queue): four 250 MB files go from 11.7 to **34.7 MB/s**. In the frozen executable,
  the binary relaunches itself with `--parse-worker` before loading Qt, so the gain
  applies to the installed version too.
- If the pool does not start - machine out of memory, trimmed binary - the
  collection carries on in the current process and says so, instead of failing.

## Provenance no longer copies every CSV

- Each parser CSV was **copied line by line in Python** to add two provenance
  columns: the whole collection rewritten a second time, line by line.
- Those columns are now added **by the import itself**, while reading: same result,
  a single pass, no intermediate file.

## Nine regular expressions per line, for nothing

- The format does not change from one end of a log to the other, and yet every line
  tried nine formats before finding the right one. Substring tests now rule out the
  impossible branches, and the write goes through `csv.writer` instead of a
  `DictWriter` rebuilt on every line: **8.8 to 11.7 MB/s per core** on the same
  file, without changing a column or a value.

## What it gives

- Collection 9.74 GiB / 259 files: **50 min 49 s to 6 min 0 s**.
- Throughput: **3.3 to 27.6 MB/s**.
- Identical result: 246 analyses, 224 complete files, 31 to verify, 4 unsupported,
  no missing file.
- A 100 GB collection therefore goes from about eight hours to about one hour.
- And a **single very large file** no longer waits for its turn: it reads in ranges
  too (see the next section).

## A single huge file reads in ranges too

- A folder parses on every core, one process per file; one file larger than the rest
  stayed on a single core at 11.5 MB/s. It is now cut into line-aligned byte ranges,
  one per worker, and the CSVs are glued back in order: same rows, same line numbers,
  same offsets, **byte for byte**.
- Measured on a real 250 MB access.log (1 752 069 lines): **22.8 s read alone, 6.1 s
  in four ranges, 3.4 s in eight** - 11.5, 43.1 then 76.3 MB/s. The merged CSV is
  identical in all three cases (747 340 923 bytes).
- Six 250 MB logs read together, which is the folder case: **23.7 s to 18.3 s**
  (55.3 to 71.6 MB/s), same 4 721 861 rows. Splitting costs the folder nothing.
- Only plain text is split. A compressed file, an archive, a UTF-16 file, a systemd
  journal and a header-driven format (Zeek TSV, W3C) are refused: a range that starts
  in the middle of a file has no header to read, and a wrongly cut record is a wrong
  analysis, silently.
- The ranges are found by one pass over the file counting newlines (0.15 s for 250 MB)
  rather than guessed, so line numbers and offsets stay absolute.
- A batch takes the whole pool at once, one batch at a time: two big files each
  holding half the workers while waiting for the rest is a deadlock, and it was
  written out of the design rather than reproduced.

## Verification

- New tests: reading in a separate process, fallback to the current process when the
  pool does not start, provenance carried by the import, ranges that start on a line
  boundary with their line number, a sliced read that gives the rows of a whole read,
  a compressed or wide file that is refused, a batch in order.
- Full suite on the range reader: 1 452 passed, 28 skipped, ruff clean, real window.
- Full suite run on the tree that was tagged: 1 475 passed, 28 skipped, ruff clean.
- End-to-end measurement on the same collection as 0.4.1, same machine, same
  reference files.

## What the acceptance run found, and what is now fixed

The 0.4.1 acceptance run covered eight sections on a clean Windows 11 virtual
machine, 282 checked steps: 274 passed, 1 to review, 7 failed. The failures are
fixed here, each with a test.

- **The coverage audit went silent after a hunt.** Once an IOC hunt had run, the
  window still held a query, `can_open_file()` stayed false, and the audit's
  `launch()` returned without a word: the user clicked, and nothing happened, with
  no way to know why. It now says the check waits for the running query, starts by
  itself as soon as the query frees the window, and explains what to do if the
  query never ends.
- **The report's Reason column was empty** for every file that was not fully read,
  although the reason existed: it lives on the run, or on a member of an archive,
  never on the file itself. The file now carries its own sentence, taken from the
  reader error, the member or the warning, deduplicated; a file no reader claims
  says so instead of leaving a blank cell.
- **An annotation export could hand over an empty file.** The note was in the
  database - the export intersected it with the filter in force (52 581 rows out of
  420 487, the annotated row outside) and wrote a header-only CSV without a word.
  It now refuses, names the count held by the analysis, and writes nothing.

- **The Read type column said its values in French.** `Structurée` and `Brute` were
  written by the parsers as data, so no translation table could reach them: an English
  interface showed French in every log analysis. The parsers now write `Structured` and
  `Raw`; the code that counts them still reads the old French words, so an analysis
  produced by an earlier version keeps working and keeps its values.
- **The column filter fields said nothing about their column.** Every field carried the
  same French hint, and its accessible name announced a position - "Filter the column 3" -
  which is what a screen reader reads out. The hint is translated and the name carries the
  real header; the sort buttons announce ascending and descending in the chosen language.

- **A Zeek or W3C header counted as raw data.** `#separator`, `#fields`, `#close` and
  `#Software` were emitted with the raw state, so the report announced raw lines that were
  declarations and the data rows were mixed with them. They keep their line, their offset
  and their text - the evidence is unchanged - but carry their own state, counted apart.

- **The active-filter list and the report's own help text stayed French.** A filter was
  shown as `Statut  Égal à (exact)  404` - the column header and the operator were read raw,
  so translating the table could not help. Both go through the translation now, and the
  report's help line is translated too.
- **The scan that hunts leftover French cried 61 times for two real hits.** `Source`, `Date`,
  `Sans Serif` and ordinary English sentences matched its list. It now uses the curated
  vocabulary of the inventory, which leaves one real hit - the filter list above - and
  stops hiding the rest.

- **The status bar had no room left for its own message.** Five permanent widgets
  met the left side of the bar - the version, a copy of the case name already in the
  window title, the global-rules summary, the coverage badge, the save stamp - and a
  running collection added a label, a progress bar and Stop that then stayed for the
  rest of the session. On a 1024-pixel window the analyst read `2 ite`. The case name
  leaves the bar, the progress block disappears with the run, the save stamp steps
  aside while a collection runs, and the running label elides with its tooltip
  carrying the whole sentence.
- **The Imports table stayed empty while the collection advanced.** Counters moved,
  the table showed "0 files in this view", because the report was only published at
  the end. It now follows the run once a second: rows are appended, the cells of the
  rows already shown are repainted, and the model is reset only when a file leaves.
- **"Full report" printed the whole page in French.** The text is assembled after the
  language pass, so no widget pass could translate it. Every line is now translated
  where it is written, status words included, and the table headers that were still
  French (Readers, Reason) have their entries.
- **Three analyses of the same family gave three identical tabs.** The tab is named
  after the evidence file, so three `CarsDB.db` from different folders were
  indistinguishable. A shared label now gains the shortest run of trailing folders
  that separates it - `active.txt · System32/config` - and two analyses of the very
  same file fall back to ` (2)`.
- **Preferences answered "Automatic" to a question about quantities.** Memory per
  analysis and both thread fields showed `Current configuration` or `Automatic`
  instead of a number. The field now reads out what automatic resolves to on this
  machine, computed by the same helper the engine uses: `Automatic · 2048 MB`,
  `Automatic · 8 threads`. The stored value is still 0.
- **The IOC hunt summary stated its counts in French.** The line under the results
  table - status, rows read, matching fields, details kept, scope, rejected
  indicators - was composed in French after the language pass, so an English
  interface showed `Terminée · 2,499,027 lignes lues · ... 1 IOC rejetés` on the
  screen an analyst reads after every hunt. Each piece is translated where it is
  written, the counts go into a translated template, and the indicator types read
  IP, Domain, URL, MD5.
- **The coverage panel stated its findings in French.** Causes, impacts and proposed
  actions are written by the engine, land in a table model and a text pane, and
  neither goes through the language pass; the status line and the badge are written
  after it too. The panel translates every cell as it displays it, and 135 table
  entries cover the reasons the engine raises, the coverage explanations and the
  export receipts.

## Known limits of this version

- A Windows install without `LongPathsEnabled` cannot open paths beyond 260 characters: the
  product relies on the operating system for extended paths, and two tests fail on a fresh
  Windows until the key is set. Documented rather than worked around.
- The collection has no per-file analyses in its session: it publishes them merged by family
  (`Prefetch.csv`, `MFT et USN.csv`, `EVTX.csv`), and the per-file ones stay on disk in
  `Collectes/<stamp>/analyses/`. That is the chosen organization mode, not a loss.
- Messages raised by the engine for a technical failure are still written in French in the
  source (916 of 924 visible strings are translated; the residue is in the deepest error
  paths).

Full suite after these fixes: 1 459 passed, 28 skipped, ruff clean, real window.

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
