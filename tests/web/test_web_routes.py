"""Every group of the Host API, exercised on a real case.

The parity document says a command is covered "when it works in the browser and
was exercised there". This file is the second half of that proof on the server
side: one test per group of routes, over a case written the way the desktop
writes it, so a route cannot drift into a decorated stub without a red test.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fireblade.core.engine import Case
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.web.service import Library, ServiceError


def _write_csv(path, rows=None):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "Artifact", "User", "SourceIP"])
        writer.writerows(rows or [
            ["2026-11-02T10:00:00Z", "EVTX", "alice", "192.0.2.10"],
            ["2026-11-02T10:01:00Z", "EVTX", "bob", "192.0.2.20"],
            ["2026-11-02T10:02:00Z", "Prefetch", "alice", ""],
        ])


@pytest.fixture()
def case_with_analysis(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    library = InvestigationLibrary(root)
    data = library.create("Routes case", "Written by the test", "windows")
    identifier = data["id"]
    folder = library.folder(identifier)
    analysis = folder / "analysis-1.duckdb"
    source = tmp_path / "rows.csv"
    _write_csv(source)
    case = Case(analysis)
    try:
        case.import_csv(source)
        info = dict(case.info)
    finally:
        case.close()
    snapshot = AnalysisSnapshot(path=str(analysis), source_info=info, view=View(), header_state=b"")
    library.save(identifier, [snapshot], 0, [], None, data["revision"])
    return root, identifier


@pytest.fixture()
def service(case_with_analysis):
    root, identifier = case_with_analysis
    library = Library(root)
    try:
        yield library, identifier
    finally:
        library.close()


def test_health_and_settings_expose_what_the_instance_runs(service):
    library, _identifier = service
    payload = library.settings()
    assert payload["page_size"] > 0
    assert payload["readers"], "the reader inventory must never be empty"
    assert "auto" in payload["csv_encodings"]
    assert ";" in payload["csv_delimiters"]


def test_the_profile_catalogue_is_readable(service):
    library, _identifier = service
    payload = library.profiles()
    names = [item["name"] for item in payload["profiles"]]
    assert "EvtxECmd" in names
    assert all(item["signature"] for item in payload["profiles"])


def test_display_layout_is_saved_in_the_analysis(service):
    library, identifier = service
    library.save_display(identifier, 0, {"widths": {"1": 120}, "hidden": [3],
                                         "pinned": [2], "pinned_right": [4]})
    restored = library.display(identifier, 0)
    assert restored["hidden"] == [3]
    assert restored["pinned"] == [2]
    assert restored["pinned_right"] == [4]
    assert restored["widths"].get("1") == 120


def test_bookmarks_and_cell_notes_round_trip(service):
    library, identifier = service
    row_id = library.rows(identifier, 0, limit=1)["rows"][0][0]
    library.bookmark(identifier, 0, row_id, "seen in the lateral movement")
    marks = {item["row_id"]: item["note"] for item in library.bookmarks(identifier, 0)["bookmarks"]}
    assert marks[row_id] == "seen in the lateral movement"
    library.cell_note(identifier, 0, row_id, 2, "the account is the pivot")
    notes = library.cell_notes(identifier, 0, [row_id])["notes"]
    assert notes[str(row_id)]["2"] == "the account is the pivot"
    # An empty note removes the mark, as the desktop does.
    library.bookmark(identifier, 0, row_id, "")
    assert library.bookmarks(identifier, 0)["bookmarks"] == []


def test_views_are_named_and_replayed(service):
    library, identifier = service
    library.save_view(identifier, 0, "Prefetch only",
                      {"filters": [{"column": 1, "operator": "eq", "value": "Prefetch"}],
                       "sort": 1, "descending": False})
    assert "Prefetch only" in library.views(identifier, 0)["views"]
    view = library.view(identifier, 0, "Prefetch only")
    assert view["filters"][0]["value"] == "Prefetch"
    assert view["sort"] == 1
    with pytest.raises(ServiceError):
        library.view(identifier, 0, "not a view")


def test_colour_rules_round_trip(service):
    library, identifier = service
    library.save_rules(identifier, 0, [{"column": 1, "operator": "eq", "value": "EVTX",
                                        "background": "#ffe08a", "foreground": "#202020",
                                        "bold": False, "enabled": True}])
    stored = library.rules(identifier, 0)["rules"]
    assert len(stored) == 1
    assert stored[0]["value"] == "EVTX"
    with pytest.raises(ServiceError):
        library.save_rules(identifier, 0, [{"column": 1, "operator": "nonsense", "value": "x"}])


def test_a_derived_column_is_added_to_the_analysis(service):
    library, identifier = service
    payload = library.add_derived(identifier, 0, {"name": "UTC timestamp",
                                                  "operation": "timestamp",
                                                  "columns": ["Timestamp"],
                                                  "format": "iso"})
    assert payload["added"] == "UTC timestamp"
    stored = library.derived_columns(identifier, 0)
    assert stored["derived"], "the analysis keeps the definition it was given"
    assert any(name.endswith("UTC timestamp") for name in stored["columns"])
    with pytest.raises(ValueError):
        library.add_derived(identifier, 0, {"name": "broken", "operation": "upper",
                                           "columns": ["User"]})


def test_the_timeline_counts_the_dated_rows(service):
    library, identifier = service
    payload = library.timeline(identifier)
    assert payload["count"] == 3
    assert len(payload["rows"]) == 3
    assert payload["sources"], "the legend must name the analysis it read"
    assert payload["sources"][0]["dated"] == 3
    assert payload["histogram"]["bins"] > 0


def test_a_global_search_finds_the_value_and_names_its_analysis(service):
    library, identifier = service
    payload = library.search(identifier, "alice")
    assert payload["total"] >= 2
    assert payload["analyses"], "a hit must say which analysis it comes from"
    assert payload["analyses"][0]["count"] >= 1
    with pytest.raises(ServiceError):
        library.search(identifier, "   ")


def test_an_ioc_scan_matches_the_pasted_indicator(service):
    library, identifier = service
    payload = library.ioc_scan(identifier, 0, "192.0.2.20\nalice.example.com")
    assert payload["indicators"] == 2, "both pasted indicators must be parsed"
    assert payload["scanned"] == 3
    assert payload["hits"], "the pasted address is in the case"
    assert payload["hits"][0]["kind"] == "ip"
    assert payload["saved"], "a scan leaves a hunt file in the case"
    with pytest.raises(ServiceError):
        library.ioc_scan(identifier, 0, "")


def test_an_ioc_hunt_is_saved_and_replayed(service):
    library, identifier = service
    first = library.ioc_scan(identifier, 0, "192.0.2.20")
    hunts = library.hunts(identifier)["hunts"]
    assert hunts, "a hunt must leave a record in the case"
    replayed = library.hunt(identifier, first["saved"])
    assert replayed["indicators"], "a saved hunt restores its indicator list"
    assert hunts[0]["hits"] >= 1


def test_the_attack_graph_refuses_on_an_empty_case(service):
    """No finding and no declared machine is a readable refusal, not an empty graph."""
    library, identifier = service
    with pytest.raises(ServiceError) as caught:
        library.graph(identifier)
    assert "machine" in str(caught.value).lower() or "detection" in str(caught.value).lower()
    with pytest.raises(ServiceError):
        library.graph(identifier, navigator=True)


def test_the_client_report_is_written_and_served_back(service):
    library, identifier = service
    row_id = library.rows(identifier, 0, limit=1)["rows"][0][0]
    library.bookmark(identifier, 0, row_id, "opening of the escalation")
    payload = library.report(identifier, "Case report", "for the client")
    name = payload["name"] if isinstance(payload, dict) else payload
    path = library.report_file(identifier, name)
    text = path.read_text(encoding="utf-8", errors="replace")
    assert "Case report" in text
    assert "opening of the escalation" in text


def test_tracking_actions_are_created_updated_and_exported(service):
    library, identifier = service
    created = library.add_action(identifier, {"title": "Ask for DNS logs", "owner": "client",
                                              "priority": "high"})
    action_id = created.get("id") or created.get("action", {}).get("id")
    assert action_id
    library.update_action(identifier, action_id, {"status": "done"})
    listing = library.workspace(identifier)
    assert listing is not None
    csv_text = library.actions_csv(identifier)
    assert "Ask for DNS logs" in csv_text and "done" in csv_text


def test_pivot_answers_what_launched_a_process(service, tmp_path):
    """A row that names a process is answered; a row that names none is refused."""
    library, identifier = service
    with pytest.raises(ServiceError):
        library.pivot(identifier, 0, library.rows(identifier, 0, limit=1)["rows"][0][0])
    processes = tmp_path / "processes.csv"
    with processes.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "EventId", "Image", "ParentImage"])
        writer.writerows([["2026-11-02T10:00:00Z", "4688", r"C:\Windows\notepad.exe", r"C:\Windows\explorer.exe"],
                          ["2026-11-02T10:01:00Z", "4688", r"C:\Windows\cmd.exe", r"C:\Windows\notepad.exe"]])
    library.import_source(identifier, processes)
    index = len(library.case(identifier)["analyses"]) - 1
    row_id = library.rows(identifier, index, limit=1)["rows"][0][0]
    payload = library.pivot(identifier, index, row_id)
    assert payload["anchor"]["process"].endswith("notepad.exe")
    assert payload["total"] >= 1, "the child process must be found"


def test_the_import_history_lists_the_files_of_the_case(service):
    library, identifier = service
    payload = library.imports(identifier)
    assert "collections" in payload


def test_detection_refuses_with_a_readable_reason(service):
    library, identifier = service
    with pytest.raises(ServiceError) as caught:
        library.detect(identifier, "low")
    message = str(caught.value)
    assert message and "Hayabusa" not in message or message.endswith("."), message
    assert len(message) > 10, "a refusal must say why"


def test_the_unknown_case_is_refused_everywhere(service):
    library, _identifier = service
    for call in (lambda: library.case("missing"), lambda: library.rows("missing", 0),
                 lambda: library.workspace("missing")):
        with pytest.raises((ServiceError, KeyError, OSError, ValueError)):
            call()

ALERTS = [
    ["2026-11-02T10:00:00Z", "Suspicious Logon", "high", "PC-1", "Security", "4624",
     "Credential Access", "T1003", "logon outside hours"],
    ["2026-11-02T10:05:00Z", "Suspicious Logon", "high", "PC-2", "Security", "4624",
     "Credential Access", "T1003", "logon outside hours"],
    ["2026-11-02T11:00:00Z", "LSASS access", "critical", "PC-1", "Security", "4656",
     "Credential Access", "T1003.001", "handle to lsass"],
]


def _import_alerts(library, identifier, tmp_path):
    source = tmp_path / "Alertes Hayabusa.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "RuleTitle", "Level", "Computer", "Channel",
                         "EventID", "MitreTactics", "MitreTags", "Details"])
        writer.writerows(ALERTS)
    library.import_source(identifier, source)
    return len(library.case(identifier)["analyses"]) - 1


def test_a_finding_marks_every_alert_it_names(service, tmp_path):
    """The desktop marks a finding's alerts in one gesture; so does the Host."""
    library, identifier = service
    index = _import_alerts(library, identifier, tmp_path)
    result = library.bookmark_finding(identifier, index, {
        "Timestamp": "2026-11-02T10:05:00Z", "Computer": "PC-2", "EventID": "4624",
        "RuleTitle": "Suspicious Logon"})
    assert result["matched"] == 1
    assert result["marked"] == 1
    marks = library.bookmarks(identifier, index)["bookmarks"]
    assert len(marks) == 1
    assert marks[0]["note"] == "Hayabusa: Suspicious Logon"
    # Only the rule name: every alert it fired on is marked.
    result = library.bookmark_finding(identifier, index, {"RuleTitle": "Suspicious Logon"})
    assert result["matched"] == 2
    assert len(library.bookmarks(identifier, index)["bookmarks"]) == 2


