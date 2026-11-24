"""The navigation tree names the evidence, not the folder it was saved under."""

from types import SimpleNamespace

from fireblade.ui.navigation import AnalysisNavigator

ROOT = r"C:\Users\OCD\Desktop\Malware\OCD_artefacts_collection-MagnetRESPONSE-2025.06.02_16.25.52\FORENSIC_LAB_OCD_2025.06.02_16.25.52\Saved_Files"


def snapshot(tmp_path, name, source):
    return SimpleNamespace(path=str(tmp_path / name), source_info={"path": source})


def test_a_narrow_tree_still_says_what_each_source_is(qt_application, tmp_path):
    documents = [
        snapshot(
            tmp_path,
            "a.timeline",
            ROOT + r"\Windows_Event_Logs\C\Windows\System32\winevt\Logs\Security.evtx",
        ),
        snapshot(
            tmp_path,
            "b.timeline",
            ROOT + r"\Windows_Event_Logs\C\Windows\System32\winevt\Logs\System.evtx",
        ),
        snapshot(
            tmp_path, "c.timeline", ROOT + r"\Amcache\C\Windows\AppCompat\Programs\Amcache.hve"
        ),
    ]
    collections = [
        {"path": str(tmp_path / "collecte"), "name": "Dossier : " + ROOT + r"\Windows_Event_Logs"}
    ]
    navigator = AnalysisNavigator()
    try:
        navigator.refresh(documents, 0, collections, grouping="families")
        texts = [item.text(0) for item in navigator.items()]
        # The collection and the two channels are readable without widening the panel.
        assert "Event logs" in texts
        assert "Event logs · Security" in texts and "Event logs · System" in texts
        assert "Amcache" in texts
        # Nothing shows the long saved-files path as its label.
        assert not any(text.startswith("C:") or "Saved_Files" in text for text in texts)
        # The path is not lost, it moved to the tooltip.
        tips = [item.toolTip(0) for item in navigator.items()]
        assert any("Security.evtx" in tip for tip in tips)
    finally:
        navigator.deleteLater()


def test_a_collection_recorded_with_its_path_is_shown_short(qt_application, tmp_path):
    navigator = AnalysisNavigator()
    try:
        navigator.refresh(
            [],
            0,
            [{"path": str(tmp_path / "col"), "name": "Dossier : " + ROOT + r"\Browser_History"}],
            grouping="families",
        )
        assert [item.text(0) for item in navigator.items()] == ["Browser history"]
    finally:
        navigator.deleteLater()
