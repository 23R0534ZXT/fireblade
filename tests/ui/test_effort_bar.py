"""The effort control: one slider, a bar that grows and reddens, one saved choice."""
from fireblade.core.machine import LEVELS, effort


def test_the_slider_moves_through_the_levels(qt_application):
    from fireblade.ui.effort_bar import EffortBar
    bar = EffortBar('light')
    seen = []
    bar.chosen.connect(seen.append)
    bar.slider.setValue(3)
    assert seen == ['maximum']
    assert bar.level == 'maximum'
    assert 'Maximum' in bar.text.text()


def test_the_bar_grows_and_turns_red_when_the_machine_will_feel_it(qt_application):
    from fireblade.ui.effort_bar import COLOURS, EffortBar
    bar = EffortBar('light')
    widths, colours = [], []
    for index, level in enumerate(LEVELS):
        bar.slider.setValue(index)
        widths.append(bar.bar.width())
        colours.append(bar.bar.styleSheet())
        assert COLOURS[effort(level).tone] in colours[-1], 'la couleur suit la charge'
    assert widths == sorted(widths), 'la barre grandit avec l’effort'
    assert COLOURS['red'] in colours[-1]


def test_choosing_a_level_saves_it_and_moves_the_budget(qt_application, tmp_path, monkeypatch):
    import fireblade.core.preferences as preferences_module
    from fireblade.core.preferences import Preferences
    saved = []
    monkeypatch.setattr(preferences_module, 'save_preferences', lambda item: saved.append(item))
    from fireblade.ui.app import Window
    window = Window(require_case=False)
    window.preferences = Preferences()
    try:
        window.set_effort('fast')
        item = effort('fast')
        assert saved and saved[-1].effort_level == 'fast'
        assert saved[-1].parsing_threads == item.threads
        assert saved[-1].resource_memory_mb == item.memory_mb
        assert window.settings.threads == item.threads
        assert window.settings.memory_mb == item.memory_mb
    finally:
        window.close()
