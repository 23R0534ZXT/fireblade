"""Inspect actual rendered glyph pixels, not just QColor roles."""
from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QToolButton

from fireblade.ui.advanced_dialogs import FilterDialog, RulesDialog, SortDialog
from fireblade.core.models import FilterGroup
from fireblade.validation.gui_driver import GuiRun


def luminance(rgb):
    values=[v/255 for v in rgb]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return .2126*linear[0]+.7152*linear[1]+.0722*linear[2]


def rendered_contrast(widget,rect=None):
    image=widget.grab().toImage().convertToFormat(QImage.Format_RGB32)
    ratio=widget.devicePixelRatioF()
    r=rect or widget.rect().adjusted(5,3,-5,-3)
    left,top=max(0,int(r.left()*ratio)),max(0,int(r.top()*ratio))
    right,bottom=min(image.width(),int((r.right()+1)*ratio)),min(image.height(),int((r.bottom()+1)*ratio))
    colors=Counter()
    for y in range(top,bottom):
        for x in range(left,right):
            c=image.pixelColor(x,y);colors[(c.red(),c.green(),c.blue())]+=1
    if not colors:raise AssertionError('Empty text capture')
    background=colors.most_common(1)[0][0]
    bg=luminance(background)
    # Check actual glyphs in either explicit application theme. This catches
    # white-on-white and black-on-black regressions, not only palette settings.
    foreground=[(rgb,count) for rgb,count in colors.items() if (luminance(rgb)>.5 if bg<.3 else luminance(rgb)<.2)]
    ink=sum(count for _,count in foreground)
    contrast=max(((max(bg,luminance(rgb))+.05)/(min(bg,luminance(rgb))+.05) for rgb,_ in foreground),default=1)
    if ink<5 or contrast<4.5:
        raise AssertionError(f'Illegible rendered text: ink={ink}, contrast={contrast:.2f}, background={background}')
    return dict(ink_pixels=ink,contrast=round(contrast,2),background=background)


def run_appearance(app,report_path):
    run=GuiRun(app,report_path,'appearance')
    error=None
    try:
        assert app.platformName()=='windows' and run.report['frozen']
        run.report['scale_factor']=run.window.devicePixelRatioF()
        def welcome():
            bar=run.window.menuBar()
            first=bar.actionGeometry(bar.actions()[0]).adjusted(4,2,-4,-2)
            result={'menu':rendered_contrast(bar,first)}
            button=next(b for b in run.window.findChildren(QPushButton) if b.isVisible() and 'Ouvrir' in b.text())
            result['open_button']=rendered_contrast(button,button.rect().adjusted(30,3,-5,-3))
            tools=[b for b in run.window.findChildren(QToolButton) if b.isVisible() and 'Ouvrir' in b.text()]
            result['toolbar']=rendered_contrast(tools[0],tools[0].rect().adjusted(28,3,-4,-3))
            disabled=next(b for b in run.window.findChildren(QToolButton) if b.isVisible() and 'Exporter' in b.text())
            assert not disabled.isEnabled()
            result['disabled_toolbar']=rendered_contrast(disabled,disabled.rect().adjusted(28,3,-4,-3))
            run.capture('01-welcome')
            return result
        run.check('welcome_menu_and_buttons_rendered_text',welcome)
        source=run.out/'évidence.csv';source.write_text('Artifact,User,ID\nMFT,alice,0001\nEVTX,bob,9007199254740993\n')
        run.check('import_via_visible_confirmation',lambda:run.import_csv(source,run.out/'evidence.timeline'))
        def loaded():
            run.text(run.window.search,'powershell')
            value=rendered_contrast(run.window.search)
            run.text(run.window.search,'')
            value['checkbox']=rendered_contrast(run.window.only_notes,run.window.only_notes.rect().adjusted(23,3,-3,-3))
            value['tab']=rendered_contrast(run.window.tabs,run.window.tabs.tabRect(0).adjusted(6,3,-26,-3))
            run.capture('02-grid')
            return value
        run.check('loaded_grid_search_text',loaded)
        def editors():
            results={}
            for name,dialog in [('filters',FilterDialog(run.window.case.headers,FilterGroup(),run.window)),
                                ('rules',RulesDialog(run.window.case.headers,[],run.window)),
                                ('sort',SortDialog(run.window.case.headers,[],run.window))]:
                dialog.show();QTest.qWait(80)
                if isinstance(dialog,SortDialog):
                    QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Ajouter'),Qt.LeftButton)
                    combo=dialog.table.cellWidget(0,0)
                    results['sort_combo']=rendered_contrast(combo,combo.rect().adjusted(4,3,-20,-3))
                run.capture('03-'+name,dialog)
                buttons=dialog.findChild(QDialogButtonBox)
                results[name]=rendered_contrast(buttons.button(QDialogButtonBox.Ok))
                dialog.close();dialog.deleteLater()
            return results
        run.check('filter_and_rules_editor_text',editors)
        def inactive():
            popup=QPushButton('Autre fenêtre');popup.show();popup.activateWindow();QTest.qWait(100)
            value=rendered_contrast(run.window.menuBar(),run.window.menuBar().actionGeometry(run.window.menuBar().actions()[0]).adjusted(4,2,-4,-2))
            run.capture('04-inactive');popup.close();popup.deleteLater()
            return value
        run.check('inactive_window_text',inactive)
        def app_dark():
            run.window.preferences.theme='dark'
            run.window.apply_preferences()
            run.app.processEvents()
            bar=run.window.menuBar()
            result=rendered_contrast(bar,bar.actionGeometry(bar.actions()[0]).adjusted(4,2,-4,-2))
            run.window.pin_column(1)
            run.app.processEvents()
            assert run.window.tree.frozen.columnWidth(2)>0
            frozen=run.window.tree.frozen
            rect=frozen.visualRect(run.window.model.index(0,2))
            assert rect.isValid() and rect.height()>0, 'Pinned data row has no visible rectangle'
            result['pinned_cell']=rendered_contrast(frozen.viewport(),rect.adjusted(5,3,-5,-3))
            run.capture('05-dark-pinned')
            run.window.pin_column(1)
            run.window.preferences.theme='light'
            run.window.apply_preferences()
            return result
        run.check('application_dark_theme_and_pinned_grid',app_dark)
    except Exception as exc:error=exc
    return run.finish(error)
