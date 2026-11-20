# Host parity, command by command

`scripts/parity_inventory.py` lists every label the Qt interface exposes. The raw
list has 157 entries, but a third are not commands: they are parameter values
(`append`, `remove`, `top`, `bottom`, `dark`, `light`), step captions of a
dialog, or HTML-escaped menu labels. The real count is **131 commands**.

This file records, for each group, where the Host edition stands. A command is
"covered" only when it works in the browser and was exercised there.

## Covered (verified in the browser)

| Group | Commands |
| --- | --- |
| Case lifecycle | create, rename, destroy with certificate, archive, restore, portable `.fireblade` export and import |
| Import | file from the browser, drop on the window, server path, three layouts (per file / per artifact family / single grid), import history per file with the reader and the reason |
| Grid | open an analysis, page, sort one column, sort several columns with Shift, filter per column with operators, advanced AND/OR/NOT filter, group by a column, group a date by interval, drill into a group, bookmarks, row notes, cell notes, colour rules, colour rule from a cell, hide/pin/resize columns, boolean display, row height, derived columns, saved views, export CSV, copy a row, show a whole cell |
| Timeline | build, histogram, source legend, correlate an entity, page |
| IOC | paste indicators, scan, results with row, column and rule |
| Detection | Hayabusa run at a chosen level, findings with tactics, per-file dedup |
| Graph | build from findings and declared hosts, ATT&CK Navigator layer |
| Report | HTML report, bookmarks-only or bounded, served back |
| Tracking | actions with owner, priority, status; close and reopen |
| Global | search across every analysis, preferences (runtime and reader inventory) |
| Display | text scale, row height, palette and density from the desktop theme |

## Real work left

- saved IOC hunts (a named indicator list, re-runnable);
- CSV import profiles: the core detects the format, the desktop lets the analyst
  confirm or override it before importing;
- export the attack graph as a PNG;
- nested filter groups (the dialog writes one group; the core accepts deeper
  trees);
- column widths and pinning are remembered per browser, not in the analysis.

## Out of scope in a browser, and why

- *Show in Explorer*, *open the parent folder*: there is no system file manager
  in front of the analyst, and the server's folders are not their machine's.
- *Detach a panel*, *window layouts*, *toolbars*, drag a header into the group
  bar: these are desktop window management. The web editor reaches the same
  result through the Group… and Columns… dialogs.

## Not wired on purpose

The AI assistant: nothing is connected, no endpoint and no key. The detection tab
says so. The decision (local model in the container, or a remote API) is the
user's, and it changes what may leave the server.
