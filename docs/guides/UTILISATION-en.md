# Using Fireblade

Fireblade can parse a folder of artefacts, analyse its EVTX with Hayabusa and explore the results with their context. It also opens CSV, delimited TSV and TXT, XLS and XLSX directly, with search, filters, sorting, groups, bookmarks and notes.

## Getting started

Download `Fireblade.exe`, then double-click it. Python, Excel and a folder of libraries next to the program are not required. The guide and the licences are available in the **Help** menu, even without an open analysis.

For the detailed reference that covers all the commands, rules, profiles, themes and TLE functions, open **Help → Complete tutorial — all features** or read the [complete tutorial](TUTORIEL-COMPLET-en.md).

The program prepares its libraries in the Windows temporary folder at startup. This step may take a few seconds. This folder is normally deleted on exit. Analyses are saved separately to preserve the work.

## Importing a collection of artefacts and running Hayabusa

The **Collection** bar and **Analysis → Parse a folder…** let you choose a folder containing raw artefacts. Subfolders are traversed; links are not followed. The working folder is created under `%LOCALAPPDATA%\\Fireblade\\Collectes`, separately from the evidence.

Before running the engines, choose the organization:

- **One tab per artefact type**: the files of the same type are brought together, for example EVTX, Amcache or Jump Lists. This is the default choice.
- **Everything in a single tab, grouped by artefact**: a “Full collection” analysis is created with the grouping already applied on the artefact column.

Columns of different formats are brought together without converting their values; the fields absent from a format remain empty. Ambiguous identically named columns are distinguished by a suffix, and the added provenance fields avoid collisions with the original fields. Each row keeps its **Artefact**, its **Source file** and its **Parser**. The databases and individual outputs remain on disk for verification; only the organization of the session changes. The choice and the grouping are preserved on resume. Older collections keep their original layout. Hayabusa alerts remain in their dedicated tab.

The Windows pack built from the pinned sources includes EvtxECmd, AmcacheParser, AppCompatCacheParser, PECmd, MFTECmd, RECmd, LECmd, JLECmd, SrumECmd, WxTCmd, RBCmd, RecentFileCacheParser and SQLECmd. RECmd uses the Kroll batch and the 70 registry plugins built from RegistryPlugins; EvtxECmd and SQLECmd have their maps. CSV and TSV files already produced can also be imported. This is not support for every existing forensic format nor for all third-party parsers.

The report is a sortable table with a search and a filter **All files**, **Succeeded**, **Warnings / to check**, **Errors / interrupted** or **Unrecognized / skipped**. Select a file to read its warnings, its SHA-256 and its outputs. **Full report** retrieves the general information; **Open the results** opens the working folder. The **1. Import and parse** part is distinct from **2. Detect in the Windows EVTX**; Hayabusa remains disabled if no usable EVTX collection is ready.

The **Imports** tab keeps the report: files processed, unrecognized, links skipped, errors and absence of output. The engine CSVs remain in `results`, the databases in `analyses`, with a `collection.json` manifest, the logs and a `collection.fireblade-session` session. The parsed outputs add the path of the artefact and the name of the parser. The existing ceiling of 1000 analyses per session applies; the outputs that cannot be loaded remain on disk and are reported as an error. The hashes of the recognized sources are verified before and after processing. The engines that are absent or in error are never counted as succeeded. The registry transaction logs LOG1/LOG2 are kept as companion files, used by the hive readers and not parsed as independent hives. The compiled EZ engines disable their Exceptionless telemetry.

**Analyse the collection with Hayabusa** processes the inventoried EVTX together, after verification and temporary copy. Choose the minimum level in the Collection tab; it is **Low** by default. Fireblade uses Hayabusa **4.3.1**, its `dfir-timeline` command and its verbose profile, without an interactive wizard or rule download during the analysis. The noisy, obsolete and unsupported rules are not enabled automatically.

The **Hayabusa Alerts.csv** tab becomes a Fireblade analysis: filter Level, RuleTitle, Computer or EventID, examine RecordID, RuleID and the details, then add your notes. `Fireblade_EVTX_Source` gives the path of the original EVTX, or a JSON list for an aggregated detection over several files; EvtxFile corresponds to the analysed temporary copy. The temporary working files are removed after execution. An analysis without any alert is distinct from an analysis in error; the report indicates any warnings.

