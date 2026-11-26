from fireblade.core import hayabusa_rules


def test_the_engines_field_mapping_files_are_not_listed_as_detection_rules(tmp_path):
    pack = tmp_path / "rules"
    (pack / "config" / "data_mapping").mkdir(parents=True)
    (pack / "sigma").mkdir()
    (pack / "config" / "data_mapping" / "Logon.yaml").write_text("title: Logon\n", encoding="utf-8")
    (pack / "sigma" / "ps.yml").write_text(
        "title: PowerShell\nlevel: high\nstatus: stable\n", encoding="utf-8"
    )
    names = [item["name"] for item in hayabusa_rules.inventory(pack, tmp_path / "base")]
    assert names == ["ps.yml"]
    # they still travel with the rules the engine runs
    assert {path.name for path in hayabusa_rules.rule_files(pack)} == {"Logon.yaml", "ps.yml"}
