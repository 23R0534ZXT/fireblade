"""The layout select is a view of the case: it lays the imports out again, without reading them again."""

import pytest

from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library


def test_a_case_is_laid_out_per_file_per_artifact_and_as_one_grid_and_back(tmp_path):
    folder = tmp_path / "logs"
    folder.mkdir()
    (folder / "a.csv").write_text("Time,User\n2026-11-01T10:00:00Z,alice\n")
    (folder / "b.csv").write_text(
        "Time,User\n2026-11-02T10:00:00Z,bob\n2026-11-03T10:00:00Z,carol\n"
    )
    (folder / "auth.log").write_text(
        "Nov  1 10:00:01 srv sshd[1]: Failed password for root from 10.0.0.9 port 22 ssh2\n"
    )
    root = tmp_path / "cases"
    root.mkdir()
    library = Library(root)
    identifier = InvestigationLibrary(root).create("Layouts", "", "linux")["id"]
    library.import_source(identifier, folder, organization="files")

    def grids():
        analyses = library.case(identifier)["analyses"]
        return len(analyses), sum(
            library.rows(identifier, item["index"], limit=1)["total"] for item in analyses
        )

    per_file = grids()
    assert per_file[0] == 3 and per_file[1] == 4
    assert library.reorganize(identifier, "combined")["collections"] == 1
    assert grids()[0] == 1, "one grid for everything"
    assert grids()[1] == 4, "and not a row lost"
    assert library.reorganize(identifier, "artifacts")["collections"] == 1
    assert 1 < grids()[0] < 3 + 1 and grids()[1] == 4
    assert library.reorganize(identifier, "files")["collections"] == 1
    assert grids() == per_file
    assert library.reorganize(identifier, "files")["collections"] == 0, "already that way"
    library.close()


@pytest.mark.parametrize("column_threshold", [3000, 1])
def test_annotations_follow_the_source_record_across_all_layouts(
    tmp_path, monkeypatch, column_threshold
):
    from fireblade.core import collection_organization
    from fireblade.core.models import Filter, View

    monkeypatch.setattr(collection_organization, "MAX_COLUMNS", column_threshold)
    source = tmp_path / "sources"
    source.mkdir()
    (source / "a.csv").write_text("User,ID\nalice,001\nbob,002\n")
    (source / "b.csv").write_text("User,ID\ncarol,003\n")
    root = tmp_path / "cases"
    root.mkdir()
    identifier = InvestigationLibrary(root).create("Notes across layouts", "", "windows")["id"]
    library = Library(root)
    try:
        library.import_source(identifier, source, organization="files")

        def chosen():
            for item in library.case(identifier)["analyses"]:
                case = library._case_for(identifier, item["index"])
                column = case.headers.index("ID")
                rows = case.page(View(filters=[Filter(column, "eq", "002")]))
                if rows:
                    return case, rows[0][0], column
            pytest.fail("The source record disappeared")

        case, row_id, column = chosen()
        case.bookmark(row_id, "Review Bob")
        case.bookmark(row_id, "Keep leading zeroes", column)
        for step, mode in enumerate(("combined", "artifacts", "files", "combined")):
            library.reorganize(identifier, mode)
            case, row_id, column = chosen()
            assert case.bookmarks()[row_id] == "Review Bob", mode
            assert case.cell_notes([row_id])[row_id, column] == "Keep leading zeroes", mode
            if mode == "combined":
                metadata = case.headers.index("Artefact")
                if step:
                    assert case.cell_notes([row_id])[row_id, metadata] == "Provenance reviewed"
                    if case.sparse:
                        assert case.cell_notes([row_id])[row_id, 3] == "Time reviewed"
                else:
                    case.bookmark(row_id, "Provenance reviewed", metadata)
                    if case.sparse:
                        case.bookmark(row_id, "Time reviewed", 3)
            elif mode == "artifacts":
                metadata = case.headers.index("Artefact")
                assert case.cell_notes([row_id])[row_id, metadata] == "Provenance reviewed"
        assert (
            case.cell_notes([row_id])[row_id, case.headers.index("Artefact")]
            == "Provenance reviewed"
        )
        case.bookmark(row_id, None)
        case.bookmark(row_id, None, column)
        for mode in ("files", "combined"):
            library.reorganize(identifier, mode)
            case, row_id, column = chosen()
            assert row_id not in case.bookmarks(), "a removed annotation must not return"
            assert (row_id, column) not in case.cell_notes([row_id])
    finally:
        library.close()