**Resume a collection…** reopens its working folder. Keep the source artefacts to run Hayabusa again; an EVTX modified since the inventory is refused. **Analysis → Abort the query** also interrupts the external engine; the results already completed and their report remain preserved. Each external processing has a maximum time limit of one hour. The DuckDB limits do not cap the memory of the parsers and of Hayabusa; also plan for the disk space needed for the CSVs, the databases and the temporary copies of the EVTX.

The Windows program embeds the engines, the .NET runtime, Hayabusa and the rules: the user keeps a single EXE for the program. The results remain separate in the working folder. This distribution is larger and its extraction at startup requires more temporary disk space. The distributed Hayabusa sources can be exported from **Help → Export the Hayabusa sources…**; the licences remain in **Help → Licences**.

A matching rule gives a lead, not automatic proof of compromise. Hayabusa covers the EVTX here; the other artefacts are parsed and explorable, without claiming to apply the EVTX rules to them.

## Understanding an alert with its EVTX context

The **Hayabusa Alerts** tab remains the short list of detections. Select an alert, choose the duration before/after (5 minutes by default), then click **View the context of this alert**. The command is also available on right-click and in **Analysis → View the EVTX context of the alert**.

A reusable side panel **EVTX context of the alert** presents a timeline of the imported events. The alert list remains open. **Keep this context as a tab** saves an analysis that can be consulted in the session; the previews that are not kept are not added to the tabs and their temporary files are removed on replacement or on close. The context contains: date, EventID, machine, channel, description and detailed data. The **Relation to the alert** column, pinned in a context kept as a tab, distinguishes:

- **Alert event**: match with the EVTX file and the EventRecordID, also checked against the machine and the EventID when they are available. The row appears in bold.
- **Candidate reference (aggregation)**: several references do not allow each identifier to be attributed to an event with certainty.
- **Temporal proximity**: neighbouring event on the same machine, possibly in another EVTX log. This proximity is not enough to declare it suspicious or to establish a causal relation.

The context is limited to 1000 events, keeping the references and the closest neighbours; the summary indicates the limits or the unavailable sources. The window is adjustable from 1 minute to 24 hours before and after. A reference that cannot be found remains explicitly unresolved; a nearby event does not silently replace it. Without a usable machine or date, the neighbourhood is not invented.

Select a row of the context then **Open the source EVTX event** to find exactly that row in the original EvtxECmd database. **Clear the filters** retrieves the other events of that file; **Back to the alerts** returns to the list of detections and keeps its filters and annotations. The Details panel and the cell window allow the full payloads to be read, even if the grid abbreviates them.

The preview is read-only. The contexts kept as tabs are ordinary Fireblade analyses: notes, bookmarks, filters and exports remain available. Their link with the alert is recorded in the working folder; opening them automatically retrieves the associated collection. They remain consultable with the imported databases even if the original EVTX are no longer accessible. These are snapshots already parsed, without reparsing or re-evaluating the Hayabusa rule; the sources remain necessary to run the detection itself.


## Opening data

1. Click **Analysis → Import a data file** or press **Ctrl+O**.
2. Choose a CSV, TSV, TXT, XLS or XLSX.
3. Confirm the name and the location of the `.timeline` analysis file. For XLS/XLSX, select the sheet; the first row must contain the column names.
4. Wait for the end of the import. The source is read without rewriting.

PowerShell CSV exports with a first `#TYPE` metadata row are accepted. Such a value in the middle of the data remains a normal record.

For a CSV, the options allow the separator and the encoding to be specified: BOM detection, UTF-8, UTF-16, UTF-32, Windows-1252 or Latin-1. If the detection is ambiguous, select the separator explicitly. The empty cells are normalized to NULL.

The values are kept as text to preserve the leading zeros and the large identifiers. The XLSX formulas are imported as text, without calculation. The styles and zeros coming only from an Excel numerical format are not imported. XLS is also supported: the formulas are read as their stored results; the macros are not executed.

## Searching and filtering

Enter the text in **Search**, then press Enter. This search applies to the columns of the active analysis.

