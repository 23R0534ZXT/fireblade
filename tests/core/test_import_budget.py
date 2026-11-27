"""A big table must not be imported five times before it fits."""

from fireblade.core.collection import fit_budget_to_file
from fireblade.core.settings import Settings


def make_file(tmp_path, megabytes):
    path = tmp_path / "big.csv"
    with path.open("wb") as handle:
        handle.truncate(megabytes * 1024 * 1024)
    return path


def test_the_first_attempt_has_room_for_the_file(tmp_path):
    path = make_file(tmp_path, 300)
    raised = fit_budget_to_file(Settings(memory_mb=128), path, ceiling_mb=8192)
    assert raised.memory_mb == 300 + 75 + 64


def test_a_small_file_keeps_the_configured_budget(tmp_path):
    path = make_file(tmp_path, 20)
    assert fit_budget_to_file(Settings(memory_mb=1024), path, ceiling_mb=8192).memory_mb == 1024


def test_the_budget_stops_at_the_machine_ceiling(tmp_path):
    path = make_file(tmp_path, 400)
    assert fit_budget_to_file(Settings(memory_mb=128), path, ceiling_mb=300).memory_mb == 300


def test_a_missing_file_keeps_the_budget(tmp_path):
    budget = Settings(memory_mb=128)
    assert fit_budget_to_file(budget, tmp_path / "absent.csv").memory_mb == 128


def test_a_multi_gigabyte_file_keeps_the_budget_that_enables_streaming(tmp_path):
    from fireblade.core.engine import Case

    path = make_file(tmp_path, 3000)
    configured = Settings(memory_mb=512)
    effective = fit_budget_to_file(configured, path, ceiling_mb=8192)
    engine = Case.__new__(Case)
    engine.settings = effective
    assert path.stat().st_size > engine.single_pass_limit()
    assert effective.memory_mb == configured.memory_mb
