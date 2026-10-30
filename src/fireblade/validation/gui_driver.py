"""Shared native GUI exercise driver. Input is QtTest, not a human operator."""
import copy
from datetime import datetime, timezone
import json
import os
import platform
from pathlib import Path
import statistics
import sys
import time
import duckdb

from PySide6.QtCore import QPoint, QTimer, Qt, qVersion
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMenu, QPushButton

from fireblade.ui.app import Window
from fireblade.ui.dialogs import ImportDialog
from fireblade.validation.windows_check import windows_memory


class GuiRun:
    def __init__(self, app, report_path, kind):
        self.app, self.path = app, Path(report_path).resolve()
        if self.path.exists():
            raise ValueError('Choose a new QA report path')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.out = self.path.parent
        self.errors = []
        self.report = dict(status='running', kind=kind, started_utc=datetime.now(timezone.utc).isoformat(),
                           platform=sys.platform, frozen=bool(getattr(sys,'frozen',False)), qt_platform=app.platformName(),
                           operating_system=platform.platform(),machine=platform.machine(),cpu_count=os.cpu_count(),
                           python=sys.version.split()[0],duckdb=duckdb.__version__,qt=qVersion(),
                           automation='QtTest clicks/keys and QContextMenuEvent for header menus; native Qt Windows widgets, not physical human input',
                           checks=[], screenshots=[], style=app.property('fireblade_style'),
                           font=dict(family=app.font().family(), point_size=app.font().pointSizeF()))
        self.window = Window(rule_path=self.out/'qa-global-rules.json')
        self.window.error = lambda error: self.errors.append(str(error))
        self.window.show()
        self.report['font'] = dict(family=app.font().family(), point_size=app.font().pointSizeF())
        self.report['style'] = app.property('fireblade_style')
        from fireblade.validation.responsiveness import ResponsivenessProbe
        self.probe = ResponsivenessProbe()
        self.stalls = []
        self.lags = []
        self.last_tick = time.monotonic()
        self.last_flush = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.flush()

    def tick(self):
        now = time.monotonic()
        gap=now-self.last_tick
        self.lags.append(gap)
        if gap>.25:
            self.stalls.append(dict(gap_ms=round(gap*1000,1),phase=self.report.get('current_check'),
                                    status=self.window.statusBar().currentMessage(),stack=self.probe.latest_stack))
            self.stalls=sorted(self.stalls,key=lambda item:item['gap_ms'],reverse=True)[:20]
        self.last_tick = now
        if now-self.last_flush > 5:
            self.flush()
            self.last_flush = now

    def flush(self):
        temporary = self.path.with_suffix('.partial')
        temporary.write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temporary,self.path)

    def settle(self, timeout=180, allow_errors=False):
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            self.app.processEvents()
            if self.errors and not allow_errors:
                raise AssertionError('UI errors: '+repr(self.errors))
            w=self.window
            if not w.jobs and not w.pool.activeThreadCount() and (w.model is None or not w.model.jobs):
                self.app.processEvents()
                return
            # qWait runs Qt's nested event loop while retaining Python's GIL.
            # That can starve CSV/XLSX worker code and falsify performance tests.
            # Pump widgets, then explicitly give worker threads the interpreter.
            time.sleep(.01)
        raise TimeoutError('GUI work timed out: '+self.window.statusBar().currentMessage())

    def check(self,name,operation):
        self.report['current_check']=name
        self.flush()
        first_tick=len(self.lags)
        start=time.perf_counter()
        try:
            result=operation()
            if self.errors:
                raise AssertionError(repr(self.errors))
            item=dict(name=name,status='passed',seconds=round(time.perf_counter()-start,3))
            item['max_timer_gap_ms']=round(max(self.lags[first_tick:],default=0)*1000,1)
            if result is not None:item['details']=result
            if os.name=='nt':item['memory']=windows_memory()
            self.report['checks'].append(item)
        except Exception as error:
            self.report['checks'].append(dict(name=name,status='failed',error=str(error),seconds=round(time.perf_counter()-start,3)))
            self.capture('failure')
            raise
        finally:self.flush()

    def capture(self,name,widget=None):
        self.app.processEvents()
        path=self.out/(name+'.png')
        if not (widget or self.window).grab().save(str(path)):
            raise RuntimeError('Screenshot failed: '+str(path))
        self.report['screenshots'].append(path.name)
        return path

    def modal(self,callback):
        deadline=time.monotonic()+10
        def attempt():
            dialog=self.app.activeModalWidget()
            if not isinstance(dialog,QDialog):
                if time.monotonic()<deadline:QTimer.singleShot(30,attempt)
                else:self.errors.append('Expected GUI dialog did not open')
                return
            try:callback(dialog)
            except Exception as error:
                self.errors.append(str(error));dialog.reject()
        QTimer.singleShot(80,attempt)

    @staticmethod
    def text(widget,value):
        widget.setFocus()
        QTest.keyClick(widget,Qt.Key_A,Qt.ControlModifier)
        QApplication.clipboard().setText(value)
        QTest.keyClick(widget,Qt.Key_V,Qt.ControlModifier)

    @staticmethod
    def choose(widget,index):
        widget.setFocus()
        QTest.keyClick(widget,Qt.Key_Home)
        for _ in range(index):QTest.keyClick(widget,Qt.Key_Down)

    @staticmethod
    def accept(dialog):
        box=dialog.findChild(QDialogButtonBox)
        button=box.button(QDialogButtonBox.Ok) or box.button(QDialogButtonBox.Open)
        if button is None:raise AssertionError('No dialog confirmation button')
        QTest.mouseClick(button,Qt.LeftButton)

    def import_csv(self,source,target):
        def fill(dialog):
            if not isinstance(dialog,ImportDialog):raise AssertionError('Unexpected import dialog')
            self.text(dialog.target,str(target))
            self.accept(dialog)
        self.modal(fill)
        # The same path as launching the app with a CSV or dropping it on the EXE.
        self.window.open_path(source)
        self.settle(600)

    def menu(self,name,action):
        bar=self.window.menuBar()
        top=next(a for a in bar.actions() if a.text().replace('&','')==name)
        menu=top.menu()
        item=next(a for a in menu.actions() if a.text()==action)
        def select():QTest.mouseClick(menu,Qt.LeftButton,pos=menu.actionGeometry(item).center())
        QTimer.singleShot(60,select)
        QTest.mouseClick(bar,Qt.LeftButton,pos=bar.actionGeometry(top).center())
        QTest.qWait(150)
        self.settle()

    def header(self,column,label):
        w=self.window;section=column+1
        w.tree.scrollTo(w.model.index(0,section))
        self.app.processEvents()
        header=w.tree.header()
        x=header.sectionViewportPosition(section)+min(header.sectionSize(section)//2,40)
        if not 0<=x<header.viewport().width():raise AssertionError('Header not visible')
        def select():
            menu=self.app.activePopupWidget()
            if not isinstance(menu,QMenu):self.errors.append('Header menu not opened');return
            try:
                action=next(a for a in menu.actions() if a.text()==label)
                QTest.mouseClick(menu,Qt.LeftButton,pos=menu.actionGeometry(action).center())
            except Exception as error:
                self.errors.append(str(error));menu.close()
        QTimer.singleShot(60,select)
        point=QPoint(x,header.height()//2)
        event=QContextMenuEvent(QContextMenuEvent.Mouse,point,header.viewport().mapToGlobal(point))
        QApplication.sendEvent(header.viewport(),event)
        self.settle()

    def button(self,label):
        button=next(b for b in self.window.findChildren(QPushButton) if b.text()==label and b.isVisible())
        QTest.mouseClick(button,Qt.LeftButton)
        self.settle()

    def work(self,operation,timeout=300):
        result=[]
        self.window.run(operation,result.append,exclusive=True)
        self.settle(timeout)
        if len(result)!=1:raise AssertionError('Operation did not complete')
        return result[0]

    def finish(self,error=None):
        if error:self.report['error']=str(error)
        self.report['status']='failed' if error or self.errors else 'passed'
        self.report['ui_errors']=self.errors
        self.timer.stop()
        self.report['responsiveness_diagnostics']=self.probe.stop()
        self.report['responsiveness_stalls']=self.stalls
        if self.lags:
            ordered=sorted(self.lags)
            self.report['ui_heartbeat']=dict(interval_ms=50,max_gap_ms=round(max(ordered)*1000,1),
                                             p95_gap_ms=round(ordered[int((len(ordered)-1)*.95)]*1000,1),samples=len(ordered))
        if os.name=='nt':self.report['memory']=windows_memory()
        try:
            if self.window.jobs or self.window.pool.activeThreadCount() or (self.window.model and self.window.model.jobs):
                self.window.interrupt_queries();self.settle(30,allow_errors=True)
            if not self.window.close():raise RuntimeError('Window did not close')
        except Exception as cleanup:
            self.report['status']='failed';self.report['cleanup_error']=str(cleanup)
        self.report['finished_utc']=datetime.now(timezone.utc).isoformat()
        self.flush()
        return 0 if self.report['status']=='passed' else 1
