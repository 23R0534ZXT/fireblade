# Desktop → Host, the exhaustive audit

This page exists because the first parity count was wrong. `HOST-PARITY.md` is built
from `scripts/parity_inventory.py`, which reads **menu actions with literal labels**.
It misses whole screens: a dialog opened by a button, a feature whose action is a
`QAction('…')` constructor, a panel behind a tab.

`scripts/desktop_surface.py` reads every Qt widget call that carries a literal:
actions, buttons, checkboxes, tabs, dialog titles. On the desktop sources it finds
**362 distinct labels** (148 actions, 152 buttons, 50 dialog titles, 19 tabs), against
157 for the menu-only inventory. That is the surface this audit compares.

## What the numbers mean

| Inventory | Labels | What it sees |
| --- | --- | --- |
| `parity_inventory.py` | 157 | menu and toolbar actions with literal labels |
| `desktop_surface.py` | 362 | actions **and** buttons, dialogs, tabs |

Neither is "features": a feature can be one dialog with twelve buttons. The audit
below is therefore by **domain**, with the desktop's own screens as the unit, and it
names what the Host does for each.

## Verdict

**No feature of the desktop is missing from the Host.** Twenty-one domains are
covered, one feature is partial (`Import — cancel`, the stop lands at the
collection's checkpoints), and six are declared with a reason — the .NET Timeline
Explorer DLL, the AI assistant, French/English, file-manager and window-manager
gestures, and destruction photo attachments. Every one of them is a decision about
the edition, not a screen that was forgotten.

This page began as an audit of 21 domains, and it found nineteen missing features.
They were closed in eighteen batches, each proved by a real API call and a browser
session, and each one is named at the end of this page. `HOST-PARITY.md` still counts
**menu commands**, not features; its "nothing left" line is withdrawn and points here.

## The domains

Legend: **yes** = the Host does it, **partial** = it does part of it, **no** = missing.

| Domain | Desktop screens and commands | Host |
| --- | --- | --- |
| Window, menus, tabs | 9 tabs, 6 menus, status bar, toolbar | **yes** |
| Command palette | "Commandes" (a keyboard launcher over every command) | **yes** — Commands… (Ctrl+K): every command the window offers, filtered and run |
| Messages | "Messages" (the application's own log) | **yes** — View > Messages: every line the status bar showed, newest first |
| Open analyses | "Analyses ouvertes…" (list, close, reorder) | **yes** — Analysis > Open analyses: open, close, reorder the tabs and keep the order |
| Open analyses — closed | a closed tab stays in the case and opens again | **yes** — the tree lists "Closed (kept in the case)"; the session keeps it in its own `closed` list, as the desktop does, and an import never drops it |
| Cases | new, edit, destroy (DoD + certificate), archive, restore, portable `.fireblade` | **yes** |
| Case history | "Historique et récupération" (the History folder) | **yes** — Case > History and recovery: the recorded states, restored after keeping the present one |
| Import — file, folder | three layouts, preview, CSV options, history file by file | **yes** |
| Import — workbook | an XLSX/XLS sheet, chosen by name, formulas read as text | **yes** — the preview lists the sheets and their columns, the import reads the chosen sheet through `Case.import_excel` and names the analysis after the file and the sheet |
| Import — disk | "Analyser un disque…" (an image, not a folder) | **yes** — Analysis > Analyse a disk: a mounted volume, a disk image or a device; the walk copies its artifacts out and reports what it visited, extracted and failed on |
| Import — cancel | "Arrêter" during a collection | **partial** — an import runs as a job with its progress line and a Stop, but the stop lands at the collection's own checkpoints: a source read in one pass finishes first |
| Import — report, file by file | status, reason, reader, "écarter du bilan", "supprimer" | **yes** — Imports > Import report: every collected file, filtered; Set aside (reversible, the entry keeps its reason) and Remove (the core refuses it when the hash changed since the collection) |
| Import — retry with a reader | "Relancer avec un lecteur" on an unread file | **yes** — Imports > Read a file again: the unread files, the reader to try, and the decision written in the collection report |
| Import — diagnostics | "Vérification des imports et diagnostics", "Familles attendues" | **yes** — Imports > Import verification (the core coverage audit, four expected-family profiles, JSON and CSV report) |
| Grid — sorting | one column, multi-column, **a priority dialog** | **yes** — Sort priority (add, reorder, remove, direction), on top of shift-click |
| Grid — filters | per column with operators, advanced ET/OU/NON | **yes** |
| Grid — relative dates | "Filtrer une date…", "Ajouter une condition de date relative" | **yes** — Filter a date: the core's 25 named windows, or one day / month / year, added to the advanced filter |
| Grid — grouping | by column, date intervals, drill-down | **yes** |
| Grid — group summaries | "Résumés et tri des groupes" | **yes** — up to 16 aggregates beside each group, and the groups ordered by count, value or a summary |
| Grid — bookmarks, notes | row marks, row notes, cell notes, on a selection | **yes** |
| Grid — colour rules | local rules, from a cell, the value chart and its statistics | **yes** — colours, text colour, bold, row or cell target, the value chart, and the statistics (most and least frequent, duplicates, values seen once, above or below the average) resolved on the server |
| Grid — visual styles | data bar, two- and three-colour scales, icon sets with thresholds and percentiles | **yes** — Visual, Bounds, Minimum/Maximum/Middle and the icon thresholds in the rule editor; the bounds are resolved by the core (`resolve_rules`) and each cell is painted with the desktop's own arithmetic |
| Grid — global rules | "Règles globales" shared by every analysis | **yes** — Colour rules > Every analysis; the book is the desktop's own file (import and export), a rule the grid cannot evaluate is skipped, never approximated |
| Grid — columns | hide, pin left **and right**, resize, layout in the analysis | **yes** |
| Grid — derived columns | timestamp conversion, expressions, categories, MACB | **yes** |
| Grid — views and profiles | named views, "Appliquer le profil détecté" | **yes** — named views, and the detected profile applied by hand (date and boolean columns, default sort, its colour rules) |
| Grid — exports | CSV, copy value / rows / cell, whole cell | **yes** |
| Grid — pivot and EVTX | "Qu'est-ce qui a lancé", source event, EVTX context | **yes** |
| Timeline | build, histogram, legend, correlate, page, three date readings | **yes** |
| Timeline — working the chart | zoom, pan, fit, back, isolate a source, select a duration | **yes** — Zoom +/−, Fit, Back, Show all sources, a drag that selects a duration and filters the rows below, shift-drag to pan, the wheel to zoom, a chip to hide one source |
| Timeline — extras | export, "Inclure sans date", "Appliquer les filtres des analyses", "Ouvrir la ligne source" | **yes** — verified CSV export with its receipt, rows without a date on request, each analysis read through its own filters, and a click on a row opens its source line |
| IOC hunting | paste, scan, results, saved hunts | **yes** |
| IOC — extras | import TXT/CSV/TSV, all analyses at once, respect the filters, sub-domains | **yes** — IOC hunting: a file or a paste, every analysis, each view's filters, and sub-domains on or off |
| Hayabusa | run by level, findings, tactics, dedup, mark, open, export sources | **yes** |
| Hayabusa — rules | "Règles de détection…" (enable, disable, override) | **yes** — Hayabusa > Detection rules (filter, edit, enable/disable, reset) |
| Hayabusa — maps | Clock, Heat map and Chain views of the findings, "Grouped by" level, computer or rule | **yes** — Hayabusa > View (Table, Clock, Heat map, Chain) and Grouped by; drawn on a canvas server-side data |
| Hayabusa — assistant | "Explain this finding", "Ask", local model | **declared** — no model is connected |
| Attack graph | build, layout, ATT&CK layer, PNG, free node with tags | **yes** |
| Workspace — machines and accounts | "Machine ou compte" (declared hosts, accounts), change one, remove one | **yes** — Actions & tracking > Machines & accounts: the form adds and saves, a row is edited in place or removed |
| Workspace — actions | add, change (status, owner, due), remove | **yes** — Actions & tracking: the row closes or reopens, and is removed from the case with its own button |
| Workspace — indicators | "Indicateurs": a stored list in the case, "Importer une liste" | **yes** — Actions & tracking > Indicators (add a list, remove) |
| Investigation report | HTML, bookmarks-only or bounded, title and mission | **yes** — HTML or PDF written by the Host itself (no Qt in the container), bookmarks-only or bounded, title, description and a coverage warning
| Client report | the document handed to the client: scope, findings by level, actions and owners, indicators, machines, destruction, PDF | **yes** — Reports > Client report, built by the desktop's own `core/client_report`; a section with no data says so
| Tracking | create, edit, close, reopen, export CSV | **yes** |
| Preferences | runtime, readers, profiles, text scale, palette, custom colours | **yes** — runtime, readers, profiles, palette and text size; copy as a table with or without headers; date format for the values that read as timestamps. Tabs wrap on their own in a browser
| Sessions and compatibility | open/save a session file, Timeline Explorer DLLs | **declared** — sessions live with the case, no .NET host |
| Language | French and English | **declared** — English only by product decision |
| System integration | Show in Explorer, Open with…, parent folder | **declared** — no file manager behind a browser |
| Window management | detach, dock, presets, splash | **declared** — no window manager in a tab |

## What this changes

- `HOST-PARITY.md` stays as the **command-level** view (102 commands from the menu
  inventory, 85 covered, 17 declared). It is not the whole story, and its "nothing
  left" line is replaced by a pointer to this page.
- This page, at feature level, is the one that decides. Its verdict today: **no
  feature of the desktop is missing from the Host**, one is partial, and six are
  declared with a reason.

### The one partial

`Import — cancel`: an import runs as a job with its progress line and a Stop, but the
stop lands at the collection's own checkpoints, so a single file read in one pass
finishes first.

### The declared ones, and why

| Difference | Why it is declared, not ported |
| --- | --- |
| Timeline Explorer DLL | a .NET plugin of 129 MB, run by the desktop's own host; it is a deployment decision, not a missing screen |
| The AI assistant ("Explain this finding", "Ask") | no model is connected in the Host edition; the detection is local and the button would lie |
| French and English | English only, by product decision since 0.3.2 |
| Show in Explorer, Open with…, parent folder | a browser has no file manager behind it |
| Detach, dock, presets, splash | a browser tab has no window manager |
| Destruction photo attachments | `case_destruction.destroy_case` — the core the Host calls — takes no attachments today; the desktop's own dialog fingerprints them separately. Wiring them means changing the shared core, which is a task of its own, not a display gap |

Two more structural differences are worth naming, because they are visible without
being missing features:

- the grouped grid **drills down** (Root / a group / back) instead of expanding its
  groups inline: the same groups are reachable, one level per page;
- the graph is drawn by the server and read in the window: the nodes are not dragged
  or zoomed like the desktop's canvas.

### What the catch-up added, in the order it was done

1. the case workspace (machines, accounts, indicators), feeding the graph and both reports;
2. the detection rules, edited beside the pack and never in it;
3. the global colour book, in the desktop's own file;
4. the coverage check and its JSON/CSV export;
5. the timeline: undated rows, verified export, windowed rows, the source row;
6. IOC hunting across every analysis, with sub-domains and a declared format;
7. the date filter, group summaries and the multi-column sort dialog;
8. open analyses, reordering, history and recovery;
9. reading a file again, and cancelling an import;
10. the investigation report as HTML and as a PDF the Host writes itself;
11. the client report, from the desktop's own `core/client_report`;
12. the three Hayabusa maps — clock, heat map, chain — with "Grouped by";
13. the visual formats of the rules: data bars, two- and three-colour scales, icon sets;
14. the workbook import, with the sheet chosen by name;
15. the timeline worked by hand: zoom, pan, fit, back, isolate, select a duration;
16. closed analyses kept in the session, machines and actions changed or removed;
17. the import report, file by file, with "set aside" and a hash-checked removal;
18. the layout exported and imported as a file.

One defect was found in the **shared core** on the way: `core/visual_bounds` cached a
rule's resolved bounds without the visual in the key, so a data bar and a three-colour
scale on the same column shared one cache entry. The visual is now part of the key,
and the desktop reads the same module.

## How this page is checked

`scripts/desktop_surface.py` regenerates the inventory:

```
python scripts/desktop_surface.py --src src/fireblade/ui --out /tmp/desktop_surface.json
```

The audit itself is read by a human; the numbers above come from that command, and
the Host column was filled by reading `src/fireblade/web/` and exercising the browser,
not by trusting the previous page.
