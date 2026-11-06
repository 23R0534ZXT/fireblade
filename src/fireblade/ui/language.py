"""Apply the chosen language anywhere in the interface.

The French label is kept on each widget as `source_text` (and as `source_tabs`,
`source_placeholder`, `source_items`, `source_headers`, `source_title`); every
language change translates from that source, so switching back and forth never
drifts.

A widget whose text was replaced by the code since the last pass — a counter, a
file name, an error — refreshes its source from what is on screen. Without that
guard a language switch would restore a stale label.

`translate_tree` handles a whole subtree, so a dialog built anywhere gets the
same treatment as the main window, and `install(app)` makes the application
translate every window the moment it appears.
"""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QMenuBar,
                               QPlainTextEdit, QPushButton, QRadioButton, QStatusBar,
                               QTableWidget, QTableWidgetItem, QTabBar, QTextEdit,
                               QToolBar, QToolButton, QTreeWidget, QTreeWidgetItem,
                               QWidget)

from fireblade.core.i18n import SOURCE_LANGUAGE, current_language, english, translate

SOURCE = "source_text"
TABS = "source_tabs"
PLACEHOLDER = "source_placeholder"
ITEMS = "source_items"
HEADERS = "source_headers"
TITLE = "source_title"
TOOLTIP = "source_tooltip"
WIDGETS = (QLabel, QPushButton, QCheckBox, QRadioButton, QGroupBox, QToolButton)
PLACEHOLDERS = (QLineEdit, QPlainTextEdit, QTextEdit)
FILTER = "_fireblade_language_filter"


def source_of(widget, key, current):
    """Recorded source of a widget, refreshed when the code replaced the text.

    The comparison uses the English form, not the displayed one: in French the
    translation is the identity, so a label we translated ourselves would look
    like a text the code replaced, and switching back would keep the English.
    """
    stored = widget.property(key)
    if stored is None or (current != stored and current != english(stored)):
        widget.setProperty(key, current)
        return current
    return stored


def text_of(widget):
    """A group box carries its label in `title`, every other widget in `text`."""
    return widget.title() if isinstance(widget, QGroupBox) else widget.text()


def set_text_of(widget, text):
    if isinstance(widget, QGroupBox):
        widget.setTitle(text)
    else:
        widget.setText(text)


def apply_to_widget(widget):
    """Buttons, labels, group titles: same table, same idempotence."""
    current = text_of(widget)
    source = source_of(widget, SOURCE, current)
    displayed = translate(source) if source else source
    if displayed != current:
        set_text_of(widget, displayed)


def apply_to_placeholder(widget):
    current = widget.placeholderText()
    source = source_of(widget, PLACEHOLDER, current)
    displayed = translate(source) if source else source
    if displayed != current:
        widget.setPlaceholderText(displayed)


def apply_to_tooltip(widget):
    current = widget.toolTip()
    if not current:
        return
    displayed = translate(source_of(widget, TOOLTIP, current))
    if displayed != current:
        widget.setToolTip(displayed)


def apply_to_title(widget):
    current = widget.windowTitle()
    if not current:
        return
    displayed = translate(source_of(widget, TITLE, current))
    if displayed != current:
        widget.setWindowTitle(displayed)


def escaped(text):
    """A lone & is a mnemonic in a tab title; doubling it prints it."""
    return text.replace('&', '&&')


def unescaped(text):
    return text.replace('&&', '&')


def apply_to_tabbar(bar):
    """Tab titles, with the ampersand escaping kept out of the recorded source.

    Reading the displayed text back and escaping it again on the next pass
    doubled the ampersands every time (`Timeline &&&& correlations`), which made
    every pass rewrite every tab — and rewriting a tab title costs a full
    relayout of the workbench.
    """
    current = [bar.tabText(index) for index in range(bar.count())]
    sources = bar.property(TABS)
    if sources is None or len(sources) != bar.count():
        sources = [unescaped(text) for text in current]
    else:
        sources = [unescaped(source) for source in sources]
        for index, shown in enumerate(current):
            if shown != escaped(translate(sources[index])):
                sources[index] = unescaped(shown)     # the code replaced the title
    bar.setProperty(TABS, sources)
    for index, source in enumerate(sources):
        displayed = escaped(translate(source))
        if current[index] != displayed:
            bar.setTabText(index, displayed)


