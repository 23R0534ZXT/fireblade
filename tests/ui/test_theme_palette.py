from PySide6.QtGui import QPalette
from fireblade.core.preferences import Preferences,save_preferences,load_preferences
from fireblade.ui.theme import apply_theme


def test_custom_theme_colors_persist_and_reach_palette_and_styles(qt_application,tmp_path):
    p=Preferences(theme='dark',theme_palette={'base':'#102030','highlight':'#456789'})
    target=tmp_path/'p.json';save_preferences(p,target);assert load_preferences(target)==p
    try:
        apply_theme(qt_application,p.theme,p.theme_palette)
        assert qt_application.palette().color(QPalette.Base).name()=='#102030'
        assert '#456789' in qt_application.styleSheet()
    finally:apply_theme(qt_application)
