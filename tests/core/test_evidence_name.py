"""A case written on Windows must read the same in a Linux container."""
from fireblade.core.paths import evidence_name


def test_evidence_name_splits_on_both_separators():
    assert evidence_name(r"C:\work\evidence\Security.evtx") == "Security.evtx"
    assert evidence_name("/data/library/evidence/auth.log") == "auth.log"
    assert evidence_name(r"\\server\share\logs\a.csv") == "a.csv"
    assert evidence_name("plain.csv") == "plain.csv"
    assert evidence_name("") == "" and evidence_name(None) == ""


def test_trailing_separator_does_not_hide_the_name():
    assert evidence_name("C:\\work\\folder\\") == "folder"
