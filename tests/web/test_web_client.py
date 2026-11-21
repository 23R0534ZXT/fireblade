"""The Host client carries the surfaces HOST-PARITY.md claims.

A parity claim is only as good as the thing it points at: these tests read the
client files and fail when a menu entry exists without its handler, or when a
handler exists without its entry. They are the cheap half of the proof; the
browser pass is the other half.
"""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "src" / "fireblade" / "web"
APP = WEB / "static" / "app.js"
INDEX = WEB / "static" / "index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_row_menu_offers_every_cell_action():
    """One entry in the menu, one handler in the switch, for each action."""
    js, html = _read(APP), _read(INDEX)
    actions = ("cell-json", "copy-value", "copy-row", "filter-value", "exclude-value",
               "sort-asc", "sort-desc", "group-by-column", "pin-column", "hide-column",
               "bookmark-row", "unmark-selection", "rule-from-cell", "pivot")
    for action in actions:
        assert f'data-act="{action}"' in html, f"no menu entry for {action}"
        assert f'case "{action}":' in js, f"no handler for {action}"


def test_the_import_dialog_offers_the_csv_options():
    """The desktop offers a separator and an encoding; so does the Host."""
    js, html = _read(APP), _read(INDEX)
    assert 'id="preview-delimiter"' in html
    assert 'id="preview-encoding"' in html
    for name in ("fillCsvOptions", "csvOptions", "refreshPreviews"):
        assert f"function {name}(" in js, name
    # The choice must reach the service on both preview routes and on the import.
    assert 'body.append("delimiter"' in js and 'body.append("encoding"' in js
    # previewFiles, previewServerPath, refreshPreviews and confirmImport all read them.
    assert js.count("csvOptions()") >= 3


def test_the_grid_selects_a_range_and_a_selection():
    js = _read(APP)
    assert "function selectRow(" in js
    assert "event.shiftKey" in js and "event.ctrlKey" in js
    assert "function selectedIds(" in js
    assert "function markSelection(" in js
    # A mark is a note: the import must not invent a bookmark without one.
    assert "postBookmark(" in js


def test_the_grouped_view_draws_its_chart():
    js, html = _read(APP), _read(INDEX)
    assert 'id="group-chart"' in html
    assert "function renderGroupChart(" in js
    # Drawn from the same page of groups as the table, not from a second request.
    assert "state.rows.slice(0, CHART_ROWS)" in js
    assert "renderGroupChart();" in js
    assert 'if (!state.grouped) $("group-chart").hidden = true;' in js
    # `display:flex` beats the [hidden] attribute: the panel must hide itself.
    css = (WEB / "static" / "app.css").read_text(encoding="utf-8")
    assert ".group-chart[hidden]{display:none}" in css


def test_a_column_can_be_frozen_on_either_edge():
    js, html = _read(APP), _read(INDEX)
    assert 'data-act="pin-column"' in html
    assert 'data-act="pin-column-right"' in html
    assert "function pinOffsets(" in js
    assert "state.pinnedRight" in js
    # The offsets accumulate real widths, or two pinned columns overlap.
    assert "offset += widthOf(index);" in js
    assert "applyPinning();" in js


def test_a_hayabusa_finding_opens_and_marks_its_alerts():
    js = _read(APP)
    assert "function showFindingInGrid(" in js
    assert "function markFinding(" in js
    assert 'data-want="show"' in js and 'data-want="mark"' in js
    assert "/bookmark-finding" in js
    assert "/detection/" in js and "/sources" in js
    # The run adds its alert analysis to the case: the client must not leave the tab.
    assert "state.openCase = await api(`/api/cases/${state.openCase.id}`);" in js


def test_the_compatibility_dialog_lists_and_installs_profiles():
    js, html = _read(APP), _read(INDEX)
    assert 'id="compat-modal"' in html
    assert 'data-act="plugin-install"' in html
    assert 'data-act="profile-create"' in html
    for name in ("openCompatibility", "loadCompatibility", "installPluginFile",
                 "createProfileFromAnalysis"):
        assert f"function {name}(" in js, name
    assert '"/api/plugins"' in js
    assert "/profiles`" in js


def test_the_evtx_actions_only_appear_for_an_alert_analysis():
    js, html = _read(APP), _read(INDEX)
    assert 'data-act="alert-context"' in html and 'data-act="alert-source"' in html
    assert "function isAlertAnalysis(" in js
    assert "function showAlertContext(" in js and "function openSourceEvent(" in js
    assert "Fireblade_EVTX_Source" in js
    # A menu entry hidden for every analysis would be a dead control.
    assert "item.hidden = !alerts;" in js
    assert "/rows/${contextRow.dataset.row}/context" in js
    assert "/rows/${contextRow.dataset.row}/source" in js