def test_the_alert_sources_of_a_run_can_be_taken_away(service):
    library, identifier = service
    folder = library.library.folder(identifier) / "collections" / "import-test" / "results" / "hayabusa-abc"
    folder.mkdir(parents=True)
    alerts = folder / "Alertes Hayabusa.csv"
    alerts.write_text("Timestamp,RuleTitle\n2026-11-02T10:00:00Z,Rule\n", encoding="utf-8")
    assert library.detection_sources(identifier, "import-test") == alerts
    with pytest.raises(ServiceError):
        library.detection_sources(identifier, "import-missing")

def test_merging_the_same_collection_twice_adds_nothing(service, tmp_path):
    """A detection re-reads its collection: its analyses must not double up."""
    library, identifier = service
    source = tmp_path / "again.csv"
    _write_csv(source)
    imported = library.import_source(identifier, source)
    before = len(library.case(identifier)["analyses"])
    session = Path(imported["collection"]) / "collection.fireblade-session"
    assert session.is_file()
    _first, added = library._merge_session(identifier, session)
    assert added == 0
    assert len(library.case(identifier)["analyses"]) == before


def test_an_analysis_is_found_by_its_path(service, tmp_path):
    library, identifier = service
    source = tmp_path / "located.csv"
    _write_csv(source)
    library.import_source(identifier, source)
    analyses = library.case(identifier)["analyses"]
    assert library._analysis_index_of(identifier, analyses[-1]["path"]) == len(analyses) - 1
    assert library._analysis_index_of(identifier, "/nowhere/absent.timeline") is None

