"""Adding data requires a case: the entry points stay greyed out until one exists."""
import pytest


@pytest.fixture
def window(qt_application):
    from fireblade.ui.app import Window
    widget = Window(require_case=True)   # the real application path
    yield widget
    widget.close()


def test_parse_and_analyze_are_greyed_without_a_case(window):
    actions = window.data_actions
    assert len(actions) >= 2
    assert all(not action.isEnabled() for action in actions)
    assert all("case" in action.toolTip().lower() for action in actions)


def test_the_entry_points_reopen_once_a_case_exists(window, monkeypatch):
    monkeypatch.setattr(window, "active_investigation", {"id": "0" * 32})
    try:
        window.update_case_gate()
        assert all(action.isEnabled() for action in window.data_actions)
        assert all("case" not in action.toolTip().lower() for action in window.data_actions)
    finally:
        monkeypatch.setattr(window, "active_investigation", None)


def test_the_backstop_still_refuses_without_a_case(window, monkeypatch):
    """Even if a stray path reaches the handler, it must not start without a case."""
    from fireblade.ui.start_workflow import StartWorkflowMixin
    seen = {}
    monkeypatch.setattr(window, "show_investigations", lambda: seen.setdefault("shown", True))
    monkeypatch.setattr(window, "active_investigation", None)
    assert window.require_active_case() is False
    assert seen.get("shown") is True
