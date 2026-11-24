"""What an analysis is called on screen."""

from fireblade.core.models import analysis_label


def test_label_names_the_evidence_file_not_the_intermediate_csv():
    info = {
        "path": r"C:\work\collecte\var\log\nginx\access.log",
        "label": "var/log/nginx/access.log",
    }
    assert analysis_label(info) == "var/log/nginx/access.log"


def test_label_falls_back_to_the_file_name_for_older_analyses():
    assert (
        analysis_label({"path": r"C:\work\results\Linux - journaux.csv"}) == "Linux - journaux.csv"
    )
    assert analysis_label({}) == ""


def test_label_is_used_by_the_tab_strip():
    from fireblade.core.models import analysis_label

    assert analysis_label({"path": "x.csv", "label": "auth.log"}) == "auth.log"