DEMO_PLUGIN = {"name": "Demo profile", "signature": ["Timestamp", "User"],
               "columns": ["Timestamp", "User"], "timestamp": ["Timestamp"],
               "booleans": [], "transforms": []}


def test_a_presentation_plugin_is_installed_and_listed(service, tmp_path):
    """A plugin declares columns and types; installing it makes the core see it."""
    library, _identifier = service
    library.plugins_root = tmp_path / "plugins"
    installed = library.install_plugin(DEMO_PLUGIN)
    assert installed["name"] == "Demo profile"
    listing = library.plugins()
    assert [item["name"] for item in listing["plugins"]] == ["Demo profile"]
    assert listing["files"] == [Path(installed["path"]).name]
    assert listing["errors"] == []
    # A broken file is reported, never silently skipped.
    (library.plugins_root / "broken.json").write_text("{not json", encoding="utf-8")
    assert library.plugins()["errors"]
    with pytest.raises((ValueError, ServiceError)):
        library.install_plugin({"name": "no signature"})


def test_a_profile_is_created_from_the_open_analysis(service, tmp_path):
    library, identifier = service
    library.plugins_root = tmp_path / "plugins-created"
    created = library.create_profile(identifier, 0, "This case's columns")
    assert created["fields"]["columns"] >= 4
    assert created["fields"]["signature"] == 3
    assert any(item["name"] == "This case's columns" for item in library.plugins()["plugins"])
    with pytest.raises(ServiceError):
        library.create_profile(identifier, 0, "   ")

