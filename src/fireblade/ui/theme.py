"""Compact desktop styling. Keep menus, buttons and inputs as standard Qt controls."""
STYLE = """
QWidget { font-family: 'Segoe UI', 'Tahoma', sans-serif; font-size: 12px; }
QToolBar { spacing: 4px; padding: 2px; border-bottom: 1px solid #bcbcbc; }
QTreeView, QPlainTextEdit, QListWidget {
    background: white; color: #202020; alternate-background-color: #f6f6f6;
    border: 1px solid #b5b5b5;
    selection-background-color: #cce8ff; selection-color: #101010;
}
QHeaderView::section { background: #eeeeee; color: #202020; padding: 3px 5px; border: 0; border-right: 1px solid #c5c5c5; border-bottom: 1px solid #b5b5b5; }
"""


def apply_theme(app):
    """Use Windows controls on Windows and a plain light palette elsewhere."""
    import sys
    from PySide6.QtGui import QColor, QPalette
    if sys.platform != "win32":
        app.setStyle("Fusion")
    palette = QPalette()
    for role, color in [
        (QPalette.Window, "#f0f0f0"), (QPalette.WindowText, "#202020"),
        (QPalette.Base, "#ffffff"), (QPalette.AlternateBase, "#f6f6f6"),
        (QPalette.Text, "#202020"), (QPalette.Button, "#f0f0f0"),
        (QPalette.ButtonText, "#202020"), (QPalette.Highlight, "#cce8ff"),
        (QPalette.HighlightedText, "#101010"), (QPalette.ToolTipBase, "#ffffe1"),
        (QPalette.ToolTipText, "#202020"), (QPalette.PlaceholderText, "#707070"),
    ]:
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#808080"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#808080"))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)