def item_sources(widget, current):
    """Sources of a combo or a list, kept in step with the items on screen."""
    recorded = widget.property(ITEMS)
    if recorded and len(recorded) == len(current):
        if all(shown == source or shown == english(source)
               for shown, source in zip(current, recorded)):
            return list(recorded)
    sources = []
    for index, shown in enumerate(current):
        previous = recorded[index] if recorded and index < len(recorded) else None
        if previous is not None and (shown == previous or shown == english(previous)):
            sources.append(previous)
        else:
            sources.append(shown)
    widget.setProperty(ITEMS, sources)
    return sources


def apply_to_items(combo):
    current = [combo.itemText(index) for index in range(combo.count())]
    for index, source in enumerate(item_sources(combo, current)):
        displayed = translate(source)
        if current[index] != displayed:
            combo.setItemText(index, displayed)


def apply_to_list(widget):
    current = [widget.item(index).text() for index in range(widget.count())]
    for index, source in enumerate(item_sources(widget, current)):
        displayed = translate(source)
        if current[index] != displayed:
            widget.item(index).setText(displayed)


def apply_to_headers(table):
    if not isinstance(table, QTableWidget):
        return
    current = [table.horizontalHeaderItem(column).text() if table.horizontalHeaderItem(column) else ""
               for column in range(table.columnCount())]
    sources = table.property(HEADERS)
    if (sources is None or len(sources) != len(current)
            or any(shown != source and shown != english(source)
                   for shown, source in zip(current, sources))):
        sources = current
        table.setProperty(HEADERS, sources)
    for column, source in enumerate(sources):
        item = table.horizontalHeaderItem(column)
        if item is not None and source:
            displayed = translate(source)
            if current[column] != displayed:
                item.setText(displayed)


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
    displayed = translate(source)
    if action.text() != displayed:
        action.setText(displayed)


def apply_to_menu(menu):
    for action in menu.actions():
        apply_to_action(action)
        if action.menu() is not None:
            apply_to_menu(action.menu())


def translate_tree(root):
    """Everything under `root`: widgets, titles, tabs, lists, headers, menus."""
    if not isinstance(root, QWidget):
        return
    apply_to_title(root)
    for widget in [root, *root.findChildren(QWidget)]:
        if isinstance(widget, WIDGETS):
            apply_to_widget(widget)
        elif isinstance(widget, PLACEHOLDERS):
            apply_to_placeholder(widget)
        apply_to_tooltip(widget)
        if isinstance(widget, QComboBox):
            apply_to_items(widget)
        elif isinstance(widget, QListWidget):
            apply_to_list(widget)
        elif isinstance(widget, QTableWidget):
            apply_to_headers(widget)
    for bar in ([root] if isinstance(root, QTabBar) else []) + root.findChildren(QTabBar):
        apply_to_tabbar(bar)
    for tree in ([root] if isinstance(root, QTreeWidget) else []) + root.findChildren(QTreeWidget):
        translate_items(tree)
    for menu_bar in root.findChildren(QMenuBar):
        for action in menu_bar.actions():
            apply_to_action(action)
            if action.menu() is not None:
                apply_to_menu(action.menu())
    # A popup menu is its own root: findChildren never returns it.
    for menu in ([root] if isinstance(root, QMenu) else []) + root.findChildren(QMenu):
        apply_to_menu(menu)
    for toolbar in root.findChildren(QToolBar):
        for action in toolbar.actions():
            apply_to_action(action)


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
    translate_tree(window)