Under each data header, the **Contains…** field filters that column directly. The filter applies after a short typing pause or immediately with Enter. Several fields combine with **AND**; clearing a field removes its “contains” filter. The fields follow the moved or pinned columns. **Filters → Clear the filters** also empties these fields.

Right-clicking a cell allows filtering on its value or excluding it. Right-clicking a header opens the column filters. The simple filters combine with AND; a double-click in their list removes a filter.

**Filters → AND / OR / NOT editor** allows nested groups to be built. The conditions are presented in nested cards: choose **All the conditions** (AND) or **At least one** (OR). Each card offers **+ Condition** and **+ Subgroup**, without prior selection in a tree. Ticking **Exclude (NOT)** inverts a condition; **Invert the group (NOT)** inverts the whole block. The AND, OR and NOT labels and the nested frames allow the blocks to be located. The **Filter reading** sentence updates while typing. **Collapse / Expand** reduces a group without removing its conditions; the summary remains accessible. The operators include textual search, exact equality, RE2 regex, empty cells, numerical comparisons and ISO date bounds. The data whose numerical or temporal conversion is impossible do not match that comparison.

**Clear the filters**, near the search, removes the searches and criteria without changing the groups, the sorting, the colours or the pinning. **View → Reset the view** restores a default view, with the global rules enabled.

## Sorting

The two arrows to the right of each header sort directly in ascending (**▲**) or descending (**▼**) order. The active arrow remains selected. Clicking the header name also toggles the direction; the context menu remains available. Choose the type **Text**, **Number** or **ISO date** according to the data.

**View → Sort on several columns** allows several keys to be ordered. The first has priority, then the following ones break ties between identical values. The NULL cells come last. The numerical conversions avoid the floating-point rounding of large identifiers.

## Grouping

Drag a header into the grouping bar, or choose **Group by this column** in its menu. Several columns create nested levels. The bar displays these levels as numbered buttons linked by chevrons. Clicking the **×** of a button removes that level while keeping the others.

**Group…** allows the columns and their order to be selected. Expanding a group loads a page of its children; collapsing it releases the loaded descendants. The group counts apply to the filtered results, not only to the visible rows.

The **Next** and **Previous** buttons browse the pages of the selected level. **Root** returns to the main level. Pagination avoids loading the whole analysis into the grid.

## Tabs and sessions

The **Collections and analyses** navigation panel groups the results by collection and artefact/family; its search filters the names without opening the inactive databases. Click an analysis to activate it. The **×** button hides the navigation; **View → Analyses navigation** finds it again. The tabs remain available. The **Row details** button, near Group, collapses or shows the details panel.

Each analysis opens in a tab. **Ctrl+Tab** and **Ctrl+Shift+Tab** switch tabs; **Ctrl+W** closes the active tab. Wait for or interrupt an operation before changing analysis.

Only the database of the active tab remains open. Returning to a tab restores its view and its columns, then reloads the first pages. The selection, the scrolling and the expanded groups are not preserved.

**File → Save the session** keeps the references to the analyses, their order, the views and the column layout in a `.fireblade-session` file. This file does not contain the data: keep the referenced `.timeline` databases. A session with a missing or changed analysis is reported.

The global rules belong to the user profile: export them separately if the session is to be shared with the same presentation.

