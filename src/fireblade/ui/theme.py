"""One coherent light style, including on Windows with dark system preferences."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPalette

STYLE = """
QWidget { color: #202020; }
QMenuBar, QMenu { background: #f0f0f0; color: #202020; }
QMenuBar::item:disabled, QMenu::item:disabled { color: #686868; }
QMenuBar::item:selected, QMenu::item:selected { background: #cce8ff; color: #101010; }
QToolBar { spacing: 4px; padding: 2px; border-bottom: 1px solid #bcbcbc; }
QPushButton, QToolButton, QCheckBox, QLabel, QTabBar { color: #202020; }
QPushButton:disabled, QToolButton:disabled, QCheckBox:disabled, QLabel:disabled { color: #686868; }
QLineEdit, QComboBox, QTreeView, QPlainTextEdit, QTextBrowser, QListWidget, QTableWidget {
    background: white; color: #202020; alternate-background-color: #f6f6f6;
    border: 1px solid #b5b5b5;
    selection-background-color: #cce8ff; selection-color: #101010;
}
QLineEdit:disabled, QComboBox:disabled { background: #eeeeee; color: #686868; }
QHeaderView::section { background: #eeeeee; color: #202020; padding: 3px 5px; border: 0; border-right: 1px solid #c5c5c5; border-bottom: 1px solid #b5b5b5; }
"""


def apply_theme(app, theme="light"):
    # Native Windows 11 styles can keep dark foregrounds while custom backgrounds
    # are light. Fusion renders every control from the same explicit palette.
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark if theme == "dark" else Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    app.setProperty("fireblade_style", "Fusion " + theme)
    font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
    if font.pointSizeF() < 9:
        font.setPointSizeF(9)
    app.setFont(font)
    palette = QPalette()
    roles = {
        QPalette.Window: "#f0f0f0", QPalette.WindowText: "#202020",
        QPalette.Base: "#ffffff", QPalette.AlternateBase: "#f6f6f6",
        QPalette.Text: "#202020", QPalette.Button: "#f0f0f0",
        QPalette.ButtonText: "#202020", QPalette.Highlight: "#cce8ff",
        QPalette.HighlightedText: "#101010", QPalette.ToolTipBase: "#ffffe1",
        QPalette.ToolTipText: "#202020", QPalette.PlaceholderText: "#686868",
        QPalette.BrightText: "#202020", QPalette.Link: "#0645ad",
        QPalette.LinkVisited: "#663399",
    }
    if theme == "dark":
        replacements = {"#f0f0f0": "#303030", "#202020": "#eeeeee", "#ffffff": "#242424",
                        "#f6f6f6": "#2b2b2b", "#cce8ff": "#315b7d", "#101010": "#ffffff",
                        "#ffffe1": "#35352b", "#686868": "#b0b0b0", "#0645ad": "#80bfff", "#663399": "#c6a2ee"}
        roles = {role: replacements.get(color, color) for role, color in roles.items()}
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        for role, color in roles.items():
            palette.setColor(group, role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#b0b0b0" if theme == "dark" else "#686868"))
    app.setPalette(palette)
    stylesheet = STYLE
    if theme == "dark":
        import re
        colors = {**replacements, "#eeeeee": "#383838", "#bcbcbc": "#555555", "#b5b5b5": "#606060", "#c5c5c5": "#555555"}
        stylesheet = re.sub(r'#[0-9a-fA-F]{6}|\bwhite\b', lambda m: colors.get(m.group(0), "#242424" if m.group(0) == "white" else m.group(0)), STYLE)
    app.setStyleSheet(stylesheet)
