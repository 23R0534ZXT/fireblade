import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from fireblade.ui.theme import apply_theme
from fireblade.validation.appearance import rendered_contrast
from fireblade.validation.gui_driver import GuiRun


def test_white_text_regression_is_detected_in_actual_pixels(qt_application):
    button=QPushButton('Ouvrir un fichier')
    button.setStyleSheet('color: white; background: #f0f0f0; border: 0;')
    button.setFocusPolicy(Qt.NoFocus)
    button.resize(180,34);button.show();QTest.qWait(30)
    with pytest.raises(AssertionError,match='Illegible'):
        rendered_contrast(button)
    button.close();button.deleteLater()


def test_light_theme_resets_dark_active_inactive_and_disabled_colors(qt_application):
    app=qt_application
    dark=QPalette()
    for group in (QPalette.Active,QPalette.Inactive,QPalette.Disabled):
        dark.setColor(group,QPalette.Window,QColor('#202020'))
        dark.setColor(group,QPalette.ButtonText,QColor('white'))
        dark.setColor(group,QPalette.Text,QColor('white'))
    app.setPalette(dark);app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    apply_theme(app)
    for group in (QPalette.Active,QPalette.Inactive,QPalette.Disabled):
        assert app.palette().color(group,QPalette.ButtonText)!=QColor('white')
    button=QPushButton('Ouvrir un fichier');button.resize(180,34);button.show();QTest.qWait(30)
    assert rendered_contrast(button)['contrast']>=4.5
    button.setEnabled(False);QTest.qWait(20)
    assert rendered_contrast(button)['contrast']>=4.5
    button.close();button.deleteLater();apply_theme(app)


def test_GUI_driver_uses_visible_import_and_context_menus(qt_application,tmp_path):
    source=tmp_path/'source.csv';source.write_text('Artifact,User,ID\nMFT,alice,001\nEVTX,bob,002\nMFT,alice,003\n')
    run=GuiRun(qt_application,tmp_path/'qa/report.json','driver smoke, not Windows qualification')
    error=None
    try:
        run.import_csv(source,tmp_path/'case.timeline')
        assert run.window.model.rowCount()==3
        run.header(0,'Grouper par cette colonne')
        assert run.window.view.groups==[0]
        run.header(1,'Ajouter au groupement')
        assert run.window.view.groups==[0,1]
        index=run.window.model.index(0,0)
        run.window.tree.setCurrentIndex(index)
        QTest.keyClick(run.window.tree,Qt.Key_Right);run.settle()
        assert run.window.model.rowCount(index)==1
        run.menu('Affichage','Réinitialiser la vue')
        assert run.window.view.groups==[]
    except Exception as exc:
        error=exc;raise
    finally:
        code=run.finish(error)
        if error is None:assert code==0


def test_GUI_driver_sort_editor_and_note_dialog(qt_application,tmp_path):
    from PySide6.QtWidgets import QPlainTextEdit
    from fireblade.ui.advanced_dialogs import SortDialog
    source=tmp_path/'source.csv';source.write_text('User,ID\nalice,10\nbob,0002\nalice,1\n')
    run=GuiRun(qt_application,tmp_path/'qa/report.json','driver smoke, not Windows qualification')
    error=None
    try:
        run.import_csv(source,tmp_path/'case.timeline')
        def edit(dialog):
            assert isinstance(dialog,SortDialog)
            QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Ajouter'),Qt.LeftButton)
            run.choose(dialog.table.cellWidget(0,0),1)
            run.choose(dialog.table.cellWidget(0,1),1)
            run.accept(dialog)
        run.modal(edit);run.menu('Affichage','Tri sur plusieurs colonnes…')
        assert run.window.model.node(run.window.model.index(0,0)).values[2]=='1'
        tree=run.window.tree
        QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.visualRect(run.window.model.index(0,1)).center())
        def note(dialog):
            field=dialog.findChild(QPlainTextEdit)
            assert field is not None
            run.text(field,'À examiner');run.accept(dialog)
        run.modal(note);run.menu('Édition','Ajouter une note à la sélection…')
        assert list(run.window.case.bookmarks().values())==['À examiner']
    except Exception as exc:error=exc;raise
    finally:
        code=run.finish(error)
        if error is None:assert code==0


def test_GUI_driver_applies_successive_nested_sort_commands(qt_application,tmp_path):
    from fireblade.ui.advanced_dialogs import SortDialog
    source=tmp_path/'sorts.csv'
    source.write_text('Timestamp,Kind,Number\n2026-01-02,B,2\n2026-01-01,A,1\n2026-01-03,A,3\n')
    run=GuiRun(qt_application,tmp_path/'qa/report.json','successive menu commands')
    error=None
    try:
        run.import_csv(source,tmp_path/'sorts.timeline')
        for column,kind,descending,wanted in [(2,'number',True,3),(1,'text',False,2),(0,'timestamp',False,2),(0,'timestamp',True,3)]:
            def edit(dialog):
                assert isinstance(dialog,SortDialog)
                while dialog.table.rowCount():
                    dialog.table.setCurrentCell(0,0)
                    QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Retirer'),Qt.LeftButton)
                QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Ajouter'),Qt.LeftButton)
                run.choose(dialog.table.cellWidget(0,0),column)
                combo=dialog.table.cellWidget(0,1);run.choose(combo,combo.findData(kind))
                run.choose(dialog.table.cellWidget(0,2),int(descending));run.accept(dialog)
            run.modal(edit);run.menu('Affichage','Tri sur plusieurs colonnes…')
            assert run.window.view.sorts[0].kind==kind
            assert run.window.model.node(run.window.model.index(0,0)).values[0]==wanted
    except Exception as exc:error=exc;raise
    finally:run.finish(error)
