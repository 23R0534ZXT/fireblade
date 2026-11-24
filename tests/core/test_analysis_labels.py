"""Tab labels stay unique when several analyses share a name."""

from fireblade.core.models import AnalysisSnapshot, View, analysis_label, analysis_tab_labels


def document(path, label=None):
    """One open analysis, built the way the workspace builds it."""
    info = {"path": path}
    if label is not None:
        info["label"] = label
    return AnalysisSnapshot(
        path=path + ".timeline", source_info=info, view=View(), header_state=b""
    )


def test_unique_labels_are_left_untouched():
    documents = [
        document(r"C:\cases\one\access.log"),
        document(r"C:\cases\two\auth.log"),
        document(r"C:\cases\three\collecte\var\log\zeek.log"),
    ]
    assert analysis_tab_labels(documents) == [analysis_label(d.source_info) for d in documents]


def test_a_recorded_label_is_left_untouched_when_unique():
    documents = [document(r"C:\cases\one\intermediate.csv", "var/log/nginx/access.log")]
    assert analysis_tab_labels(documents) == ["var/log/nginx/access.log"]


def test_two_same_names_in_different_folders_get_different_suffixes():
    documents = [
        document(r"C:\cases\one\nginx\access.log", "access.log"),
        document(r"C:\cases\two\nginx\access.log", "access.log"),
    ]
    labels = analysis_tab_labels(documents)
    assert labels == ["access.log \u00b7 one/nginx", "access.log \u00b7 two/nginx"]
    assert labels[0] != labels[1]


def test_three_nested_same_names_get_distinct_readable_suffixes():
    documents = [
        document(r"C:\cases\red\config\active.txt", "active.txt"),
        document(r"C:\cases\blue\System32\config\active.txt", "active.txt"),
        document(r"C:\cases\green\deep\System32\config\active.txt", "active.txt"),
    ]
    labels = analysis_tab_labels(documents)
    assert labels == [
        "active.txt \u00b7 red/config",
        "active.txt \u00b7 blue/System32/config",
        "active.txt \u00b7 deep/System32/config",
    ]
    assert len(set(labels)) == 3
    assert all(label.startswith("active.txt \u00b7 ") for label in labels)
    assert all(chr(92) not in label for label in labels)


def test_the_same_path_twice_falls_back_to_a_rank():
    documents = [
        document(r"C:\cases\sql\CarsDB.db", "CarsDB.db"),
        document(r"C:\cases\sql\CarsDB.db", "CarsDB.db"),
        document(r"C:\cases\sql\CarsDB.db", "CarsDB.db"),
    ]
    labels = analysis_tab_labels(documents)
    assert labels == ["CarsDB.db", "CarsDB.db (2)", "CarsDB.db (3)"]


def test_a_rank_and_a_suffix_can_be_combined():
    documents = [
        document(r"C:\cases\one\CarsDB.db", "CarsDB.db"),
        document(r"C:\cases\one\CarsDB.db", "CarsDB.db"),
        document(r"C:\cases\two\CarsDB.db", "CarsDB.db"),
    ]
    labels = analysis_tab_labels(documents)
    assert labels == ["CarsDB.db \u00b7 one", "CarsDB.db \u00b7 one (2)", "CarsDB.db \u00b7 two"]
    assert len(set(labels)) == 3


def test_the_same_name_in_different_folders_is_not_confused_with_a_rank():
    documents = [
        document(r"C:\cases\one\CarsDB.db", "CarsDB.db"),
        document(r"C:\cases\two\CarsDB.db", "CarsDB.db"),
        document(r"C:\cases\three\CarsDB.db", "CarsDB.db"),
    ]
    labels = analysis_tab_labels(documents)
    assert labels == ["CarsDB.db \u00b7 one", "CarsDB.db \u00b7 two", "CarsDB.db \u00b7 three"]
    assert all("(" not in label for label in labels)


def test_an_empty_label_does_not_crash_and_stays_distinct():
    assert analysis_tab_labels([document(""), document(""), document("")]) == ["", "(2)", "(3)"]
    assert analysis_tab_labels(
        [AnalysisSnapshot(path="empty.timeline", source_info={}, view=View(), header_state=b"")]
    ) == [""]
    assert analysis_tab_labels([]) == []


def test_both_separators_are_understood():
    documents = [
        document(r"C:\cases\one\access.log", "access.log"),
        document("C:/cases/two/access.log", "access.log"),
    ]
    labels = analysis_tab_labels(documents)
    assert labels == ["access.log \u00b7 one", "access.log \u00b7 two"]
    assert all(chr(92) not in label for label in labels)
