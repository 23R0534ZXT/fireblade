"""Workspace modes: the same chrome, the panels come back, nothing leaks between modes."""

import time

import pytest
from PySide6.QtWidgets import QDockWidget

from fireblade.ui.app import Window

from test_modular_workspace import add_case, settle


def bars(window):
    return [window.main_toolbar, window.collection_toolbar, window.workspace_layout.toolbar]


def visible_bars(window):
    return sorted(bar.objectName() for bar in bars(window) if not bar.isHidden())


def actions(window):
    seen = []
    for bar in bars(window):
        for action in bar.actions():
            if action.isSeparator():
                continue
            seen.append((bar.objectName(), action.text().replace("&", "")))
    return sorted(seen)


def docks(window):
    return sorted(
        (dock.objectName(), not dock.isHidden()) for dock in window.findChildren(QDockWidget)
    )


def wait_visible(app, widget, want=True, timeout=10):
    """Visibility settles a turn later: assert the intent, not the first frame."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if widget.isVisible() == want:
            return True
        time.sleep(0.005)
    return False


def test_every_mode_keeps_the_same_buttons_on_the_top_bars(qt_application, tmp_path):
    window = Window(require_case=False)
    window.show()
    try:
        add_case(window, tmp_path, "modes")
        settle(qt_application, window)
        layout = window.workspace_layout
        layout.analysis()
        bars_before, actions_before = visible_bars(window), actions(window)
        assert bars_before, "les barres du haut doivent être là"
        for mode in (layout.timeline, layout.side_by_side, layout.analysis):
            mode()
            settle(qt_application, window)
            assert visible_bars(window) == bars_before, mode.__name__
            assert actions(window) == actions_before, mode.__name__
    finally:
        window.close()


def test_timeline_only_hides_the_panels_and_gives_them_back(qt_application, tmp_path):
    window = Window(require_case=False)
    window.show()
    try:
        add_case(window, tmp_path, "panels")
        settle(qt_application, window)
        layout = window.workspace_layout
        # A dock only exists once a panel is taken out of the splitter: without one
        # this test would pass while proving nothing.
        layout.detach_auxiliary("details", window.details, window.splitter)
        dock = window.findChild(QDockWidget, "workspace-details")
        assert dock is not None
        layout.analysis()
        assert wait_visible(qt_application, dock), "le panneau doit être visible en Analyse"

        layout.timeline()
        assert wait_visible(qt_application, dock, want=False), "les panneaux doivent être masqués"
        assert not window.workbench.tabBar().isHidden(), (
            "les onglets restent : c'est le chemin du retour"
        )

        layout.analysis()
        assert wait_visible(qt_application, dock), "les panneaux doivent revenir"
        assert not window.workbench.tabBar().isHidden()
    finally:
        window.close()


def test_entering_timeline_only_twice_is_stable(qt_application, tmp_path):
    window = Window(require_case=False)
    window.show()
    try:
        add_case(window, tmp_path, "twice")
        settle(qt_application, window)
        layout = window.workspace_layout
        layout.analysis()
        bars_before = visible_bars(window)
        layout.timeline()
        first = docks(window)
        layout.timeline()
        assert docks(window) == first
        assert visible_bars(window) == bars_before
        layout.analysis()
        assert not any(hidden for _name, hidden in docks(window))
    finally:
        window.close()


def test_side_by_side_then_analysis_brings_the_timeline_back_as_a_tab(qt_application, tmp_path):
    window = Window(require_case=False)
    window.show()
    try:
        add_case(window, tmp_path, "docked")
        settle(qt_application, window)
        layout = window.workspace_layout
        layout.side_by_side()
        assert window.timeline_tab_index in window.workbench.panels
        layout.analysis()
        assert window.timeline_tab_index not in window.workbench.panels, (
            "l'analyse seule ne garde pas de panneau détaché"
        )
    finally:
        window.close()


def test_reset_brings_back_everything_from_any_mode(qt_application, tmp_path):
    window = Window(require_case=False)
    window.show()
    try:
        add_case(window, tmp_path, "reset")
        settle(qt_application, window)
        layout = window.workspace_layout
        for mode in (layout.timeline, layout.side_by_side):
            mode()
            layout.reset()
            settle(qt_application, window)
            assert not any(hidden for _name, hidden in docks(window))
            assert not window.workbench.tabBar().isHidden()
            assert len(visible_bars(window)) == len(bars(window))
    finally:
        window.close()


def test_saving_a_focused_workspace_keeps_the_mode_and_leaves_nothing_hidden(
    qt_application, tmp_path
):
    window = Window(require_case=False)
    window.show()
    try:
        add_case(window, tmp_path, "save")
        settle(qt_application, window)
        layout = window.workspace_layout
        layout.analysis()
        bars_before = visible_bars(window)
        layout.timeline()
        layout.save()
        assert layout.focused, "enregistrer ne doit pas sortir du mode"
        assert visible_bars(window) == bars_before
        assert all(hidden for _name, hidden in docks(window))
        layout.analysis()
        assert not any(hidden for _name, hidden in docks(window))
    finally:
        window.close()


def test_timeline_only_keeps_every_tab_visible(qt_application, tmp_path):
    """Reports came in as "les onglets disparaissent": the strip is the way back."""
    window = Window(require_case=False)
    window.show()
    try:
        add_case(window, tmp_path, "tabs")
        settle(qt_application, window)
        layout = window.workspace_layout
        layout.analysis()
        titles = [window.workbench.tabText(index) for index in range(window.workbench.count())]
        assert window.workbench.tabBar().isVisible()
        layout.timeline()
        assert window.workbench.tabBar().isVisible()
        assert [
            window.workbench.tabText(index) for index in range(window.workbench.count())
        ] == titles
        # Using a tab leaves the mode, so the window is never left half stripped.
        window.workbench.setCurrentIndex(0)
        assert not layout.focused
        layout.analysis()
        assert [
            window.workbench.tabText(index) for index in range(window.workbench.count())
        ] == titles
    finally:
        window.close()