**File → Timeline Explorer compatibility → Export a TLE session (sources and bookmarks)…** creates a `.tle_sess` referencing the original source files of all the tabs and their bookmarks, even those hidden by a filter. The notes, views and layouts remain specific to Fireblade. Keep the sources at the indicated paths and install the necessary readers in TLE. An integrity check reads the sources before saving; it can be interrupted and does not rewrite the data. The cases that would change the tags are refused: modified source, same source opened in several analyses, ambiguous reader number or Excel sheet other than the first. Failure or cancellation keeps a session already present at the destination. See [the contract and the limits](../development/COMPATIBILITE.md#export-de-sessions-timeline-explorer).


## Bookmarks and notes

A click in the first column highlights the whole row and adds it to the bookmarks. The marker is kept in the database and found again after reopening. A new click removes the bookmark; if a note exists, Fireblade asks for confirmation before deleting it. A double-click on a data cell opens the bookmark and its note. In this individual dialogue, an empty note removes the bookmark.

For several rows, use Ctrl/click or Shift/click, then the **Edit** menu:

- **Mark the selection** adds a bookmark without erasing an existing note; an empty note remains possible.
- **Add a note** appends the text after the existing note, with a line break.
- **Replace the notes** explicitly replaces their content.
- **Remove the bookmarks** deletes the bookmarks and their notes on the selected rows.

The group headers are ignored: selecting a group alone does not automatically mark its descendants. The **Bookmarks** checkbox limits the view to the marked rows.

The notes are kept in the analysis. The grid loads only the annotations of the loaded pages.

## Colours and details

The editor follows three steps: **1. When?** for the condition cards, **2. Apply to** for the activation, the target and the stop after the rule, then **3. Appearance** for the colours or graphics. In Appearance, **Advanced settings: statistics and font** expands the additional options. The preview uses a sample value; it checks neither the condition nor the statistical distribution of the source. The bookmark highlighting keeps a uniform background over the whole row, even when a rule colours a cell; the rules are not removed.

**Analysis → Colouring rules** defines the rules local to the view: conditions, background and text colours, bold, row or cell. The first matching rule has priority.

**Analysis → Global rules** manages the reusable rules, their JSON import/export and their reloading. They follow the column names, even if their order changes. A rule with a missing column is ignored and reported in the status bar. The local rules have priority. The **Apply to this view** option allows the global rules to be disabled for that view only.

The **Details** panel displays the full values and the note of the row. **Show the cell / JSON** opens a cell as plain text or as indented JSON, without modifying the source. The JSON formatting is limited to 2 MB; plain text remains available.

**View → Apply the detected profile** offers initial presets for MFTECmd, EvtxECmd, PECmd, Hayabusa and Plaso L2T. They organize the columns and the sorting; they are not parsers of raw artefacts.

## Saving and exporting

The bookmarks and notes are saved in `.timeline`. **Ctrl+S** saves a named view in that analysis; **Ctrl+L** reloads it.

**File → Export** produces a CSV or XLSX of the visible columns in their order, for all the filtered results, even if the grid shows only one page. For a grouped view, choose the rows or the counts per group.

**Export the bookmarks and notes** exports the marked rows of the filtered view and adds three columns: source record number, presence of the bookmark and note. The number corresponds to the order of the imported records, excluding the header; a multiline CSV field may occupy several physical lines.

XLSX writes the values as text, including those that start with `=`. The results exceeding the capacity of a sheet are spread over several sheets. A cell of more than 32767 characters causes an explicit error: use CSV to keep its full value.

A failed or cancelled export keeps the old destination file. The source and the open analyses cannot be used as an export destination.

## Interrupting an operation

Use **Analysis → Abort the query**. A cancelled import or an error reopens the previous analysis and its view. A final validation already committed may complete despite a late request. An empty database may remain after a cancelled import.

Cancelling a collective annotation before validation cancels the whole selection.

## Where is the work located?

By default, Fireblade uses the Windows profile:

- `%LOCALAPPDATA%\\Fireblade\\Analyses`: proposed destination for the new analyses.
- `%LOCALAPPDATA%\\Fireblade\\regles-globales.json`: library of the global rules.
- `%LOCALAPPDATA%\\Fireblade\\fireblade.toml`: optional user configuration.
- `%LOCALAPPDATA%\\Fireblade\\Journaux\\demarrage.log`: startup diagnostic.

The analysis, session and export locations can be chosen. The sources can be on a read-only medium. Back up the useful analyses and sessions: deleting or replacing the executable does not delete their content.

## Shortcuts

| Action | Shortcut |
|---|---|
| Open data | Ctrl+O |
| Open an analysis | Ctrl+Shift+O |
| Export | Ctrl+Shift+E |
| Save / load a view | Ctrl+S / Ctrl+L |
| Save the session | Ctrl+Shift+S |
| Filter on the value of the active cell | Ctrl+Shift+F |
| Filter editor | Ctrl+Alt+F |
| Clear the filters | Ctrl+E |
| Expand / collapse the groups | Ctrl+M / Ctrl+K |
| Mark / remove the selection | Ctrl+Alt+B / Ctrl+Shift+M |
| Next / previous tab | Ctrl+Tab / Ctrl+Shift+Tab |
| Close the tab | Ctrl+W |
| Copy the selected rows | Ctrl+C |
| User guide | F1 |

## In case of a problem

If an import is refused, check the separator, the encoding, the header or the selected sheet. An already existing file is not overwritten when an analysis is created.

If the program does not start, consult the startup log. Also check that the user profile and the Windows temporary folder are writable. An invalid rules file is left intact; correct and reload, or explicitly import a valid library.

Fireblade remains a prototype. The automated tests do not replace the trials on real exports of several GB and on investigation workstations.

## Cross-file and cross-tab search

**Filters → Search in all the analyses** or **Ctrl+F** searches in the databases of the open tabs. The counts concern all their records, not the loaded pages. An option keeps the filters and bookmarks of each view. A double-click on a result opens the filtered analysis. An error per file is displayed, without silent omission.

The search scans one analysis at a time and can be interrupted. **View → Open analyses** filters the names or paths. **Ctrl+Shift+T** reopens the last closed tab with its view and its notes. The preferences allow tabs on several rows. A close keeps at most 20 snapshots.

The Open dialogue accepts several files. The files dropped during an operation wait in a sequential queue. Each import keeps its destination confirmation; cancelling a confirmation moves on to the next file. **File → Empty the open queue** removes the pending files without interrupting the current operation.

## Summaries and grouping periods

**View → Summaries and group sorting** adds calculations: non-empty, distinct values, sum, average, minimum and maximum. The chosen type applies to the calculation; the numerical or date values that are invalid are ignored by their conversion. The counts concern all the filtered records. Sort by count, value or summary, choosing the direction; the export of the groups includes the summaries.

A header menu offers the grouping of the dates by year, month, day or hour and a calendar filter. The filter of a month stops at the beginning of the following month, excluded. The invalid dates appear under NULL in the temporal groups.

**Ctrl+K** collapses the groups and releases their descendants. **Expand all the groups (paginated view)** builds an index of the whole hierarchy on disk. All the groups and records can be browsed with **Next/Previous**, without materializing millions of rows in Qt. The first expansion may take time; **Abort the query** cancels it. Collapsing restores the interactive tree.

## Pinned columns, copy and export

A header menu allows a column to be pinned to the left or to the right, moved to the other side or unpinned. The two panes share the same model and the same selection; they do not load another copy of the data. The copies and exports order the pinned columns on the left, the visible central columns, then the pinned columns on the right. Hiding a pinned column also removes it from its pane. **Ctrl+R** resets the widths.

The checkbox of the Row/group column marks a row without asking for a note; the notes remain accessible by double-click and through the Edit menu. A source column recognized as boolean can be displayed as checkboxes without becoming editable. The header menu also allows this display to be toggled.

## Preferences and details

**View → Preferences** separates Appearance, Grid and copy, Dates and Compatibility. The Appearance page offers a gallery of 24 themes with preview and sets the light/dark mode, the font family and size, the recognized dates (source, ISO, ISO with seven decimals), the position of the details panel, the copying of the headers and the immediate copy on right-click. **Shift+right-click** keeps the context menu when the immediate copy is active. The preferences are saved in `%LOCALAPPDATA%\\Fireblade\\preferences.json`.

The detail and the export keep the source text, even if the grid shows a date or a boolean. The seven-decimal format does not remove the additional decimals present in the source. Right-clicking a field of the Details panel allows its full value to be copied, filtered or excluded. The cell window can format JSON or XML up to 2 MB; the XML DTDs and entities are refused.

A cell menu offers **Open with** (explicitly chosen program) and Explorer for the paths existing on this workstation. It does not automatically follow the paths of the evidence to another system.

## Profiles, supertimelines and TLE compatibility

**View → Profiles and plugins** displays the embedded schemas and installs personal JSON profiles. **Apply the detected profile** offers columns, dates, booleans and presentation. The catalogue is described in [the profiles documentation](../development/PLUGINS.md). Recognizing a header does not guarantee all the processing of the corresponding Timeline Explorer plugin. The compatible DLL readers can be loaded via the .NET helpers; see the Reading plugins and TLE functions section for their limits.

The supertimeline legend describes the first colouring categories of the recognized profiles. Check the values of the event; a colour alone does not constitute a forensic conclusion.

**Analysis → Export/import the layout** shares a `.fireblade-view` view between analyses having exactly the same columns. The import also accepts certain TLE XML layouts for the order, the widths, the left/right pinning, the groups and the sorts. The incompatible filters and rules cause an explicit message instead of being ignored.

**File → Timeline Explorer compatibility → Import a Timeline Explorer session** reads a `.tle_sess`, verifies its sources and reimports them into new databases, with the tags. The sources must be available; the CSV uses its UTF-8/16/32 BOM (UTF-8 in the absence of a BOM), the workbooks use their first sheet for this migration. The local layouts of the format are found again automatically when each tab is opened. In case of failure or cancellation, the new databases of this migration are deleted and the previous analysis is restored.

**Filters → Text expression** accepts a limited and controlled grammar: `Contains`, `StartsWith`, `EndsWith`, `IsNull`, `IsNullOrEmpty`, `In`, `Between`, comparisons, `And`, `Or`, `Not`. Examples: `Contains([User], 'alice') And [ID] >= 10`; `[Date] >= #2026-01-01# And [Date] < #2026-02-01#`. The expressions also accept nested functions, calculations, `Iif`, `Upper`, `Substring`, `ToInt`, `Round`, `GetYear`, `AddDays`, `DateDiffDay` and the virtual fields `Line`, `Tag`, `Note`. The unsupported DevExpress functions are refused. The AND/OR/NOT editor allows the conditions to be built without knowing this syntax.

**View → Messages** shows the last 500 messages of the session. The startup log remains available separately.

## Derived columns

**Analysis → Calculations and conversions → Convert a date…**: choose the column, optionally a second time column, the source format and the time zone of the dates without offset. The result is a new UTC column with nine decimals; the source remains intact. Formats: ISO, US/European dates, Unix s/ms/us/ns, FILETIME, WebKit, .NET and OLE. The IANA and Windows time zones are accepted. The local times follow the DST conventions of ICU; to remove an ambiguity, provide an explicit offset.

**Add a calculated column…**: enter a name and an expression, for example `Iif([Size] > 1024, 'large', 'small')`. The column is calculated by DuckDB and persisted in the analysis. **Check the derived columns…** counts the NULL values; these may indicate an empty, invalid or out-of-range source. No record is deleted.

Applying a profile may offer these normalized columns, the categories and the MACB indicators. They remain available after reopening and in the exports.

## Timeline Explorer preferences

**File → Timeline Explorer compatibility → Import the Timeline Explorer preferences…** reads `Settings/TLE_settings.xml`: font, size, copying of the headers, right-click copy, tabs on several rows, details at the top/bottom, date format and simple list of pinned columns. The Office, Visual Studio, blue, silver and high contrast families are associated with the corresponding Fireblade themes; this association adapts the colours and does not load the DevExpress skins. The unknown or untranslated structured fields are reported in Messages. The TLE file remains intact. The same settings can be changed in the Fireblade preferences; the default pinning uses one name per row.

The recognized forensic profiles are applied automatically to the new imports, before the display of their columns. Disable **Apply the recognized forensic profile on import** in the preferences to keep a generic grid. Adding a derived column keeps the order, the widths, the hiding and the pinning of the existing columns.

## Graphical and statistical formatting

In **Analysis → Colouring rules**, add a rule and choose the target. The Appearance tab contains background/text, styles, a font specific to the rule and ranking, average, unique values or duplicates. For a statistical rule on the whole row, explicitly choose its value field. “Active background”, “Active text” and “Active font” allow several rules to be combined; disable “Stop after this rule” to let the following ones contribute.

The Chart tab offers bars, two/three-colour gradients and icons. The bounds are chosen independently: fixed, automatic, percentage of the range or exact percentiles. The calculations apply to the whole filtered result, not only the page. The first calculation may take time; the following pages use the cache. The negative bars have a colour and a zero axis; the icons have three to five levels with strict or inclusive thresholds, customisable colours and images.

The invalid values remain without a chart. Hiding values changes neither the data nor their copy or export. The rules are kept in the views and the global libraries. CSV/XLSX export the data without the drawings of the grid. The standard XML rules of the TLE layouts are translated; any adaptation is reported.

## Reading plugins and TLE functions

**File → Timeline Explorer compatibility → Import with a TLE plugin (.NET)…** allows a reader DLL and a source to be chosen. **Analysis → Calculations and conversions → Load .NET functions…** adds its functions to the expressions, for the active analysis. The functions already selected for that analysis are reloaded automatically, under the control of the local registry and of the DLL hash. Use the native CSV import for the usual large volumes. See the [plugins guide](../development/PLUGINS.md) for the contracts and limits.


The statistical and graphical rules also offer a calculation over the whole source, ignoring the active filter. The averages accept strict or inclusive comparisons. The relative dates use `InDateRange([Date], 'Today')` and the periods offered in the rule editor; the days are calculated in UTC, the weeks start on Monday. The XML import takes over the combined relative dates, the value lists and the twelve documented predefined text/background styles of DevExpress. The predefined palettes are adapted; the custom styles can be defined in a local JSON library or associated with the layout; see [the examples and limits](LAYOUTS-TLE.md). A name without a definition remains refused.


**View → Preferences → Customize the colours** sets the background of the windows, the text, the fields, the alternating rows and the selection. “Restore the theme colours” retrieves the palette of the theme chosen in the gallery (or the standard theme if no model is chosen). The icon rules also offer triangles, squares, diamonds, stars, rankings and flags; personal PNGs remain usable.


## Pinning a column to the right

Right-click on the header → **Pin to the right**. The column remains visible on the right during horizontal scrolling. Both sides can be used simultaneously. The same menu allows the column to be moved to the left or unpinned. Hiding a pinned column also removes it from its pane. The views, layouts and sessions keep the side and the width; copy and export place the pinned columns on the right at the end of the table. The TLE layouts `Fixed=Right` are taken over.

### Automatic layout by format

On close or on tab change, Fireblade saves a `.layout.local` in `%LOCALAPPDATA%\\Fireblade\\Layouts\\Local`. The following files with the same format and the same schema take over the columns, the widths, the order, the hiding, the left/right pinning and the view: groups, sorts, filters, search, summaries and colours. The stored filters may therefore limit the visible rows of the new file. The Fireblade sessions keep their own view.

Your TLE XML can be placed in `%LOCALAPPDATA%\\Fireblade\\Layouts\\Default` or `Layouts\\Default` next to the EXE: `<ReaderName>.layout.local` has priority over `<ReaderName>.layout`. The name of the recognized profile is also accepted (`EvtxECmd`, etc.). The stored Fireblade layout has priority over these XML files. Delete it to take over the XML; delete the `.layout.local` files to take over the default `.layout`. An invalid layout is reported in **View → Messages**, without blocking the import or being overwritten on close. The layouts are never saved in the evidence folder.

### Sorts and styles imported from TLE

The XML import takes over the sort by summary of each group level, including several criteria, different directions and tag references. The grid, the expansion and the grouped export keep the same order. In **Summaries and group sorting**, changing the global sort or the summaries replaces these advanced criteria; accepting without change keeps them.

The colours and fonts of the rows, groups, cells and headers are kept, as well as the enabled even/odd alternation, the selection, the focus, the alignments and the gradients. The pinned columns are concerned. The explicit conditional options override the predefined style instead of erasing it entirely. The parameters specific to DevExpress that are not taken over appear in the migration messages.

### .NET functions and complex objects

After an import with a DLL reader and the loading of the functions, an expression such as `MyFunction([Details])` receives the real CLR object, with its methods and its original type. The collections (`[Details.Children]`), the nested members and the returns of other functions are also passed by reference. The JSON displayed in the grid remains a preview, not the object given to the function.

Keep the source and the DLL of the reader: on the first call after opening, Fireblade verifies them then restarts the reader to retrieve its objects. The context remains in memory until the analysis is closed; its volume depends on the third-party reader. Without a call using these objects, the context is not loaded. A cancellation terminates it and the next call can rebuild it.

### Advanced criteria

Examples usable in the filters and colour rules:

```text
EventID=4624 And InRange(PID,1m,10000m)
[Items][[Amount]>[^.Limit]].Count()>0
[Groups].Sum([Children][[Amount]>[^.^.Limit]].Sum([Amount]))>100m
[Items][]
IsJanuary([Time]) And IsSameDay([Time],#!2026-01-02!#)
CharIndex('error',[Message],10)>=0
[Identifier]={513724e5-17b7-4ec6-abc4-0eae12c72c1f}
```

`^` goes up one collection context; it can be repeated for the nested collections. A restriction `[Items][condition]` is true as soon as one element matches. `[Items][]` tests whether the collection is non-empty. The simple names can be written without brackets; `@Or` allows a column bearing a reserved word to be targeted. The names containing spaces remain in brackets.

The calendar functions follow the UTC convention and the weeks start on Monday. `GetTimeOfDay` returns ticks of 100 ns; `AddTimeSpan` accepts ticks or a duration `[-][days.]hh:mm:ss[.fffffff]`. The three-argument form of `InDateRange` includes the end day; `InRange` excludes its upper bound. The date-only and time-only types use `#!…!#`.


## Group footers and row height

In **View → Summaries and group sorting**, the **Per group** tab chooses the calculations, their footer column and the display mode of the footers: hidden, expanded groups or always visible. A summary placed in the header remains at that location. The **Global footer** tab chooses independent calculations applying to all the filtered results. The group footers keep their own appearances and are not data rows to be marked or exported.

**View → Row height** allows the rows to be adapted to the displayed text, the text to be wrapped and the heights of rows, groups and headers to be set. The automatic height may exceed three lines; the pinned columns keep the same alignment and the scrolling allows a row taller than the window to be browsed. Only the cells already loaded are measured. The grid displays at most 600 characters per cell; use the details for the full content.


## Theme gallery

**View → Preferences → Theme gallery** offers Office light/dark grey/black, Classic blue, Silver, Graphite, Studio light/dark, Sand, Forest and High contrast light/dark. The preview shows a small grid, a selection and commands. It remains local to the dialogue: **Cancel** keeps the application theme. **OK** applies and saves the choice for the next startup.

Choosing a gallery theme restores its palette; **Customize the colours** then allows it to be modified. Manually changing to a mode different from that of the theme reverts to “Standard / custom”. The preferences remain scrollable when the screen or the zoom limits the space, with OK/Cancel always accessible.

These palettes and renderings are Qt creations of Fireblade. The proprietary resources, drawings and metrics of the DevExpress skins are not integrated and the visual identity with Timeline Explorer is not claimed.

## CatScale Linux collections

In a case, use **Import a collection folder…** to choose an extracted CatScale folder or one containing its `catscale_*.tar.gz` / `FSecure_*.tar.gz` archives. Choose the tabs by family or the grouped grid. The parser is integrated without a Linux dependency.

The Reading column distinguishes the structured data from the preserved plain text; Source and Line keep the provenance. Check the warnings, the unsupported binaries and the limits before concluding that the collection is complete. Hayabusa remains reserved for the Windows EVTX. See [the complete walkthrough and its limits](TUTORIEL-COMPLET-en.md#importing-a-linux-catscale-collection).

## Shellbags and WebCache

Import the folder containing the `UsrClass.dat` / `NTUSER.DAT` hives and the ESE database `WebCacheV01.dat`. Keep the registry `.LOG1` / `.LOG2` next to their hive. The choice by artefact gives Shellbags and WebCache tabs, with the filters, notes and backups of the case.

The registry references, the Shellbags bytes, the WebCache tables/containers and the raw dates are kept. The warnings indicate the dirty hives/databases or the unreadable elements. The Shellbags key dates are not certain visit times; the WebCache reader does not replay the ESE logs and does not recover the deleted data. See [the fields and limits of the tutorial](TUTORIEL-COMPLET-en.md#shellbags-and-webcache-windows).

## Timeline and advanced backups

Version 0.5 adds a **Timeline & correlations** tab, the recovery history of
cases, the portable `.fireblade-case` archives and the HTML/PDF
reports. Consult the [detailed guide](CHRONOLOGIE-ET-SAUVEGARDES-en.md) to choose
the dates, cross the artefacts, recover a session and transport an investigation.