def test_an_alert_points_to_its_source_event(service, tmp_path):
    """The desktop opens the EVTX event an alert came from; the Host says where it is."""
    library, identifier = service
    events = tmp_path / "System.csv"
    with events.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["TimeCreated", "EventRecordId", "Computer", "EventId"])
        writer.writerows([["2026-11-02T10:00:00Z", "4624", "PC-1", "7045"],
                          ["2026-11-02T10:00:01Z", "4625", "PC-1", "7045"]])
    library.import_source(identifier, events)
    source_index = len(library.case(identifier)["analyses"]) - 1

    alerts = tmp_path / "alerts.csv"
    with alerts.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "RuleTitle", "Level", "RecordID", "Fireblade_EVTX_Source"])
        writer.writerow(["2026-11-02T10:00:00Z", "Suspicious Service", "high", "4624", str(events)])
    library.import_source(identifier, alerts)
    alert_index = len(library.case(identifier)["analyses"]) - 1

    row_id = library.rows(identifier, alert_index, limit=1)["rows"][0][0]
    payload = library.alert_source_event(identifier, alert_index, row_id)
    assert payload["analysis"] == source_index
    assert payload["column"] == "EventRecordId"
    assert payload["value"] == "4624"
    assert payload["matches"] == 1

    # A row that is not an alert is refused, with a readable reason.
    plain = library.rows(identifier, 0, limit=1)["rows"][0][0]
    with pytest.raises(ServiceError):
        library.alert_source_event(identifier, 0, plain)
    with pytest.raises(ServiceError):
        library.alert_context(identifier, 0, plain)


def test_the_context_of_an_alert_needs_an_alert(service):
    library, identifier = service
    plain = library.rows(identifier, 0, limit=1)["rows"][0][0]
    with pytest.raises(ServiceError) as caught:
        library.alert_context(identifier, 0, plain, minutes=5)
    assert "EVTX" in str(caught.value) or "alert" in str(caught.value).lower()

def test_the_timeline_reads_a_date_the_way_the_analyst_chooses(service):
    """The desktop offers three readings per analysis; so does the Host."""
    library, identifier = service
    auto = library.timeline(identifier)
    assert auto["sources"][0]["dated"] == 3
    assert auto["sources"][0]["headers"][0] == "Timestamp"
    assert auto["sources"][0]["chosen"] == "auto"

    none = library.timeline(identifier, dates={"0": "none"})
    assert none["sources"][0]["dated"] == 0
    assert none["sources"][0]["undated"] == 3

    named = library.timeline(identifier, dates={"0": "Timestamp"})
    assert named["sources"][0]["dated"] == 3
    assert named["sources"][0]["chosen"] == "Timestamp"

    with pytest.raises(ServiceError):
        library.timeline(identifier, dates={"0": "NotAColumn"})
    with pytest.raises(ServiceError):
        library.timeline(identifier, dates={"9": "none"})

def test_the_timeline_can_read_two_columns_as_one_date(service, tmp_path):
    """IIS and W3C exports keep the date and the time apart; the desktop joins them."""
    library, identifier = service
    source = tmp_path / "iis.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "date", "time", "User", "SourceIP"])
        writer.writerows([["2026-11-02T00:00:00Z", "2026-11-02", "10:00:01", "alice", "192.0.2.10"],
                          ["2026-11-02T00:00:00Z", "2026-11-02", "10:00:02", "bob", "192.0.2.20"]])
    library.import_source(identifier, source)
    index = len(library.case(identifier)["analyses"]) - 1

    guessed = library.timeline(identifier)
    entry = next(item for item in guessed["sources"] if item["id"] == index)
    assert entry["column_name"] == "timestamp"
    assert entry["split"] is True, "the two columns are there, the option must be offered"

    joined = library.timeline(identifier, dates={str(index): "split"})
    entry = next(item for item in joined["sources"] if item["id"] == index)
    assert entry["column_name"] == "date + time"
    assert entry["combined"] is True
    assert entry["dated"] == 2

def test_a_free_node_joins_the_graph_and_stays_with_the_case(service):
    library, identifier = service
    with pytest.raises(ServiceError):
        library.graph(identifier)          # nothing to draw yet, and it says so
    node = library.add_graph_node(identifier, "SRV-EXCHANGE", tags="host, pivot")
    assert node["label"] == "SRV-EXCHANGE"
    assert node["tags"] == ["host", "pivot"]
    assert node["id"].startswith("custom-")
    graph = library.graph(identifier)
    assert any(item["label"] == "SRV-EXCHANGE" for item in graph["nodes"])
    with pytest.raises(ServiceError):
        library.add_graph_node(identifier, "   ")

