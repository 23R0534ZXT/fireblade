"""The archive has to open with Windows Explorer, which stops at 260 characters."""

from pathlib import Path

from scripts.windows.build_forensic_tools import PATH_LIMIT, shorten_paths

PREFIX = "Fireblade/_internal/resources/"


def test_a_long_rule_path_is_shortened_and_keeps_its_bytes(tmp_path):
    folder = (
        tmp_path
        / "forensic-tools"
        / "Hayabusa"
        / "rules"
        / "sigma"
        / "sysmon"
        / "emerging-threats"
        / "2023"
        / "Exploits"
        / "CVE-2023-34362-MOVEit-Transfer-Exploit"
    )
    folder.mkdir(parents=True)
    name = "proc_creation_win_exploit_cve_2023_34362_moviet_transfer_exploitation_activity.yml"
    rule = folder / name
    rule.write_text("title: MOVEit\n", encoding="utf-8")

    renamed = shorten_paths(tmp_path)

    assert list(renamed) == [rule.relative_to(tmp_path).as_posix()]
    assert not rule.exists()
    survived = tmp_path / renamed[next(iter(renamed))]
    assert survived.read_text(encoding="utf-8") == "title: MOVEit\n"
    assert len(PREFIX) + len(survived.relative_to(tmp_path).as_posix()) <= PATH_LIMIT


def test_a_short_path_is_left_alone(tmp_path):
    rule = (
        tmp_path
        / "forensic-tools"
        / "Hayabusa"
        / "rules"
        / "builtin"
        / "proc_creation_win_dcom.yml"
    )
    rule.parent.mkdir(parents=True)
    rule.write_text("title: DCOM\n", encoding="utf-8")

    assert shorten_paths(tmp_path) == {}
    assert rule.is_file()


def test_two_files_in_the_same_deep_folder_keep_distinct_names(tmp_path):
    folder = tmp_path / "rules" / ("deep-folder-name-" * 5)
    folder.mkdir(parents=True)
    first = folder / ("a" * 90 + ".yml")
    second = folder / ("a" * 89 + "b.yml")
    first.write_text("one\n", encoding="utf-8")
    second.write_text("two\n", encoding="utf-8")

    renamed = shorten_paths(tmp_path)

    assert len(renamed) == 2
    targets = {tmp_path / value for value in renamed.values()}
    assert len(targets) == 2
    assert {path.read_text(encoding="utf-8") for path in targets} == {"one\n", "two\n"}


def test_nothing_above_the_limit_survives(tmp_path):
    folder = tmp_path / ("x" * 120)
    folder.mkdir(parents=True)
    for index in range(5):
        (folder / (("y" * 80) + f"-{index}.yml")).write_text("rule\n", encoding="utf-8")

    shorten_paths(tmp_path)

    for path in tmp_path.rglob("*"):
        if path.is_file():
            relative = path.relative_to(tmp_path).as_posix()
            assert len(PREFIX) + len(relative) <= PATH_LIMIT
