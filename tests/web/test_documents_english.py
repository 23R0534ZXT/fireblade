"""Every document the Host hands over, read for French.

A report, a certificate, an export or a diagnostic leaves the window: nobody translates it on the
way. The case below holds everything those documents talk about — bookmarks and notes, actions of
every owner, priority and status, indicators of every status, a machine, an indicator hunt, a
coverage check — and each document built from it is scanned for French words and accents. The
evidence in it is English on purpose, so a French word is the generator's.
"""

import io
import json
import re

import pytest
from _audit import standard_csv

from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library

FRENCH = re.compile(
    r"\b(octets?|rapport de|Synthèse|Périmètre|Conclusions?|Constats?|Aucun(e)?|"
    r"Opérateur|Témoin|Motif|Méthode|Début|Statut|Priorité|Responsable|À faire|En cours|Terminé|"
    r"Empreintes?|fichiers?|ligne\(s\)|lignes|colonnes?|vérification|détecté|écart|"
    r"Indicateurs?|Actions? ouvertes?|Échéance|Mission|Engagement|Client\s+—)\b|[àâçéèêëîïôùûü]",
    re.IGNORECASE,
)

# words that are English too, or that the evidence of this case holds
ALLOWED = ("é",)


def _plain(text):
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


def _french(text, name):
    found = [match.group(0) for match in FRENCH.finditer(text)]
    found = [word for word in found if word not in ALLOWED]
    assert not found, f"{name}: {sorted(set(found))[:8]}"


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    root = tmp_path_factory.mktemp("documents-cases")
    library = Library(root)
    identifier = InvestigationLibrary(root).create(
        "Documents case", "Everything a document can say", "windows"
    )["id"]
    evidence = tmp_path_factory.mktemp("documents-evidence") / "events.csv"
    evidence.write_text(standard_csv())
    library.import_source(identifier, evidence, organization="files")
    for row in (1, 2, 3, 7):
        library.bookmark(identifier, 0, row, f"a lead on row {row}")
    for number, (owner, priority, status, kind) in enumerate(
        [
            ("us", "low", "todo", "collect"),
            ("client", "medium", "in_progress", "analysis"),
            ("third_party", "high", "waiting_client", "remediation"),
            ("vendor", "critical", "waiting_us", "coordination"),
            ("unassigned", "medium", "blocked", "meeting"),
            ("us", "high", "done", "report"),
            ("client", "low", "cancelled", "legal"),
            ("us", "medium", "todo", "destruction"),
        ]
    ):
        library.add_action(
            identifier,
            {
                "title": f"Action {number}",
                "owner": owner,
                "priority": priority,
                "status": status,
                "type": kind,
                "detail": "details of the action",
            },
        )
    for status, value in (
        ("new", "203.0.113.7"),
        ("confirmed", "evil.example"),
        ("benign", "10.0.0.9"),
        ("unknown", "198.51.100.23"),
    ):
        library.add_indicator(identifier, value, label=f"{status} indicator", status=status)
    library.add_entity(
        identifier, {"kind": "machine", "label": "Finance laptop", "hostname": "FIN-LT-04"}
    )
    library.add_entity(identifier, {"kind": "account", "label": "alice"})
    library.ioc_scan(identifier, 0, "10.0.0.1\nevil.example")
    yield library, identifier
    library.close()


def test_the_investigation_report_has_no_french(case, tmp_path):
    library, identifier = case
    for bookmarks_only in (True, False):
        built = library.report(identifier, "Intrusion review", "scope text", bookmarks_only)
        path = library.report_file(identifier, built["name"])
        _french(
            _plain(path.read_text(encoding="utf-8")), f"investigation report ({bookmarks_only})"
        )


def test_the_client_report_has_no_french(case):
    library, identifier = case
    built = library.client_report(
        identifier,
        title="Client review",
        analyst="A. Analyst",
        include_findings=True,
        include_coverage=True,
    )
    path = library.report_file(identifier, built["name"])
    _french(_plain(path.read_text(encoding="utf-8")), "client report")


def test_the_pdf_of_a_report_has_no_french(case):
    pypdf = pytest.importorskip("pypdf")
    library, identifier = case
    built = library.client_report(identifier, title="Client review", analyst="A. Analyst", pdf=True)
    name = built.get("pdf") or built["name"]
    path = library.report_file(identifier, name)
    if path.suffix != ".pdf":
        pytest.skip("no PDF writer here")
    reader = pypdf.PdfReader(io.BytesIO(path.read_bytes()))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert len(text) > 200
    _french(text, "client report PDF")


def test_the_coverage_report_has_no_french(case):
    library, identifier = case
    library.coverage(identifier)
    as_json = library.coverage_export(identifier).decode("utf-8")
    json.loads(as_json)
    _french(as_json, "coverage JSON")
    _french(library.coverage_export(identifier, as_csv=True).decode("utf-8-sig"), "coverage CSV")


def test_the_timeline_and_the_grid_exports_have_no_french_in_their_headers(case):
    library, identifier = case
    data, _receipt = library.timeline_export(identifier)
    _french(data.decode("utf-8-sig").splitlines()[0], "timeline CSV header")
    path = library.export(identifier, 0)
    _french(path.read_text(encoding="utf-8-sig").splitlines()[0], "grid CSV header")


def test_the_hunt_and_its_saved_record_have_no_french(case):
    library, identifier = case
    result = library.ioc_scan(identifier, 0, "10.0.0.1\nevil.example\nhttps://evil.example/a")
    _french(json.dumps(result["hits"]), "hunt hits")
    for hunt in library.hunts(identifier)["hunts"]:
        _french(json.dumps(library.hunt(identifier, hunt["name"])), "saved hunt")


def test_the_case_and_its_workspace_answers_have_no_french(case):
    library, identifier = case
    for answer in (library.case(identifier), library.workspace(identifier)):
        _french(json.dumps(answer, ensure_ascii=False), "workspace answer")
    _french(library.actions_csv(identifier), "actions CSV")