def test_a_machine_is_declared_and_reaches_the_graph(service):
    """The desktop's "Machine ou compte" dialog, and what the graph reads."""
    library, identifier = service
    machine = library.add_entity(identifier, {"kind": "machine", "label": "SRV-DC01",
                                              "hostname": "srv-dc01", "ip": "10.0.0.5",
                                              "os": "Windows Server 2022"})
    assert machine["kind"] == "machine"
    assert machine["hostname"] == "srv-dc01"
    account = library.add_entity(identifier, {"kind": "account", "label": "admin.svc"})
    assert account["kind"] == "account"
    workspace = library.workspace(identifier)
    assert {item["label"] for item in workspace["entities"]} == {"SRV-DC01", "admin.svc"}
    graph = library.graph(identifier)
    assert any(item["label"] == "SRV-DC01" for item in graph["nodes"])
    with pytest.raises(ServiceError):
        library.add_entity(identifier, {"kind": "machine", "label": "  "})
    with pytest.raises(ServiceError):
        library.add_entity(identifier, {"kind": "nonsense", "label": "x"})


def test_indicators_are_tracked_and_removed(service):
    """A tracked list, not only a pasted scan: the case remembers it."""
    library, identifier = service
    single = library.add_indicator(identifier, "192.0.2.66", label="C2 candidate")
    assert single["added"] == 1
    batch = library.add_indicator(identifier, "192.0.2.66\nevil.example.com\nnot-an-ioc!!")
    assert batch["added"] == 1 or batch["skipped"] >= 1
    tracked = library.workspace(identifier)["iocs"]
    assert any(item["value"] == "192.0.2.66" for item in tracked)
    assert any(item["value"] == "evil.example.com" for item in tracked)
    identity = next(item["id"] for item in tracked if item["value"] == "192.0.2.66")
    library.remove_indicator(identifier, identity)
    assert all(item["value"] != "192.0.2.66" for item in library.workspace(identifier)["iocs"])
    with pytest.raises(ServiceError):
        library.add_indicator(identifier, "   ")
    with pytest.raises((ValueError, ServiceError)):
        library.remove_indicator(identifier, "not-an-id")

RULE_TEXT = """title: Suspicious Service Path
id: 11111111-2222-3333-4444-555555555555
status: test
level: high
logsource:
    product: windows
    service: system
detection:
    selection:
        EventID: 7045
    condition: selection
"""


def _fake_pack(tmp_path):
    pack = tmp_path / "tools"
    rules = pack / "Hayabusa" / "rules" / "hayabusa" / "builtin"
    rules.mkdir(parents=True)
    (rules / "susp.yml").write_text(RULE_TEXT, encoding="utf-8")
    return pack


def test_detection_rules_are_listed_edited_and_toggled(service, tmp_path):
    """The desktop's "Règles de détection" dialog, over HTTP."""
    library, _identifier = service
    library.tools_root = _fake_pack(tmp_path)
    library.plugins_root = tmp_path / "plugins"
    listing = library.rules_inventory()
    assert listing["count"] == 1
    rule = listing["rules"][0]
    assert rule["title"] == "Suspicious Service Path"
    assert rule["level"] == "high"
    assert rule["enabled"] is True

    text = library.rule_text("susp.yml")["text"]
    assert "EventID: 7044" not in text
    library.save_rule("susp.yml", text.replace("7045", "7044"))
    edited = library.rules_inventory()["rules"][0]
    assert edited["source"] == "user"
    assert "7044" in library.rule_text("susp.yml")["text"]

    library.set_rule_enabled("susp.yml", False)
    assert library.rules_inventory()["rules"][0]["enabled"] is False
    assert library.rules_inventory(changed_only=True)["count"] == 1

    library.reset_rule("susp.yml")
    back = library.rules_inventory()["rules"][0]
    assert back["source"] == "pack"
    assert "7045" in library.rule_text("susp.yml")["text"]

    with pytest.raises(ValueError):
        library.save_rule("susp.yml", "title: only a title\n")
    with pytest.raises(ValueError):
        library.save_rule("susp.txt", text)


def test_the_rules_need_a_tool_pack(service):
    library, _identifier = service
    library.tools_root = None
    with pytest.raises(ServiceError):
        library.rules_inventory()


