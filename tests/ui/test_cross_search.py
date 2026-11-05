"""Cross-document search must report counts and a few real matching rows."""
import csv

from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.ui.cross_search import WorkspaceSearch, summarize


def make_case(tmp_path, name, rows):
    source = tmp_path / f"{name}.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "User", "Command"])
        writer.writerows(rows)
    case = Case(tmp_path / f"{name}.timeline")
    case.import_csv(source)
    document = AnalysisSnapshot(str(case.path), case.info, View(), b"")
    return case, document


def test_search_returns_a_count_and_sample_rows(tmp_path):
    case, document = make_case(tmp_path, "a", [
        ["2026-01-01T00:00:00Z", "alice", "powershell -enc AAA"],
        ["2026-01-01T00:00:01Z", "bob", "cmd /c whoami"],
        ["2026-01-01T00:00:02Z", "alice", "powershell -w hidden"],
    ])
    try:
        hits = WorkspaceSearch([document], case.settings, active=case).find("powershell")
        assert len(hits) == 1
        assert hits[0].count == 2
        assert len(hits[0].sample) == 2
        assert all("powershell" in line for line in hits[0].sample)
    finally:
        case.close()


def test_search_without_matches_returns_an_empty_sample(tmp_path):
    case, document = make_case(tmp_path, "b", [["2026-01-01T00:00:00Z", "alice", "cmd"]])
    try:
        hits = WorkspaceSearch([document], case.settings, active=case).find("powershell")
        assert hits[0].count == 0
        assert hits[0].sample == []
    finally:
        case.close()


def test_every_open_artifact_is_searched(tmp_path):
    first, first_document = make_case(tmp_path, "c", [["2026-01-01T00:00:00Z", "alice", "powershell"]])
    second, second_document = make_case(tmp_path, "d", [["2026-01-01T00:00:00Z", "bob", "powershell"]])
    # Inactive analyses are closed, as in the application: the search reopens them
    # read-only, which DuckDB refuses while the writer connection is still open.
    second.close()
    try:
        hits = WorkspaceSearch([first_document, second_document], first.settings, active=first).find("powershell")
        assert [hit.count for hit in hits] == [1, 1]
        assert [hit.name for hit in hits] == ["c.csv", "d.csv"]
    finally:
        first.close()


def test_summarize_skips_empty_values_and_truncates():
    assert summarize((1, "a", None, "", "b"), limit=40) == "a · b"
    assert summarize((1, "x" * 300), limit=160) == "x" * 160


def test_the_panel_text_shows_a_sample_and_the_remaining_count():
    from fireblade.ui.cross_search import SearchHit, sample_text

    hit = SearchHit("p", "x.csv", 12, sample=["a", "b"])
    text = sample_text(hit)
    assert "• a" in text and "• b" in text
    assert "10" in text
    assert sample_text(SearchHit("p", "x.csv", 0)) == "Aucune correspondance dans cet artefact."
    assert sample_text(SearchHit("p", "x.csv", None, error="fichier illisible")) == "fichier illisible"