def test_the_timeline_offers_the_three_date_readings():
    js, html = _read(APP), _read(INDEX)
    assert 'id="timeline-dates"' in html
    assert "function renderTimelineDates(" in js
    assert "function applyTimelineDates(" in js
    for value in ('value="auto"', 'value="none"', 'value="split"'):
        assert value in js, value
    assert 'params.set("dates", dates);' in js
    # The selectors are rebuilt with the timeline, so the choice must survive it.
    assert "timelineState.dates[String(source.id)] || \"auto\"" in js


def test_the_palette_offers_presets_and_custom_colours():
    js, html, css = _read(APP), _read(INDEX), (WEB / "static" / "app.css").read_text(encoding="utf-8")
    assert 'id="palette-theme"' in html
    for value in ('value="light"', 'value="dark"', 'value="custom"'):
        assert value in html, value
    # The six colours of the desktop's own dialog, in its order.
    for key in ("window", "text", "base", "alternate", "highlight", "selection_text"):
        assert f'data-colour="{key}"' in html, key
    assert 'data-theme="dark"' in css and "[data-theme=\"dark\"]" in css
    assert "function applyPalette(" in js and "function loadPalette(" in js
    assert "localStorage.setItem(\"fireblade.palette\"" in js
    assert "loadPalette();" in js


def test_the_graph_takes_a_free_node():
    js, html = _read(APP), _read(INDEX)
    assert 'id="graph-node"' in html and 'id="graph-node-modal"' in html
    assert "function openGraphNode(" in js and "function saveGraphNode(" in js
    assert "/graph/nodes" in js
    assert "await buildGraph();" in js


def test_the_tracking_tab_holds_three_lists():
    js, html = _read(APP), _read(INDEX)
    for sub in ("actions", "indicators", "entities"):
        assert f'data-sub="{sub}"' in html, sub
        assert f'id="sub-{sub}"' in html, sub
    assert "function showWorkspaceSub(" in js
    assert "function renderEntities(" in js and "function renderIndicators(" in js
    assert "/entities" in js and "/iocs" in js
    assert "function addEntity(" in js and "function addIndicators(" in js
    assert "function removeIndicator(" in js


def test_no_function_is_declared_twice():
    """A classic script lets the last definition win, silently: one handler dies."""
    js = _read(APP)
    names = re.findall(r'^(?:async )?function ([A-Za-z_][\w]*)\(', js, flags=re.M)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"functions declared twice: {duplicates}"


def test_no_top_level_name_is_declared_twice():
    """A const or a function declared twice is a silent override, not an error."""
    js = _read(APP)
    names = re.findall(r'^(?:async )?function ([A-Za-z_][\w]*)\(', js, flags=re.M)
    names += re.findall(r'^(?:const|let|var) ([A-Za-z_][\w]*)\s*=', js, flags=re.M)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"declared twice at the top level: {duplicates}"


def test_the_window_keeps_its_messages_and_its_commands():
    js, html = _read(APP), _read(INDEX)
    for name in ("palette-modal", "messages-modal", "analyses-modal", "history-modal"):
        assert f'id="{name}"' in html, name
    for name in ("openPalette", "openMessages", "openAnalysesDialog", "openCaseHistory",
                 "restoreHistory", "saveAnalysesOrder", "paletteEntries"):
        assert f"function {name}(" in js, name
    assert "rememberMessage(" in js and "messageLog" in js
    assert "/history" in js and "analyses/reorder" in js


def test_no_element_id_appears_twice():
    """A duplicated id is a dead control: one of the two is never updated."""
    html = _read(INDEX)
    ids = re.findall(r'id="([^"]+)"', html)
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    assert not duplicates, f"duplicate ids in the window: {duplicates}"


def test_the_detection_rules_dialog_edits_a_rule():
    js, html = _read(APP), _read(INDEX)
    assert 'id="detrules-open"' in html and 'id="detrules-modal"' in html
    for name in ("openDetectionRules", "loadDetectionRules", "selectDetectionRule",
                 "saveDetectionRule", "resetDetectionRule", "toggleDetectionRule"):
        assert f"function {name}(" in js, name
    assert "apiPut(" in js and "/rules/" in js
    # An edit is kept beside the tool pack, and a reset gives the pack's rule back.
    assert "reset to the pack" in js.lower() or "Reset to the pack" in html


def test_the_colour_rules_carry_two_scopes():
    js, html = _read(APP), _read(INDEX)
    assert 'data-scope="analysis"' in html and 'data-scope="global"' in html
    for name in ("showRulesScope", "loadGlobalRules", "persistGlobalRules", "globalRuleList"):
        assert f"function {name}(" in js, name
    assert "/api/global-rules" in js
    # A rule the grid cannot evaluate is skipped, never approximated.
    assert "rule.simple === false" in js
    assert 'id="rule-global-export"' in html and 'id="rule-global-import"' in html


