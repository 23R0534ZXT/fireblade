# Kagarasu Host 0.15.0 browser qualification

**474 of 474 collected tests passed** on Linux with Python 3.12.14 and Playwright Chromium 159.0.8154.6. The suite comprised 427 Host tests and 47 comparisons with the offscreen Qt grid. Every test has a recorded result, with zero skips. The release sweep ran by module during integration. The first freeze replayed 39 regression cases, including saved-session reopening after an earlier failure. CI subsequently exposed two timing-sensitive workflows. After the keyboard focus fix and the observation-dialog test correction, both affected modules passed on the final client (six cases). [Test-by-test results](browser-tests.tsv)

**516 of 516 distinct static control keys received a browser input event** across the Host tests, Docker tests, menu tour and targeted replays. Keys represent commands, fields, tabs and menu entries identified on the live Host page. Repeated instances can share a key. Workflow tests check outcomes such as saved row values, restored filters, collected file hashes and downloaded document contents. [Control-by-control evidence](gui-controls.tsv)

The public GUI archive contains a browsable gallery of 135 screenshots, both inventories, client asset fingerprints and SHA-256 checksums. Extract it and open `index.html`. The separate Docker archive includes native-reader results and isolated-case evidence. [GUI evidence ZIP](https://github.com/23R0534ZXT/kogarasu/releases/download/v0.15.0/Kagarasu-Host-0.15.0-GUI-evidence.zip) · [Docker QA ZIP](https://github.com/23R0534ZXT/kogarasu/releases/download/v0.15.0/Kagarasu-Host-0.15.0-Docker-QA.zip)

## Analyst workflows

| Area | What was verified |
| --- | --- |
| Case library and imports | Create, open, rename, archive and erase temporary cases. Import the sample CSV, verify 80 rows, filter to 20 interactive logons and read `WS-LAB-01` from a record. Upload two folders with matching names and verify both copies retain their paths and different SHA-256 hashes. |
| Evidence review | Inspect original values and provenance. Filter, sort, group, page, configure columns and apply color rules. Preserve selected values across checklist pages. A filtered two-key numeric sort returned 100, 10, 10, 2 with the expected tie order after session import and case reopening. |
| Investigation | Explore a two-partition disk, choose an individual file and verify its extracted bytes. Read-only E01 mounts yielded a 93-byte FAT log and a 96-byte NTFS journal stream, each matching its fixture hash. Follow timeline, IOC, finding and graph results to their evidence and review tagged, time-bounded relationships. |
| Tracking and reports | Record an observation, edit notes and review a proposed rewrite before accepting it. Download two HTML reports, two PDFs, the editable investigation and intake DOCX files, and the tracking workbook. Chromium, Poppler and LibreOffice opened the outputs. Both PDFs had selectable text, correct titles and one page each. The six-sheet workbook printed one full-width A4 landscape page per sheet. |
| Container operation | Start two isolated drivers on separate networks. Open a case through its proxy, import two rows, reload the workspace, erase the temporary case by name and retrieve the external HTML and DOCX certificates. The release image passed all 16 image tests and all 47 reference checks across eight scenarios, including 523 Shellbags rows, 1,612 WebCache rows and 13 EVTX events. |

## Visual review and scope

The final tour captured **101 states at 1500 × 900**, with zero layout findings and zero uncaught JavaScript errors. Additional captures cover light and dark themes, the case library, imports, row details, the timeline and narrow windows. Widths of 390, 680, 800 and 1100 pixels and 175% zoom were checked for toolbar reachability, tab scrolling and dialog sizing. The initial tour logged 105 geometry warnings. The updated checker accounts for popup layers and scroll clipping. Pointer hit-testing confirmed that visible row-note controls open their editors.

The generic CSV tour received five HTTP 400 responses. The rule inventory request required a local Hayabusa tool pack. The row context request required an EVTX event reference. Two tracking requests used a timestamp in place of an IP address. The annotated export requested bookmarks from an unmarked grid. Positive paths for detection rules, event context, IP tracking and annotated exports are covered in the test inventories.

The final application commit was `9cf9c2b0df39c5365ba713ecb104efa3f915e6bb`. The rebuilt case image had local ID `sha256:c0229259b6ba74c61967a577cffa64cc3767cf212ac599d5459f0cf365135fd7`. The driver image had ID `sha256:30135c751cb4bb4fe0f5b334314191db611c78ed52aded5ca168699a366c8b08`. The browser runs used temporary investigations and synthetic or documented public fixtures. Rewrite review used a simulated provider response. Other browser engines, external model endpoints and physical disks were outside this run.

## Reproduce the Host browser run

Use the development environment described in [Contributing](../../../../CONTRIBUTING.md). The Linux browser tests start local HTTP servers and make temporary cases. The parity module also opens the Qt grid offscreen for comparison.

```bash
export QT_QPA_PLATFORM=offscreen
export FIREBLADE_JS_COVERAGE="$PWD/artifacts/qualification/control-events"
export FIREBLADE_SCREENSHOTS="$PWD/artifacts/qualification/screenshots"
python -m pytest -q -ra tests/web/test_browser*.py tests/web/test_parity_grid.py \
  --junitxml=artifacts/qualification/browser.xml
python -m scripts.audit.controls "$FIREBLADE_JS_COVERAGE"
```

For a visual tour of an open synthetic case, run the following command with its local address and case name. The gallery captures tabs, menus and the states reached by menu commands. A separate test covers destructive commands on temporary cases.

```bash
python -m scripts.audit.gallery --url http://127.0.0.1:8080 \
  --case "Workstation review" --out artifacts/qualification/gallery
```
