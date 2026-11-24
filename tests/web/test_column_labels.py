"""Column names on screen: English for what Fireblade generates, untouched for the analyst's own."""

from fastapi.testclient import TestClient

from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.server import create_app

AUTH = (
    "Nov  1 10:00:01 srv sshd[1]: Failed password for root from 10.0.0.9 port 22 ssh2\n"
    "Nov  1 10:00:05 srv sshd[2]: Accepted password for alice from 10.0.0.5 port 22 ssh2\n"
)
FRENCH_CSV = "Horodatage,Utilisateur,Hôte\n2026-11-01T10:00:00Z,alice,PC01\n"


def _case(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    identifier = InvestigationLibrary(root).create("Labels", "", "linux")["id"]
    return TestClient(create_app(root)), identifier


def _upload(client, identifier, name, text):
    answer = client.post(
        f"/api/cases/{identifier}/upload",
        params={"organization": "files"},
        files={"file": (name, text.encode(), "text/plain")},
    )
    assert answer.status_code == 200, answer.text


def test_a_linux_log_reads_in_english_on_screen_and_in_the_export(tmp_path):
    client, identifier = _case(tmp_path)
    _upload(client, identifier, "auth.log", AUTH)
    columns = client.get(f"/api/cases/{identifier}/analyses/0/columns").json()["columns"]
    assert "Host" in columns and "Timestamp" in columns and "Target user" in columns
    assert not {"Hôte", "Horodatage", "Utilisateur cible"} & set(columns)
    rows = client.get(f"/api/cases/{identifier}/analyses/0/rows", params={"limit": 5}).json()
    assert rows["columns"] == columns
    exported = (
        client.get(f"/api/cases/{identifier}/analyses/0/export")
        .text.lstrip("\ufeff")
        .splitlines()[0]
    )
    assert "Host" in exported and "Hôte" not in exported


def test_a_french_csv_keeps_its_own_headers(tmp_path):
    """The headers of a file the analyst brought are evidence: never translated."""
    client, identifier = _case(tmp_path)
    _upload(client, identifier, "poste.csv", FRENCH_CSV)
    columns = client.get(f"/api/cases/{identifier}/analyses/0/columns").json()["columns"]
    assert columns[-3:] == ["Horodatage", "Utilisateur", "Hôte"]
    exported = (
        client.get(f"/api/cases/{identifier}/analyses/0/export")
        .text.lstrip("\ufeff")
        .splitlines()[0]
    )
    assert exported.split(",")[:3] == ["Horodatage", "Utilisateur", "Hôte"]


def test_an_expression_is_typed_with_the_names_on_screen(tmp_path):
    """The analyst writes lower(Method), what they read; the core stores a French name."""
    client, identifier = _case(tmp_path)
    _upload(client, identifier, "auth.log", AUTH)
    base = f"/api/cases/{identifier}/analyses/0"
    added = client.post(
        f"{base}/derived",
        json={
            "name": "User lower",
            "operation": "expression",
            "expression": "lower([Remote address])",
        },
    )
    assert added.status_code == 200, added.text
    assert "User lower" in added.json()["columns"]
    rows = client.get(f"{base}/rows", params={"limit": 2}).json()
    assert rows["rows"], "the derived column evaluates over the rows"


def test_a_refusal_is_in_english_whatever_module_raised_it(tmp_path):
    client, identifier = _case(tmp_path)
    _upload(client, identifier, "auth.log", AUTH)
    base = f"/api/cases/{identifier}/analyses/0"
    refused = client.post(
        f"{base}/derived",
        json={"name": "broken", "operation": "expression", "expression": "lower("},
    )
    assert refused.status_code == 400
    detail = refused.json()["detail"]
    assert not any(ch in detail for ch in "éèàçô") and "attendu" not in detail, detail


def test_an_organised_family_reads_in_english_and_a_file_the_analyst_brought_keeps_its_name(
    tmp_path,
):
    from fireblade.web.service import Library

    organised = {"path": "/case/collections/import-1/results/organisation-ab12/Persistance.csv"}
    brought = {"path": "/case/evidence/Persistance.csv"}
    assert Library._label(organised, "") == "Persistence"
    assert Library._label(brought, "") == "Persistance.csv", (
        "an analyst's own file name is evidence"
    )


def test_analyses_of_one_database_are_told_apart_by_their_container(tmp_path):
    from fireblade.web.service import Library

    def table(name, container):
        path = tmp_path / f"{name}.csv"
        path.write_text(
            f"WebCache_Table,WebCache_Container\n{name},{container}\n", encoding="utf-8"
        )
        return {"label": "WebCacheV01.dat", "parser": "WebCache", "working_path": str(path)}

    entries = [
        {"label": "WebCacheV01.dat", "source_info": table("a", "History")},
        {"label": "WebCacheV01.dat", "source_info": table("b", "History")},
        {"label": "WebCacheV01.dat", "source_info": table("c", "Cookies")},
        {"label": "other.csv", "source_info": {}},
    ]
    Library._tell_apart(entries)
    assert [e["label"] for e in entries] == [
        "WebCacheV01.dat — History",
        "WebCacheV01.dat — History (2)",
        "WebCacheV01.dat — Cookies",
        "other.csv",
    ]


def test_tables_a_reader_writes_from_one_file_are_named_by_what_the_reader_called_them():
    from fireblade.web.service import Library

    def entry(working, source):
        return {
            "label": source.rsplit("/", 1)[1],
            "source_info": {"working_path": working, "path": source, "parser": "RECmd"},
        }

    entries = [
        entry("/r/20261124201404/20261124201404_AppCompat_/SYSTEM.csv", "/e/SYSTEM"),
        entry("/r/20261124201404/20261124201404_Services_/SYSTEM.csv", "/e/SYSTEM"),
        entry(
            "/r/20261124201403055415_Cars_Companies_af5bcf3f-b316-4e49-8d12-ce9e180b3914.csv",
            "/e/CarsDB.db",
        ),
        entry(
            "/r/20261124201403055415_Cars_MakeModel_af5bcf3f-b316-4e49-8d12-ce9e180b3914.csv",
            "/e/CarsDB.db",
        ),
        entry("/r/20261124201402_Single.csv", "/e/Single.pf"),
    ]
    Library._tell_apart(entries)
    assert [e["label"] for e in entries] == [
        "SYSTEM — AppCompat",
        "SYSTEM — Services",
        "CarsDB.db — Cars_Companies",
        "CarsDB.db — Cars_MakeModel",
        "Single.pf",
    ]


def test_the_alert_file_fireblade_writes_reads_in_english():
    from fireblade.web.service import Library

    source = {"path": "/case/collections/import-1/results/Alertes Hayabusa.csv"}
    assert Library._label(source, "") == "Hayabusa alerts"