def test_the_import_verification_shows_what_was_not_attested():
    js, html = _read(APP), _read(INDEX)
    assert 'id="coverage-open"' in html and 'id="coverage-modal"' in html
    for name in ("openCoverage", "renderCoverage", "runCoverage", "showCoverage"):
        assert f"function {name}(" in js, name
    assert "/coverage" in js and "coverage/export" in js
    assert 'id="coverage-level"' in html and 'id="coverage-search"' in html
    # the page must never present an absence as a proof
    assert "never a proof" in html


def test_the_timeline_exports_and_shows_undated_rows():
    js, html = _read(APP), _read(INDEX)
    assert 'id="timeline-undated"' in html and 'id="timeline-export"' in html
    assert 'include_undated' in js
    assert "timeline/export" in js


def test_the_indicator_hunt_covers_the_case_and_reads_a_file():
    js, html = _read(APP), _read(INDEX)
    for name in ("ioc-all", "ioc-filters", "ioc-subdomains", "ioc-file-open", "ioc-file"):
        assert f'id="{name}"' in html, name
    for name in ("runIocFile", "iocOptions", "iocSummary"):
        assert f"function {name}(" in js, name
    assert "/ioc-scan" in js and "/ioc-file" in js
    assert "<th>Analysis</th>" in html


def test_the_grid_offers_dates_summaries_and_sort_priority():
    js, html = _read(APP), _read(INDEX)
    for name in ("date-modal", "summaries-modal", "sort-modal", "rule-values"):
        assert f'id="{name}"' in html, name
    for name in ("openDateFilter", "addDateCondition", "openSummaries", "applySummaries",
                 "openSortPriority", "applySortPriority", "loadRuleValues"):
        assert f"function {name}(" in js, name
    assert "/api/date-ranges" in js
    # a summary is sent as column:operation:kind, the shape the route reads
    assert 'params.append("summary"' in js


def test_an_import_is_followed_and_can_be_stopped():
    js, html = _read(APP), _read(INDEX)
    assert 'id="import-progress-modal"' in html and 'id="import-progress-stop"' in html
    assert 'id="retry-open"' in html and 'id="retry-modal"' in html
    for name in ("startImportJob", "followImportJob", "stopImportJob", "openRetry", "runRetry"):
        assert f"function {name}(" in js, name
    assert "/import-jobs" in js and "/unread" in js


def test_the_report_can_be_generated_as_a_pdf():
    js, html = _read(APP), _read(INDEX)
    assert 'data-act="report-build-pdf"' in html
    assert "buildReport(true)" in js and "/pdf" in js


def test_the_display_preferences_are_remembered_and_applied():
    js, html = _read(APP), _read(INDEX)
    assert 'id="prefs-copy-headers"' in html and 'id="prefs-date-format"' in html
    for name in ("loadCopyPrefs", "saveCopyPrefs", "formatTimestamp"):
        assert f"function {name}(" in js, name
    assert "copyPrefs.headers" in js and "state.timestamps" in js
    assert "localStorage.setItem(\"fireblade.display\"" in js


def test_a_disk_can_be_analysed_from_the_window():
    js, html = _read(APP), _read(INDEX)
    assert 'id="disk-modal"' in html and 'data-act="disk-open"' in html
    for name in ("openDiskDialog", "startDiskAnalysis"):
        assert f"function {name}(" in js, name
    assert "/disk-jobs" in js


def test_a_rule_statistic_is_read_from_the_server():
    js, html = _read(APP), _read(INDEX)
    assert 'id="rule-statistic"' in html and 'id="rule-stat-rank"' in html
    assert "rule.resolved" in js
    for statistic in ("top", "duplicate", "above_avg", "unique"):
        assert f'<option value="{statistic}"' in html, statistic


def test_the_detected_profile_can_be_applied_by_hand():
    js, html = _read(APP), _read(INDEX)
    assert 'data-act="profile-apply"' in html and 'id="profile-note"' in html
    assert "function applyDetectedProfile(" in js
    assert "/profile" in js


def test_a_timeline_row_opens_its_source_line():
    js, html = _read(APP), _read(INDEX)
    assert 'id="timeline-filters"' in html and 'id="source-row-modal"' in html
    assert "function openSourceRow(" in js
    assert "/timeline/row/" in js
    assert "respect_filters" in js


def test_the_two_report_types_share_one_dialog():
    js, html = _read(APP), _read(INDEX)
    assert 'id="report-type"' in html and 'id="report-client-fields"' in html
    assert 'id="client-analyst"' in html and 'id="client-coverage"' in html
    assert "function showReportType(" in js
    assert "/client-report" in js


def test_the_filter_input_keeps_the_operator():
    """A value filtered with "=" must not silently become "contains"."""
    js = _read(APP)
    assert "function filterPrefix(" in js
    assert 'eq: "= "' in js and 'ne: "!= "' in js
