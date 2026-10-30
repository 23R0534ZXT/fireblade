"""Native Windows source diagnostic; separate from frozen-EXE qualification."""
import argparse
from pathlib import Path
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from fireblade.core.models import View,Filter,SortKey
from fireblade.validation.gui_driver import GuiRun
from fireblade.ui.theme import apply_theme
from scripts.windows.dataset import generate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--gib',type=int,default=3)
    args=parser.parse_args()
    if os.name!='nt':raise SystemExit('This diagnostic requires native Windows')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    spec=generate(out/'data',target_bytes=args.gib*1024**3)
    app=QApplication([]);apply_theme(app)
    run=GuiRun(app,out/'profile.json','Windows source stall diagnostic, not frozen qualification')
    error=None
    try:
        run.report['dataset']={k:spec[k] for k in ('bytes','rows','sha256')}
        run.check('import',lambda:run.import_csv(spec['source'],out/'large.timeline'))
        for columns in ([1],[1,3,4],[6]):
            def group(columns=columns):
                run.window.set_view(View(groups=columns));run.settle()
                index=run.window.model.index(0,0)
                run.window.tree.setExpanded(index,True);run.settle()
                run.window.tree.setExpanded(index,False);run.settle()
            run.check('groups_'+str(columns),group)
        run.check('global_search',lambda:(run.window.set_view(View(search='user042')),run.settle()))
        run.check('deep_numeric_sort',lambda:run.work(lambda:run.window.case.page(View(sort_column=6,sort_type='number'),offset=100000)))
        run.check('filtered_export',lambda:run.work(lambda:run.window.case.export(out/'filtered.csv',View(filters=[Filter(3,'eq','user042')]))))
        small=out/'small.csv';small.write_text('ID\nsmall\n')
        run.check('switch_small_import',lambda:run.import_csv(small,out/'small.timeline'))
        def back():
            bar,index=run.window.tabs.tab_widget(0)
            QTest.mouseClick(bar,Qt.LeftButton,pos=bar.tabRect(index).intersected(bar.rect()).center());run.settle()
        run.check('reopen_large_case',back)
        run.capture('profile-final')
    except Exception as exc:error=exc
    raise SystemExit(run.finish(error))


if __name__=='__main__':main()