def test_global_rules_reach_every_analysis_that_has_the_column(service, tmp_path):
    """The desktop's "Règles globales": one book, applied wherever the column fits."""
    library, identifier = service
    library.plugins_root = tmp_path / "plugins"
    saved = library.save_global_rules(
        [{"column": "User", "operator": "eq", "value": "alice",
          "background": "#ffe08a", "foreground": "#202020", "bold": True, "enabled": True}],
        headers=["User", "SourceIP"])
    assert saved["saved"] == 1

    state = library.global_rules(identifier, 0)
    assert state["stored"] == 1
    assert state["enabled"] is True
    assert state["applied"] == 1
    assert state["effective"][0]["column"] == 2, state["effective"]
    assert state["rules"][0]["column_name"] == "User"

    # An analysis without that column keeps its rows uncoloured, and says why.
    other = library.save_global_rules(
        [{"column": "Domain", "operator": "contains", "value": "corp", "enabled": True}])
    assert other["saved"] == 1
    state = library.global_rules(identifier, 0)
    assert state["applied"] == 0
    assert state["skipped"], "a rule whose column is absent must be reported, not silently dropped"

    library.set_global_rules_enabled(False)
    assert library.global_rules(identifier, 0)["enabled"] is False
    library.set_global_rules_enabled(True)

    data = library.global_rules_file()
    assert b"fireblade-global-rules" in data
    imported = library.import_global_rules(data)
    assert imported["imported"] == 1
    with pytest.raises(ValueError):
        library.import_global_rules(b'{"format": "something else"}')


def test_the_coverage_check_reads_the_case_and_keeps_its_report(service):
    """The desktop's "Vérification des imports et diagnostics", over HTTP."""
    library, identifier = service
    result = library.coverage(identifier, expected="observed")
    report = result["report"]
    assert report["format"] == "fireblade-coverage"
    assert report["expected_profile"] == "observed"
    assert result["analyses"] == 1
    assert result["counts"].get("error", 0) == 0 or report["findings"]
    # every finding says what it costs and what to do about it
    for finding in report["findings"]:
        assert finding["stage"] and finding["severity"] in ("info", "warning", "error")
        assert finding["reason"]
        assert finding["action"] or finding["code"] == "operation"
    kept = library.coverage_report(identifier)
    assert kept["report"]["created"] == report["created"]
    data = library.coverage_export(identifier)
    assert b"fireblade-coverage" in data
    flat = library.coverage_export(identifier, as_csv=True)
    assert b"Gravit" in flat
    with pytest.raises(ServiceError):
        library.coverage(identifier, expected="nonsense")


def test_the_timeline_exports_a_verified_file(service):
    """The desktop's "Exporter la chronologie": rows written and counted."""
    library, identifier = service
    payload = library.timeline(identifier)
    assert payload["extent"]["rows"] == 3
    data, receipt = library.timeline_export(identifier)
    assert data.startswith(b"\xef\xbb\xbf"), "the desktop writes a BOM for Excel"
    text = data.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("Date_UTC")
    assert len(text.strip().splitlines()) == 4, "three rows and the header"
    assert receipt["written"] == receipt["expected"] == 3
    assert len(receipt["sha256"]) == 64


