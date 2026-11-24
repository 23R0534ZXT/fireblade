"""Hayabusa rules the analyst can change, without touching the delivered pack."""

import json

from fireblade.core import hayabusa_rules as rules

RULE = """title: Suspicious PowerShell Encoded Command
id: 11111111-2222-3333-4444-555555555555
status: test
level: high
logsource:
    product: windows
    service: powershell
detection:
    selection:
        EventID: 4104
    condition: selection
"""


def pack(tmp_path):
    folder = tmp_path / "pack" / "rules"
    folder.mkdir(parents=True)
    (folder / "ps.yml").write_text(RULE, encoding="utf-8")
    (folder / "cmd.yml").write_text(
        RULE.replace("PowerShell Encoded Command", "Cmd").replace("11111111", "99999999"),
        encoding="utf-8",
    )
    return folder


def test_the_pack_is_read_and_never_written(tmp_path):
    base = tmp_path / "user"
    folder = pack(tmp_path)
    before = (folder / "ps.yml").read_bytes()
    rows = rules.inventory(folder, base)
    assert {row["name"] for row in rows} == {"ps.yml", "cmd.yml"}
    assert all(row["source"] == "pack" and row["enabled"] for row in rows)
    assert rules.read_rule(folder, "ps.yml", base) == RULE
    assert (folder / "ps.yml").read_bytes() == before


def test_an_edited_rule_shadows_the_pack(tmp_path):
    base = tmp_path / "user"
    folder = pack(tmp_path)
    edited = RULE.replace("level: high", "level: critical")
    rules.save_rule(folder, "ps.yml", edited, base)
    rows = {row["name"]: row for row in rules.inventory(folder, base)}
    assert rows["ps.yml"]["source"] == "user"
    assert rules.read_rule(folder, "ps.yml", base) == edited
    assert (folder / "ps.yml").read_text(encoding="utf-8") == RULE, "the pack was modified"


def test_a_rule_missing_what_hayabusa_needs_is_refused(tmp_path):
    base = tmp_path / "user"
    folder = pack(tmp_path)
    for broken in ("", "title: only a title\n", "title: x\nlevel: high\n"):
        try:
            rules.save_rule(folder, "ps.yml", broken, base)
        except ValueError as exc:
            assert "incomplète" in str(exc) or "vide" in str(exc), exc
        else:
            raise AssertionError("a broken rule was accepted: " + repr(broken))


def test_disabling_a_rule_keeps_the_file_and_stops_it_loading(tmp_path):
    base = tmp_path / "user"
    folder = pack(tmp_path)
    rules.set_enabled("ps.yml", False, base)
    rows = {row["name"]: row for row in rules.inventory(folder, base)}
    assert rows["ps.yml"]["enabled"] is False
    assert (folder / "ps.yml").is_file(), "the pack rule was deleted"
    target = tmp_path / "effective"
    receipt = rules.effective_rules(folder, target, base)
    assert receipt["skipped"] == 1
    assert not (target / "ps.yml").exists()
    assert (target / "cmd.yml").is_file()


def test_the_effective_folder_carries_overrides_and_the_rest_of_the_pack(tmp_path):
    base = tmp_path / "user"
    folder = pack(tmp_path)
    rules.save_rule(folder, "ps.yml", RULE.replace("level: high", "level: critical"), base)
    target = tmp_path / "effective"
    receipt = rules.effective_rules(folder, target, base)
    assert receipt["overrides"] == 1
    text = (target / "ps.yml").read_text(encoding="utf-8")
    assert "critical" in text
    assert "cmd.yml" in {path.name for path in target.iterdir()}


def test_resetting_a_rule_gives_the_pack_rule_back(tmp_path):
    base = tmp_path / "user"
    folder = pack(tmp_path)
    rules.save_rule(folder, "ps.yml", RULE.replace("level: high", "level: critical"), base)
    assert rules.reset_rule("ps.yml", base) is True
    assert rules.read_rule(folder, "ps.yml", base) == RULE
    assert rules.reset_rule("ps.yml", base) is False


def test_changes_are_detected_only_when_there_are_some(tmp_path):
    base = tmp_path / "user"
    assert rules.has_changes(base) is False
    rules.set_enabled("ps.yml", False, base)
    assert rules.has_changes(base) is True
    json.loads(rules.state_path(base).read_text(encoding="utf-8"))
