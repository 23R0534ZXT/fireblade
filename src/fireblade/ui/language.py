"""Apply the chosen language to the menu bar and the main toolbar.

The French label is kept on each action as `source_text`; every language change
translates from that source, so switching back and forth never drifts.
"""
from PySide6.QtWidgets import (QCheckBox, QGroupBox, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QRadioButton, QTabBar, QToolBar, QToolButton,
                               QWidget)

from fireblade.core.i18n import translate

SOURCE = "source_text"
TABS = "source_tabs"
PLACEHOLDER = "source_placeholder"
WIDGETS = (QLabel, QPushButton, QCheckBox, QRadioButton, QGroupBox, QToolButton)
PLACEHOLDERS = (QLineEdit, QPlainTextEdit)


def apply_to_widget(widget):
    """Buttons, labels, titles: same table, same idempotence."""
    source = widget.property(SOURCE)
    if source is None:
        source = widget.text()
        widget.setProperty(SOURCE, source)
    if not source:
        return
    widget.setText(translate(source))


def apply_to_placeholder(widget):
    source = widget.property(PLACEHOLDER)
    if source is None:
        source = widget.placeholderText()
        widget.setProperty(PLACEHOLDER, source)
    if source:
        widget.setPlaceholderText(translate(source))


def apply_to_tabbar(bar):
    sources = bar.property(TABS)
    if sources is None or len(sources) != bar.count():
        sources = [bar.tabText(index) for index in range(bar.count())]
        bar.setProperty(TABS, sources)
    for index, source in enumerate(sources):
        # A lone & is a mnemonic in a tab title; escaping prints it.
        bar.setTabText(index, translate(source).replace('&', '&&'))


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
    for bar in window.findChildren(QToolBar):
        for action in bar.actions():
            apply_to_action(action)
    for widget in window.findChildren(QWidget):
        if isinstance(widget, WIDGETS):
            apply_to_widget(widget)
        elif isinstance(widget, PLACEHOLDERS):
            apply_to_placeholder(widget)
    for bar in window.findChildren(QTabBar):
        apply_to_tabbar(bar)