def test_rows_without_a_date_join_the_timeline_on_request(tmp_path):
    """A row the sender never dated is shown when the analyst asks for it."""
    root = tmp_path / "cases"
    root.mkdir()
    book = InvestigationLibrary(root)
    data = book.create("Undated case", "One row without a date", "windows")
    identifier = data["id"]
    folder = book.folder(identifier)
    analysis = folder / "analysis-1.duckdb"
    source = tmp_path / "undated.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "Artifact", "User", "SourceIP"])
        writer.writerow(["2026-11-02T10:00:00Z", "EVTX", "alice", "192.0.2.10"])
        writer.writerow(["", "Prefetch", "bob", "192.0.2.20"])
    case = Case(analysis)
    try:
        case.import_csv(source)
        info = dict(case.info)
    finally:
        case.close()
    snapshot = AnalysisSnapshot(path=str(analysis), source_info=info, view=View(), header_state=b"")
    book.save(identifier, [snapshot], 0, [], None, data["revision"])
    library = Library(root)
    instant = int(datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    try:
        whole = library.timeline(identifier)
        assert whole["extent"]["rows"] == 2, "no window: every row is there"
        assert whole["extent"]["dated"] == 1
        # A window keeps the dated rows; the undated one joins only when asked.
        windowed = library.timeline(identifier, start=instant, end=instant)
        assert windowed["extent"]["rows"] == 1
        with_undated = library.timeline(identifier, start=instant, end=instant, include_undated=True)
        assert with_undated["extent"]["rows"] == 2
        assert with_undated["count"] == 2
        data_bytes, receipt = library.timeline_export(identifier, start=instant, end=instant,
                                                      include_undated=True)
        assert receipt["written"] == 2
        assert "Fuseau_UTC_supposé" in data_bytes.decode("utf-8-sig").splitlines()[0]
    finally:
        library.close()


def test_an_indicator_hunt_covers_every_analysis_and_respects_the_filters(tmp_path):
    """The desktop's IOC tab: one list, the whole case, each view's own filters."""
    from fireblade.core.models import Filter

    root = tmp_path / "cases"
    root.mkdir()
    book = InvestigationLibrary(root)
    data = book.create("Hunt case", "Indicators across two analyses", "windows")
    identifier = data["id"]
    folder = book.folder(identifier)
    documents = []
    rows = [
        ["2026-11-02T10:00:00Z", "EVTX", "alice", "192.0.2.10"],
        ["2026-11-02T10:01:00Z", "Prefetch", "bob", "host.evil.example.com"],
        ["2026-11-02T10:02:00Z", "EVTX", "carol", "plain.example.com"],
    ]
    for number, keep in ((1, None), (2, "EVTX")):
        analysis = folder / f"analysis-{number}.duckdb"
        source = tmp_path / f"rows-{number}.csv"
        with source.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["Timestamp", "Artifact", "User", "SourceIP"])
            writer.writerows(rows)
        case = Case(analysis)
        try:
            case.import_csv(source)
            info = dict(case.info)
        finally:
            case.close()
        view = View(filters=[Filter(1, "eq", keep)]) if keep else View()
        documents.append(AnalysisSnapshot(path=str(analysis), source_info=info, view=view,
                                          header_state=b""))
    book.save(identifier, documents, 0, [], None, data["revision"])
    library = Library(root)
    try:
        single = library.ioc_scan(identifier, 0, "192.0.2.10")
        assert single["indicators"] == 1
        assert len(single["hits"]) == 1, "the address is in one row of the first analysis"

        whole = library.ioc_scan(identifier, 0, "192.0.2.10", all_analyses=True)
        assert {item["analysis"] for item in whole["hits"]} == {0, 1}
        assert whole["scanned"] == 6, "every row of both analyses is read"

        filtered = library.ioc_scan(identifier, 0, "192.0.2.10", all_analyses=True, respect_filters=True)
        assert filtered["scanned"] == 5, "the EVTX filter holds one of the six rows back"

        with_sub = library.ioc_scan(identifier, 0, "evil.example.com", include_subdomains=True)
        without_sub = library.ioc_scan(identifier, 0, "evil.example.com", include_subdomains=False)
        assert len(with_sub["hits"]) == 1, "host.evil.example.com is found under the domain"
        assert not without_sub["hits"], "without sub-domains the same value is not a match"
    finally:
        library.close()


def test_group_summaries_and_the_order_of_the_groups(service):
    """The desktop's "Résumés et tri des groupes": aggregates, and how groups rank."""
    library, identifier = service
    plain = library.rows(identifier, 0, groups=[1], limit=10)
    assert plain["grouped"] is True
    assert plain["rows"] and len(plain["rows"][0]) == 2, "a group row is a value and a count"

    with_summary = library.rows(identifier, 0, groups=[1], limit=10,
                                summaries=[(2, "distinct", "text")])
    assert with_summary["summaries"][0]["operation"] == "distinct"
    assert with_summary["summaries"][0]["name"] == "User"
    assert len(with_summary["rows"][0]) == 3, "the summary rides beside the count"

    by_value = library.rows(identifier, 0, groups=[1], limit=10,
                            order="value", order_descending=False)
    values = [str(row[0]) for row in by_value["rows"]]
    assert values == sorted(values), "groups sorted by their value, ascending"

    by_count = library.rows(identifier, 0, groups=[1], limit=10, order="count", order_descending=True)
    counts = [row[1] for row in by_count["rows"]]
    assert counts == sorted(counts, reverse=True)

    with pytest.raises(ServiceError):
        library.rows(identifier, 0, groups=[1], summaries=[(2, "sum", "text")])
    with pytest.raises(ServiceError):
        library.rows(identifier, 0, groups=[1], order="summary")


def test_the_named_date_windows_come_from_the_core(service):
    library, _identifier = service
    names = [item["name"] for item in library.date_ranges()["ranges"]]
    for expected in ("Today", "Yesterday", "ThisWeek", "LastWeek", "Earlier"):
        assert expected in names


def test_an_import_runs_in_the_background_and_can_be_followed(service, tmp_path):
    """A collection takes minutes: it runs in a job, not inside the request."""
    import time

    library, identifier = service
    source = tmp_path / "extra.csv"
    _write_csv(source)
    started = library.start_import_job(identifier, source)
    assert started["status"] == "running"
    state = None
    for _ in range(300):
        state = library.import_job(started["job"])
        if state["status"] not in ("running", "cancelling"):
            break
        time.sleep(0.1)
    assert state is not None and state["status"] == "complete", state
    assert state["result"]["analyses"] >= 1
    assert state["log"], "the job keeps the lines the collection reported"
    # A finished job cannot be cancelled twice, and says so instead of lying.
    again = library.cancel_import_job(started["job"])
    assert again["cancelled"] is False
    with pytest.raises(ServiceError):
        library.import_job("not-a-job")


