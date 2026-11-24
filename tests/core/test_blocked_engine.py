"""An engine blocked by Windows must stop the collection, not wait an hour."""

from pathlib import Path

from fireblade.core.collection import blocked_by_windows


def test_a_log_naming_the_application_control_block_is_recognised(tmp_path):
    log = tmp_path / "parser.log"
    log.write_text(
        "Error loading plugin: C:\\Tools\\RECmd\\Plugins\\RegistryPlugin.ETW.dll\n"
        "System.IO.FileLoadException: Une stratégie de contrôle d'application a bloqué ce fichier. (0x800711C7)\n",
        encoding="utf-8",
    )
    assert blocked_by_windows(log) is True


def test_a_normal_engine_log_is_not_mistaken_for_a_block(tmp_path):
    log = tmp_path / "parser.log"
    log.write_text("Processed 12 records in 0.4 s\nErrors: 0\n", encoding="utf-8")
    assert blocked_by_windows(log) is False


def test_a_missing_log_is_not_a_block(tmp_path):
    assert blocked_by_windows(Path(tmp_path) / "absent.log") is False
