"""The documents the Host hands out are written in English, and the evidence in them is not touched."""

import html
import os
import re
import types
from datetime import datetime
from pathlib import Path

from fireblade.core import client_report
from fireblade.core.case_destruction import destroy_case
from fireblade.web import english

# An accent, or a word English never uses: the mark of a sentence left in its source language.
FRENCH = re.compile(
    r"[àâçéèêëîïôûùüœÉÈÀÊ]|\b(Aucun|Aucune|Généré|Périmètre|Synthèse|Constats?|"
    r"Fichiers?|Opérateur|Témoin|détruit|Référence|dans|pour|sont)\b"
)


def _nodes(document):
    stripped = re.sub(r"<(style|pre|code)\b.*?</\1>", "", document, flags=re.S)
    return [
        html.unescape(text).strip() for text in re.findall(r">([^<>]+)<", stripped) if text.strip()
    ]


def _group(**values):
    return types.SimpleNamespace(**values)


def _client_document():
    when = datetime.fromisoformat
    high = _group(
        level="high",
        severity=4,
        title="Suspicious service",
        host="SRV01",
        count=12,
        start=when("2026-11-01T10:00:00+00:00"),
        end=when("2026-11-01T11:00:00+00:00"),
        event_ids=["7045"],
        tactics="Persistence",
        techniques="T1543",
    )
    critical = _group(
        level="critical",
        severity=5,
        title="Credential dumping",
        host="PC02",
        count=3,
        start=when("2026-11-01T12:00:00+00:00"),
        end=when("2026-11-01T12:30:00+00:00"),
        event_ids=["4688"],
        tactics="Credential Access",
        techniques="T1003",
    )
    incident = _group(
        groups=[high, critical],
        hits=15,
        level="high",
        title="x",
        start=when("2026-11-01T10:00:00+00:00"),
        end=when("2026-11-01T12:30:00+00:00"),
    )
    analysis = _group(
        source_info={"path": r"C:\evidence\Security.evtx", "sha256": "ab" * 32, "rows": 1200},
        path="/case/analysis.timeline",
    )
    workspace = dict(
        client={"name": "ACME", "reference": "REF-1"},
        engagement={
            "notes": "Scope",
            "contract": "C-9",
            "lead": "Jane",
            "start": "2026-10-30",
            "end": "2026-11-20",
        },
        actions=[
            dict(
                title="Isolate",
                detail="now",
                owner="client",
                status="todo",
                priority="high",
                type="remediation",
                date="2026-11-02",
                machine="SRV01",
                intervenant="",
            ),
            dict(
                title="Report",
                detail="",
                owner="us",
                status="done",
                priority="low",
                type="report",
                date="2026-11-03",
                machine="",
                intervenant="",
            ),
        ],
        entities=[
            dict(
                kind="machine", label="SRV01", hostname="srv01", ip="10.0.0.5", os="Linux", tags=[]
            )
        ],
        iocs=[
            dict(
                kind="ip",
                value="203.0.113.7",
                status="confirmed",
                machine="SRV01",
                label="c2",
                source="",
            )
        ],
        destruction=[
            dict(
                label="DoD",
                method="dod3",
                started="2026-11-20T10:00:00+00:00",
                operator="Jane",
                witness="Bob",
                files=[1, 2],
                status="complete",
            )
        ],
    )
    return client_report.build(
        title="Client report — ACME",
        case_name="ACME",
        case_id="abc",
        workspace=workspace,
        documents=[analysis],
        findings=[high, critical],
        incidents=[incident],
        destruction=workspace["destruction"],
        coverage={
            "scope": "Open analyses",
            "findings": [
                dict(
                    severity="warning",
                    stage="Collecte",
                    path="x",
                    reason="Aucun inventaire de collecte",
                )
            ],
        },
        analyst="Jane",
        graph_png="AAAA",
    )["html"]


def test_a_full_client_report_has_no_sentence_left_in_french():
    translated = english.document(_client_document())
    assert 'lang="en"' in translated
    left = [text for text in _nodes(translated) if FRENCH.search(text)]
    assert not left, left
    assert "CONFIDENTIAL — RESTRICTED TO THE CLIENT" in translated
    assert "Critical, High" in translated, "levels joined in one cell are each translated"


def test_the_destruction_certificate_has_no_sentence_left_in_french(tmp_path):
    case = tmp_path / ("0" * 32)
    case.mkdir()
    (case / "case.json").write_text('{"name": "X", "id": "%s"}' % ("0" * 32))
    (case / "evidence.bin").write_bytes(os.urandom(4000))
    certificate = tmp_path / "certificates" / "pv.html"
    certificate.parent.mkdir()
    destroy_case(
        case,
        "dod3",
        operator="Jane",
        witness="Bob",
        reason="End of contract",
        certificate_path=certificate,
        case_name="X",
        case_id="0" * 32,
        attachments=[],
        extras=[],
    )
    english.rewrite(certificate)
    document = certificate.read_text(encoding="utf-8")
    left = [text for text in _nodes(document) if FRENCH.search(text)]
    assert not left, left
    assert "Evidence destruction certificate" in document and "End of contract" in document


def test_evidence_inside_a_document_is_never_translated():
    """A log line, a file name or a host that happens to read as French is the evidence's own."""
    page = (
        '<html lang="fr"><body><h2>1. Synthèse</h2>'
        "<table><tr><td>Du Pont.docx</td><td>Aucune machine</td><td>Moyen</td></tr></table>"
        "<pre>Généré le Dupont : Aucun accès dans les journaux</pre>"
        "<code>Périmètre</code></body></html>"
    )
    translated = english.document(page)
    assert "<h2>1. Summary</h2>" in translated
    assert "<td>Du Pont.docx</td>" in translated, "a file name is not a sentence"
    assert "<pre>Généré le Dupont : Aucun accès dans les journaux</pre>" in translated
    assert "<code>Périmètre</code>" in translated


def test_a_json_answer_is_translated_value_by_value_and_keys_stay():
    answer = {
        "stage": "Collecte",
        "reason": "Aucun inventaire de collecte",
        "items": ["Contrôle de couverture", 3],
    }
    translated = english.data(answer)
    assert list(translated) == ["stage", "reason", "items"]
    assert translated["reason"] == "No collection inventory"
    assert translated["items"] == ["Coverage check", 3]
