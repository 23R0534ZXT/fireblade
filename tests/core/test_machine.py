"""The effort levels must fit the machine they describe, not a fixed table."""

from fireblade.core.machine import LEVELS, describe, effort, from_settings, tone_for


def test_levels_grow_with_the_machine():
    small = [effort(level, cpu=4, ram=4096) for level in LEVELS]
    large = [effort(level, cpu=32, ram=65536) for level in LEVELS]
    for series in (small, large):
        threads = [item.threads for item in series]
        memories = [item.memory_mb for item in series]
        assert threads == sorted(threads) and memories == sorted(memories)
    assert small[1].threads < large[1].threads
    assert small[1].memory_mb < large[1].memory_mb


def test_no_level_takes_more_than_the_machine_has():
    for cpu, ram in ((1, 1024), (4, 4096), (64, 131072)):
        for level in LEVELS:
            item = effort(level, cpu=cpu, ram=ram)
            assert 1 <= item.threads <= cpu
            assert item.memory_mb <= ram
            assert 0 < item.share <= 1.0


def test_light_stays_green_and_maximum_says_red():
    assert effort("light", cpu=8, ram=16384).tone == "green"
    assert effort("maximum", cpu=8, ram=16384).tone == "red"
    assert tone_for(0.44) == "green" and tone_for(0.5) == "amber" and tone_for(0.9) == "red"


def test_the_line_is_readable_without_a_manual():
    line = describe(effort("balanced", cpu=16, ram=32768), ram=32768)
    assert "threads" in line and "GB of" in line and "32.0 GB" in line


def test_a_hand_edited_choice_is_described_the_same_way():
    item = from_settings(30, 20000, cpu=16, ram=32768)
    assert item.threads == 16, "jamais plus de threads que de cœurs"
    assert item.memory_mb == 20000, "une valeur explicite sous la RAM est respectée"
    assert item.tone in ("green", "amber", "red")
