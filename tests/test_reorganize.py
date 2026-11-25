"""The layout select is a view of the case: it lays the imports out again, without reading them again."""

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
