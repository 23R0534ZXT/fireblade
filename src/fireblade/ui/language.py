"""Apply the chosen language to the menu bar and the main toolbar.

The French label is kept on each action as `source_text`; every language change
translates from that source, so switching back and forth never drifts.
"""
from fireblade.core.i18n import translate

SOURCE = "source_text"


def source_text(action):
    """The French label the code was written with, whatever is displayed now."""
    return action.property(SOURCE) or action.text()


def apply_to_action(action):
    if action.isSeparator():
        return
    source = action.property(SOURCE)
    if source is None:
        source = action.text()
        action.setProperty(SOURCE, source)
    if not source:
        return
    action.setText(translate(source))


def apply_to_menu(menu):
    for action in menu.actions():
        apply_to_action(action)
        if action.menu() is not None:
            apply_to_menu(action.menu())


def apply_language(window):
    """Idempotent: safe to call before the menus exist or many times in a row."""
    bar = getattr(window, "menuBar", None)
    if bar is not None:
        menu_bar = bar()
        for action in menu_bar.actions():
            apply_to_action(action)
            if action.menu() is not None:
                apply_to_menu(action.menu())
    toolbar = getattr(window, "main_toolbar", None)
    if toolbar is not None:
        for action in toolbar.actions():
            apply_to_action(action)
