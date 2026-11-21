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

**The port is not complete.** Twenty-one domains are covered, but this audit found
**1 features the Host does not have** and **5 it has partially** (five closed since the
audit was written: machines and accounts, tracked indicators, Hayabusa rules,
global colour rules, import diagnostics). None of them was
visible in the label inventory, which is why `HOST-PARITY.md` said "nothing left" —
and that claim is withdrawn here.

## The domains

Legend: **yes** = the Host does it, **partial** = it does part of it, **no** = missing.

| Domain | Desktop screens and commands | Host |
| --- | --- | --- |
| Window, menus, tabs | 9 tabs, 6 menus, status bar, toolbar | **yes** |
| Command palette | "Commandes" (a keyboard launcher over every command) | **yes** — Commands… (Ctrl+K): every command the window offers, filtered and run |
| Messages | "Messages" (the application's own log) | **yes** — View > Messages: every line the status bar showed, newest first |
| Open analyses | "Analyses ouvertes…" (list, close, reorder) | **yes** — Analysis > Open analyses: open, close, reorder the tabs and keep the order |
| Cases | new, edit, destroy (DoD + certificate), archive, restore, portable `.fireblade` | **yes** |
| Case history | "Historique et récupération" (the History folder) | **yes** — Case > History and recovery: the recorded states, restored after keeping the present one |
| Import — file, folder | three layouts, preview, CSV options, history file by file | **yes** |
| Import — disk | "Analyser un disque…" (an image, not a folder) | **no** |
| Import — cancel | "Arrêter" during a collection | **partial** — an import runs as a job with its progress line and a Stop, but the stop lands at the collection's own checkpoints: a source read in one pass finishes first |
| Import — retry with a reader | "Relancer avec un lecteur" on an unread file | **yes** — Imports > Read a file again: the unread files, the reader to try, and the decision written in the collection report |
| Import — diagnostics | "Vérification des imports et diagnostics", "Familles attendues" | **yes** — Imports > Import verification (the core coverage audit, four expected-family profiles, JSON and CSV report) |
| Grid — sorting | one column, multi-column, **a priority dialog** | **yes** — Sort priority (add, reorder, remove, direction), on top of shift-click |
| Grid — filters | per column with operators, advanced ET/OU/NON | **yes** |
| Grid — relative dates | "Filtrer une date…", "Ajouter une condition de date relative" | **yes** — Filter a date: the core's 25 named windows, or one day / month / year, added to the advanced filter |
| Grid — grouping | by column, date intervals, drill-down | **yes** |
| Grid — group summaries | "Résumés et tri des groupes" | **yes** — up to 16 aggregates beside each group, and the groups ordered by count, value or a summary |
| Grid — bookmarks, notes | row marks, row notes, cell notes, on a selection | **yes** |
| Grid — colour rules | local rules, from a cell, the value chart and its statistics | **partial** — colours, text colour, bold, row/cell target and the value chart; the statistics (top, duplicates, above average) are missing |
| Grid — global rules | "Règles globales" shared by every analysis | **yes** — Colour rules > Every analysis; the book is the desktop's own file (import and export), a rule the grid cannot evaluate is skipped, never approximated |
| Grid — columns | hide, pin left **and right**, resize, layout in the analysis | **yes** |
| Grid — derived columns | timestamp conversion, expressions, categories, MACB | **yes** |
| Grid — views and profiles | named views, "Appliquer le profil détecté" | **partial** — views yes, applying a profile by hand no |
| Grid — exports | CSV, copy value / rows / cell, whole cell | **yes** |
| Grid — pivot and EVTX | "Qu'est-ce qui a lancé", source event, EVTX context | **yes** |
| Timeline | build, histogram, legend, correlate, page, three date readings | **yes** |
| Timeline — extras | export, "Inclure sans date", "Appliquer les filtres des analyses", "Ouvrir la ligne source" | **partial** — verified CSV export with its receipt, and rows without a date on request; the analyses' filters and the source row are missing |
| IOC hunting | paste, scan, results, saved hunts | **yes** |
| IOC — extras | import TXT/CSV/TSV, all analyses at once, respect the filters, sub-domains | **yes** — IOC hunting: a file or a paste, every analysis, each view's filters, and sub-domains on or off |
| Hayabusa | run by level, findings, tactics, dedup, mark, open, export sources | **yes** |
| Hayabusa — rules | "Règles de détection…" (enable, disable, override) | **yes** — Hayabusa > Detection rules (filter, edit, enable/disable, reset) |
| Hayabusa — assistant | "Explain this finding", "Ask", local model | **declared** — no model is connected |
| Attack graph | build, layout, ATT&CK layer, PNG, free node with tags | **yes** |
| Workspace — machines and accounts | "Machine ou compte" (declared hosts, accounts) | **yes** — Actions & tracking > Machines & accounts |
| Workspace — indicators | "Indicateurs": a stored list in the case, "Importer une liste" | **yes** — Actions & tracking > Indicators (add a list, remove) |
| Client report | HTML, bookmarks-only or bounded, title and mission | **yes** — HTML or PDF written by the Host itself (no Qt in the container), bookmarks-only or bounded, title, description and a coverage warning
| Tracking | create, edit, close, reopen, export CSV | **yes** |
| Preferences | runtime, readers, profiles, text scale, palette, custom colours | **partial** — no copy behaviour, date format, tab wrapping |
| Sessions and compatibility | open/save a session file, Timeline Explorer DLLs | **declared** — sessions live with the case, no .NET host |
| Language | French and English | **declared** — English only by product decision |
| System integration | Show in Explorer, Open with…, parent folder | **declared** — no file manager behind a browser |
| Window management | detach, dock, presets, splash | **declared** — no window manager in a tab |

## What this changes

- `HOST-PARITY.md` stays as the **command-level** view (102 commands from the menu
  inventory, 85 covered, 17 declared). It is not the whole story, and its "nothing
  left" line is replaced by a pointer to this page.
- The work list is the **no** and **partial** lines above: 19 missing features and 9
  partial ones, ordered here by how much an analyst would miss them:
  1. machines and accounts, indicators (the case workspace: the graph and the report
     already read them, only the way to fill them is missing);
  2. Hayabusa detection rules;
  3. global colour rules;
  4. import diagnostics and expected families, retry with a reader;
  5. timeline export, include-undated, source row;
  6. IOC across every analysis, filters respected, sub-domains, file import;
  7. grid: multi-sort dialog, group summaries, relative dates, value chart;
  8. command palette, messages, open-analyses dialog, case history;
  9. disk images;
  10. preferences: copy behaviour, date format, tab wrapping;
  11. PDF report.

## How this page is checked

`scripts/desktop_surface.py` regenerates the inventory:

```
python scripts/desktop_surface.py --src src/fireblade/ui --out /tmp/desktop_surface.json
```

The audit itself is read by a human; the numbers above come from that command, and
the Host column was filled by reading `src/fireblade/web/` and exercising the browser,
not by trusting the previous page.