def test_unread_files_are_listed_with_the_readers_that_can_retry(service):
    library, identifier = service
    listing = library.unread_files(identifier)
    assert listing["count"] == 0, "the fixture case read everything it was given"
    assert set(listing["readers"]) == {"text", "html", "csv", "pdf"}
    with pytest.raises(ServiceError):
        library.retry_file(identifier, "import-nope", "/tmp/whatever", "text")
    with pytest.raises(ServiceError):
        library.retry_file(identifier, "import-x", "/tmp/whatever", "nonsense")


def test_a_report_can_leave_as_a_pdf(service):
    """The container has no Qt: the Host writes the PDF itself, from the same HTML."""
    library, identifier = service
    built = library.report(identifier, "A test report", "Written by the suite")
    assert built["name"].endswith(".html")
    made = library.report_pdf(identifier, built["name"])
    assert made["name"].endswith(".pdf")
    assert made["bytes"] > 800
    path = library.library.folder(identifier) / "reports" / made["name"]
    data = path.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert data.rstrip().endswith(b"%%EOF")
    assert b"/Type /Catalog" in data and b"/Type /Pages" in data
    assert b"Fireblade Host" in data
    # The text of the report is in the content streams, not just a header.
    assert b"test report" in data or b"A test report" in data
    with pytest.raises(ServiceError):
        library.report_pdf(identifier, "../case.json")


def test_a_disk_is_walked_in_the_background(service, tmp_path):
    """The desktop's "Analyser un disque…": a volume walked, its artifacts read."""
    import time

    library, identifier = service
    volume = tmp_path / "volume"
    (volume / "Windows" / "System32" / "winevt" / "Logs").mkdir(parents=True)
    source = volume / "Windows" / "System32" / "winevt" / "Logs" / "System.evtx"
    _write_csv(source)  # the extension is what the walk looks at
    started = library.start_disk_job(identifier, str(volume), "mounted")
    assert started["status"] == "running"
    state = None
    for _ in range(600):
        state = library.import_job(started["job"])
        if state["status"] not in ("running", "cancelling"):
            break
        time.sleep(0.1)
    assert state is not None, "the job must answer"
    assert state["status"] in ("complete", "error"), state
    if state["status"] == "complete":
        disk = state["result"]["disk"]
        assert disk.get("visited", 0) >= 1
    with pytest.raises(ServiceError):
        library.start_disk_job(identifier, str(volume), "nonsense")


def test_a_colour_rule_can_carry_a_statistic(service):
    """The desktop's "Valeurs les plus élevées", "Doublons", "Au-dessus de la moyenne"."""
    library, identifier = service
    library.save_rules(identifier, 0, [
        {"column": 1, "operator": "contains", "value": "", "statistic": "top",
         "stat_rank": "2", "background": "#ffe08a"},
        {"column": 1, "operator": "contains", "value": "", "statistic": "duplicate",
         "background": "#d9f2c4"},
    ])
    rules = library.rules(identifier, 0)["rules"]
    assert len(rules) == 2
    top = rules[0]
    assert top["statistic"] == "top"
    assert top["resolved"]["values"], "a resolved statistic names its values"
    assert len(top["resolved"]["values"]) <= 2
    duplicates = rules[1]
    assert duplicates["resolved"]["values"], "Artifact repeats, so a duplicate rule names it"
    with pytest.raises(ServiceError):
        library.save_rules(identifier, 0, [{"column": 1, "operator": "contains", "value": "",
                                            "statistic": "nonsense"}])


def test_a_rule_can_select_the_values_above_the_average(tmp_path):
    """A numeric column, an average, and the rows above it."""
    root = tmp_path / "cases"
    root.mkdir()
    book = InvestigationLibrary(root)
    data = book.create("Averages", "Numeric column", "windows")
    identifier = data["id"]
    folder = book.folder(identifier)
    analysis = folder / "analysis-1.duckdb"
    source = tmp_path / "numbers.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "Artifact", "Bytes"])
        writer.writerow(["2026-11-02T10:00:00Z", "EVTX", "100"])
        writer.writerow(["2026-11-02T10:01:00Z", "EVTX", "200"])
        writer.writerow(["2026-11-02T10:02:00Z", "Prefetch", "900"])
    case = Case(analysis)
    try:
        case.import_csv(source)
        info = dict(case.info)
    finally:
        case.close()
    snapshot = AnalysisSnapshot(path=str(analysis), source_info=info, view=View(), header_state=b"")
    book.save(identifier, [snapshot], 0, [], None, data["revision"])
    library = Library(root)
    try:
        library.save_rules(identifier, 0, [
            {"column": 2, "operator": "contains", "value": "", "statistic": "above_avg",
             "value_column": 2, "background": "#cfe3ff"}])
        rule = library.rules(identifier, 0)["rules"][0]
        assert rule["resolved"]["compare"] == "ge"
        assert rule["resolved"]["threshold"] == pytest.approx(400.0)
        assert rule["resolved"]["strict"] is True
    finally:
        library.close()