class LanguageFilter(QObject):
    """Translate a window the moment it appears.

    Dialogs are built by a dozen modules and shown by a dozen more; translating
    the tree on `Show` covers every one of them without touching their code. The
    pass runs once the window is fully built, so the lookups that find a menu by
    its French name while the interface is assembled are never disturbed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False

    def eventFilter(self, watched, event):
        # French is the source: nothing to do, and the walk is not free.
        if current_language() == SOURCE_LANGUAGE:
            return False
        if event.type() == QEvent.Show and not self._busy and isinstance(watched, QWidget):
            self._busy = True
            try:
                translate_tree(watched)
            finally:
                self._busy = False
        return False


def install(app):
    """One filter and one set of hooks for the application; idempotent."""
    existing = getattr(app, FILTER, None)
    if existing is not None:
        return existing
    install_hooks()
    language_filter = LanguageFilter(app)
    app.installEventFilter(language_filter)
    setattr(app, FILTER, language_filter)
    return language_filter


ITEM_SOURCE = Qt.UserRole + 901      # the French label an item was built with
ITEM_HOOKED = set()
_ITEM_BUSY = [False]                 # an item setter calling another one


def _remember(item, text, column=None):
    if column is None:
        item.setData(ITEM_SOURCE, text)
    else:
        item.setData(column, ITEM_SOURCE, text)


def _recall(item, column=None):
    return item.data(ITEM_SOURCE) if column is None else item.data(column, ITEM_SOURCE)


def _hook_item_class(cls, tree_item):
    """Items built with their label, or given one later, are translated too.

    A tree node, a table cell or a list entry is not a widget: no event reaches
    it. Its label is captured where the code writes it, and the French source is
    kept on the item so switching back restores it.
    """
    if cls in ITEM_HOOKED:
        return
    ITEM_HOOKED.add(cls)
    original_init = cls.__init__
    original_set_text = cls.setText

    def init(self, *args):
        if _ITEM_BUSY[0]:
            return original_init(self, *args)
        for index, arg in enumerate(args):
            if isinstance(arg, str):
                forwarded = list(args)
                forwarded[index] = translate(arg)
                original_init(self, *forwarded)
                _remember(self, arg)
                return
            if isinstance(arg, (list, tuple)) and arg and all(isinstance(value, str) for value in arg):
                forwarded = list(args)
                forwarded[index] = [translate(value) for value in arg]
                original_init(self, *forwarded)
                for column, text in enumerate(arg):
                    _remember(self, text, column if tree_item else None)
                return
        original_init(self, *args)

    def set_text(self, *args):
        if _ITEM_BUSY[0]:
            return original_set_text(self, *args)
        _ITEM_BUSY[0] = True
        try:
            if tree_item:
                column, text = args[0], args[1]
                if isinstance(text, str):
                    _remember(self, text, column)
                    return original_set_text(self, column, translate(text))
            else:
                text = args[0]
                if isinstance(text, str):
                    _remember(self, text)
                    return original_set_text(self, translate(text))
            return original_set_text(self, *args)
        finally:
            _ITEM_BUSY[0] = False

    original_set_data = cls.setData

    def set_data(self, *args):
        # Some tables write the label through the display role, not the text.
        if _ITEM_BUSY[0]:
            return original_set_data(self, *args)
        wants = (tree_item and len(args) == 3 and args[1] == Qt.DisplayRole and isinstance(args[2], str)) \
            or (not tree_item and len(args) == 2 and args[0] == Qt.DisplayRole and isinstance(args[1], str))
        if not wants:
            return original_set_data(self, *args)
        _ITEM_BUSY[0] = True
        try:
            if tree_item:
                _remember(self, args[2], args[0])
                return original_set_data(self, args[0], args[1], translate(args[2]))
            _remember(self, args[1])
            return original_set_data(self, args[0], translate(args[1]))
        finally:
            _ITEM_BUSY[0] = False

    cls.__init__ = init
    cls.setText = set_text
    cls.setData = set_data


def translate_items(tree):
    """Re-apply the stored source to every item under a tree widget."""
    def walk(item):
        for column in range(tree.columnCount()):
            source = _recall(item, column)
            if source is None:
                continue
            displayed = translate(source)
            if item.text(column) != displayed:
                item.setText(column, displayed)
        for index in range(item.childCount()):
            walk(item.child(index))

    for index in range(tree.topLevelItemCount()):
        walk(tree.topLevelItem(index))


HOOKED = {}


def _hook(cls, name, wrap):
    """Install one wrapper, once, keeping the original implementation."""
    key = (cls, name)
    if key in HOOKED:
        return
    original = getattr(cls, name)
    HOOKED[key] = original
    setattr(cls, name, wrap(original))


def _translated_setter(key):
    """A setter that records the French source and displays the translation."""
    def wrap(original):
        def setter(self, text, *args):
            if not isinstance(text, str) or current_language() == SOURCE_LANGUAGE:
                return original(self, text, *args)
            return original(self, translate(source_of(self, key, text)), *args)
        return setter
    return wrap


def _translated_tab_text(original):
    def set_tab_text(self, index, text):
        if not isinstance(text, str) or current_language() == SOURCE_LANGUAGE:
            return original(self, index, text)
        return original(self, index, translate(text))
    return set_tab_text


def _remember_item(widget, index, source):
    """Keep the French label of an item the moment the code adds it."""
    recorded = widget.property(ITEMS)
    sources = list(recorded) if recorded else []
    while len(sources) <= index:
        sources.append("")
    sources[index] = source
    widget.setProperty(ITEMS, sources)


def _translated_item(original):
    """Combos and lists: the label is the first string argument."""
    def add_item(self, *args):
        if args and isinstance(args[0], str) and current_language() != SOURCE_LANGUAGE:
            source = args[0]
            _remember_item(self, self.count(), source)
            args = (translate(source),) + args[1:]
        return original(self, *args)
    return add_item


def _translated_insert_item(original):
    def insert_item(self, index, *args):
        if args and isinstance(args[0], str) and current_language() != SOURCE_LANGUAGE:
            source = args[0]
            _remember_item(self, index, source)
            args = (translate(source),) + args[1:]
        return original(self, index, *args)
    return insert_item


def _translated_set_item_text_hook(original):
    def set_item_text(self, index, text):
        if isinstance(text, str) and current_language() != SOURCE_LANGUAGE:
            _remember_item(self, index, text)
            text = translate(text)
        return original(self, index, text)
    return set_item_text


def _translated_set_item_text(original):
    def set_item_text(self, index, text):
        if not isinstance(text, str):
            return original(self, index, text)
        return original(self, index, translate(text))
    return set_item_text


def _translated_add_items(original):
    def add_items(self, texts):
        if isinstance(texts, (list, tuple)) and current_language() != SOURCE_LANGUAGE:
            start = self.count()
            for offset, text in enumerate(texts):
                if isinstance(text, str):
                    _remember_item(self, start + offset, text)
            texts = [translate(text) if isinstance(text, str) else text for text in texts]
        return original(self, texts)
    return add_items


def _translated_headers(original):
    def set_headers(self, labels):
        if isinstance(labels, (list, tuple)) and current_language() != SOURCE_LANGUAGE:
            sources = [label if isinstance(label, str) else label for label in labels]
            self.setProperty(HEADERS, list(sources))
            labels = [translate(label) if isinstance(label, str) else label for label in labels]
        return original(self, labels)
    return set_headers


def install_hooks():
    """Translate the text at the moment the code sets it.

    The Show pass covers a window built before it appears; this covers what is
    written afterwards — a counter, an error, a combo filled once a case loads.
    French is the source: in French the wrapper stores the label and sets it
    unchanged, so nothing is lost when the language is switched back.
    """
    for cls in (QLabel, QPushButton, QCheckBox, QRadioButton, QToolButton):
        _hook(cls, "setText", _translated_setter(SOURCE))
    _hook(QGroupBox, "setTitle", _translated_setter(SOURCE))
    for cls in (QLineEdit, QPlainTextEdit, QTextEdit):
        _hook(cls, "setPlaceholderText", _translated_setter(PLACEHOLDER))
    _hook(QWidget, "setWindowTitle", _translated_setter(TITLE))
    _hook(QWidget, "setToolTip", _translated_setter(TOOLTIP))
    _hook(QAction, "setText", _translated_setter(SOURCE))
    _hook(QStatusBar, "showMessage", _translated_setter(SOURCE))
    _hook(QTabBar, "setTabText", _translated_tab_text)
    _hook(QComboBox, "addItem", _translated_item)
    _hook(QComboBox, "insertItem", _translated_insert_item)
    _hook(QComboBox, "setItemText", _translated_set_item_text_hook)
    _hook(QComboBox, "addItems", _translated_add_items)
    _hook(QListWidget, "addItem", _translated_item)
    _hook(QListWidget, "addItems", _translated_add_items)
    _hook(QTableWidget, "setHorizontalHeaderLabels", _translated_headers)
    for cls in (QTreeWidgetItem, QTableWidgetItem, QListWidgetItem):
        _hook_item_class(cls, tree_item=cls is QTreeWidgetItem)
