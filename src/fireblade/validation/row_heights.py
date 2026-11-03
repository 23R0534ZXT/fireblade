"""Exercise auto-sized rows, shared pin geometry and long header probing."""
import csv
from pathlib import Path
import time

from PySide6.QtWidgets import QApplication,QAbstractItemView

from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.reader_detection import header_record,signatures
from fireblade.ui.app import Window
from fireblade.ui.row_heights import RowHeightDialog


def check_auto_row_heights(parent,directory,expect,captures=None):
    directory=Path(directory);source=directory/'multiline-height.csv'
    with source.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['Text','Other','N'])
        writer.writerow(['\n'.join(f'line {i}' for i in range(8)),'word '*100,'1']);writer.writerow(['short','short','2'])
    case=Case(directory/'multiline-height.timeline',settings=parent.settings);case.import_csv(source)
    view=View(auto_row_height=True,layout_styles={'row':{'word_wrap':True}},pinned_columns=[0],right_pinned_columns=[2])
    window=Window(require_case=False, settings=parent.settings);errors=[];window.error=errors.append
    def settle():
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            QApplication.processEvents()
            if not window.jobs and not window.pool.activeThreadCount() and not window.model.jobs and not window.tree.row_heights.pending:return
            time.sleep(.005)
        raise TimeoutError('Automatic row heights did not settle')
    try:
        window.attach(case,view);window.show();settle()
        tree=window.tree;tree.frozen.setColumnWidth(1,140);tree.setColumnWidth(2,96);settle()
        height=tree.visualRect(window.model.index(0,2)).height()
        expect(height>3*window.fontMetrics().height(),'RowAutoHeight is still limited to three lines')
        expect(window.model.index(0,1).data().count('\n')==7,'Displayed multiline values lost their line breaks')
        for panel,column in [(tree.frozen,1),(tree.right_frozen,3)]:
            expect(panel.visualRect(window.model.index(0,column)).height()==height,'Automatic row heights diverged in a pinned view')
            expect(panel.visualRect(window.model.index(1,column)).top()==tree.visualRect(window.model.index(1,2)).top(),'Pinned rows are vertically misaligned')
            expect(panel.verticalScrollMode()==QAbstractItemView.ScrollPerPixel,'Tall rows cannot be scrolled in pixels')
        expect(tree.verticalScrollBar().maximum()>0,'Tall-row scroll fixture does not exercise scrolling')
        tree.verticalScrollBar().setValue(min(20,tree.verticalScrollBar().maximum()));QApplication.processEvents()
        expect(tree.frozen.visualRect(window.model.index(0,1)).top()==tree.visualRect(window.model.index(0,2)).top(),'Pinned pixel scrolling is out of sync')
        tree.verticalScrollBar().setValue(0);tree.setColumnWidth(2,500);settle()
        smaller=tree.visualRect(window.model.index(0,2)).height()
        expect(smaller<height and smaller>=8*window.fontMetrics().height(),'Resizing did not recompute the shared wrapped height')
        dialog=RowHeightDialog(window.view,window)
        try:
            dialog.accept();expect(dialog.result()==1 and dialog.view==window.view,'Row-height editor did not preserve imported settings')
        finally:dialog.deleteLater()
        saved=View.from_json(window.view.to_json());saved.auto_row_height=False
        window.set_view(saved);settle()
        expect(tree.uniformRowHeights() and tree.frozen.uniformRowHeights() and tree.right_frozen.uniformRowHeights(),'Uniform height was not restored')
        saved.auto_row_height=True;window.set_view(saved);settle()
        expect(not tree.uniformRowHeights(),'Saved view lost automatic row height')
        if captures:window.grab().save(str(Path(captures)/'automatic-multiline-row-height.png'))
        expect(not errors,'Automatic-height UI reported an error')
    finally:
        settle();window.close();parent.apply_preferences();parent.activateWindow();QApplication.processEvents()


def check_progressive_header_probe(directory,expect):
    directory=Path(directory)
    expected=signatures('Text,Identifier')
    for encoding in ('utf-8','utf-16','utf-32'):
        path=directory/(encoding+'-wide-header.csv')
        path.write_text('Text,Identifier'+(' '*140000)+'\nvalue,1\n',encoding=encoding,newline='')
        original=path.read_bytes();record=header_record(path)
        expect(record is not None and signatures(record)==expected,'A complete long header was not recognized for '+encoding)
        expect(path.read_bytes()==original,'Header probing rewrote the source')
        path.write_text('Text,Identifier'+(' '*140000)+',Extra\nvalue,1,other\n',encoding=encoding,newline='')
        record=header_record(path)
        expect(record is not None and signatures(record)!=expected,'A truncated header prefix produced a false reader match')
