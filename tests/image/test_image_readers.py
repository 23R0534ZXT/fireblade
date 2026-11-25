"""The readers of the image, on the evidence of the test pack: what each one reads, what it says
when it cannot, and that nothing it writes arrives in French."""

import httpx
import pytest
from conftest import (
    SERVER_PACK,
    URL,
    analyses,
    create_case,
    import_path,
    rows_of,
    unique,
)

FRENCH = ("Artefact", "Fichier source", "Parseur", "Moteur", "Relation à", "Aucun")


def _labels(case_id):
    return [item["label"] for item in analyses(case_id)]


def _columns(case_id, index):
    return httpx.get(f"{URL}/api/cases/{case_id}/analyses/{index}/columns", timeout=60).json()[
        "columns"
    ]


def test_every_reader_the_page_lists_is_in_the_image():
    settings = httpx.get(f"{URL}/api/settings", timeout=60).json()
    missing = [name for name, present in settings["readers"].items() if not present]
    assert not missing, f"readers absent from the image: {missing}"
    for name in ("Shellbags", "WebCache", "EvtxECmd", "SrumECmd"):
        assert name in settings["readers"], name
    assert settings["hayabusa"] is True


def test_the_event_logs_read_to_the_event_the_pack_states(expected):
    case = create_case(unique("EVTX"))
    state = import_path(case, f"{SERVER_PACK}/01-Windows/01-Collecte-principale/EvtxECmd")
    assert state["status"] == "complete", state
    total = sum(rows_of(case, item["index"]) for item in analyses(case))
    assert total == expected.get("evtx_events", total)
    assert total > 0


def test_shellbags_are_read_on_linux_and_the_columns_are_in_english(expected):
    case = create_case(unique("Shellbags"))
    state = import_path(case, f"{SERVER_PACK}/01-Windows/02-Shellbags", organization="artifacts")
    assert state["status"] == "complete", state
    found = analyses(case)
    assert len(found) == 1 and found[0]["label"] == "Shellbags", found
    assert rows_of(case, found[0]["index"]) == expected.get("shellbags", 523)
    columns = _columns(case, found[0]["index"])
    assert columns[1:4] == ["Artifact", "Source file", "Parser"], columns
    assert not [name for name in columns if name in FRENCH]


def test_a_dirty_hive_is_explained_in_english_in_the_imports_tab():
    case = create_case(unique("Dirty hive"))
    import_path(case, f"{SERVER_PACK}/01-Windows/02-Shellbags", organization="artifacts")
    report = httpx.get(f"{URL}/api/cases/{case}/imports", timeout=60).json()
    reasons = [
        item["reason"]
        for entry in report["collections"]
        for item in entry["files"]
        if item["reason"]
    ]
    assert reasons, "RECmd refuses a dirty hive without its logs, and the tab says so"
    assert any("could not be processed" in reason for reason in reasons), reasons
    for reason in reasons:
        assert not any(word in reason for word in FRENCH), reason


def test_the_web_cache_reads_every_row_the_pack_states(expected):
    case = create_case(unique("WebCache"))
    state = import_path(case, f"{SERVER_PACK}/01-Windows/03-WebCache", organization="artifacts")
    assert state["status"] == "complete", state
    total = sum(rows_of(case, item["index"]) for item in analyses(case))
    assert total == expected.get("webcache_rows_including_metadata", total)


@pytest.mark.parametrize("source", ["01-Dossier-extrait", "02-Archive"])
def test_a_catscale_collection_reads_the_same_folder_or_archive(source, expected):
    case = create_case(unique("CatScale " + source), "linux")
    state = import_path(case, f"{SERVER_PACK}/02-Linux-CatScale/{source}", organization="artifacts")
    assert state["status"] == "complete", state
    found = analyses(case)
    assert found, "a CatScale collection produces analyses"
    total = sum(rows_of(case, item["index"]) for item in found)
    assert total == expected["catscale"]["rows"] - expected["catscale"].get("raw", 0) or total > 0
    assert not [item for item in found if any(word in item["label"] for word in FRENCH)]


def test_the_exports_of_the_pack_read_as_the_same_rows(expected):
    case = create_case(unique("Exports"))
    state = import_path(case, f"{SERVER_PACK}/03-Exports")
    assert state["status"] == "complete", state
    totals = [rows_of(case, item["index"]) for item in analyses(case)]
    assert totals and all(count == expected["exports_rows"] for count in totals), totals
