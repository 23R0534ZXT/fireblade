"""Exercise the appearance migration and actual pixels inside the standalone EXE."""
import base64
import json
from pathlib import Path
from PySide6.QtCore import QByteArray,QBuffer,QIODevice,Qt
from PySide6.QtGui import QImage,QColor
from fireblade.core.models import View
from fireblade.core.tle_layout import read_tle_layout


def check_layout_appearance(window,directory,settle,expect,captures=None):
    directory=Path(directory)
    image=QImage(10,10,QImage.Format_ARGB32);image.fill(QColor('#fe12ab'))
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly)
    expect(image.save(buffer,'PNG'),'Cannot encode a layout image')
    encoded=base64.b64encode(bytes(data)).decode('ascii')
    path=directory/'embedded-appearance.layout'
    path.write_text(f'''<XtraSerializer><property name="Appearance">
      <property name="GroupPanel"><property name="BackColor">#102030</property><property name="BorderColor">#ff0000</property><property name="Image">{encoded}</property><property name="ImageAlignment">TopRight</property></property>
      <property name="Row"><property name="TextOptions"><property name="WordWrap">Wrap</property></property></property>
      <property name="HeaderPanel"><property name="BackColor">White</property><property name="BorderColor">#ff0000</property><property name="Image">{encoded}</property><property name="ImageAlignment">TopRight</property></property>
      </property><property name="Columns"><property name="Item1"><property name="FieldName">User</property><property name="Fixed">Right</property></property></property>
      <property name="FormatRules"><property name="Item1"><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[User]='bob'</property><property name="PredefinedName">Evidence</property></property></property></property></XtraSerializer>''',encoding='utf-8')
    sidecar=Path(str(path)+'.styles.json')
    sidecar.write_text(json.dumps({'Evidence':dict(background='#abcdef',border_color='#00ff00',image=encoded,image_align='TopRight')}),encoding='utf-8')
    layout=read_tle_layout(path,window.case.headers)
    expect(not layout.warnings,'Unexpected layout appearance adaptation warning')
    window.apply_tle_layout(layout);settle()
    def pixel(widget,x,y):
        raster=widget.grab().toImage();ratio=raster.devicePixelRatio()
        return raster.pixelColor(round(x*ratio),round(y*ratio)).name()
    panel=window.groups_label
    expect(pixel(panel,1,4)=='#102030','Group panel background is invisible')
    expect(pixel(panel,panel.width()-3,3)=='#fe12ab','Embedded panel image is invisible')
    expect(pixel(panel,0,0)=='#ff0000','Imported panel border is invisible')
    right=window.tree.right_frozen;column=window.case.headers.index('User')+1
    header=right.header();x=header.sectionViewportPosition(column)+header.sectionSize(column)-3
    expect(pixel(header.viewport(),x,3)=='#fe12ab','Pinned header image is invisible')
    expect(pixel(header.viewport(),x,0)=='#ff0000','Pinned header border is invisible')
    expect(header.height()==window.tree.header().height(),'Styled pinned header is misaligned')
    for row in range(window.model.rowCount()):
        index=window.model.index(row,column)
        if index.data()=='bob':break
    else:raise AssertionError('Missing conditional appearance fixture row')
    expect(index.data(Qt.BackgroundRole).name()=='#abcdef','Custom named style was not resolved')
    rect=right.visualRect(index)
    expect(pixel(right.viewport(),rect.right()-4,rect.top()+4)=='#fe12ab','Conditional image is invisible')
    expect(pixel(right.viewport(),rect.left(),rect.top()+5)=='#00ff00','Conditional border is invisible')
    expect(rect.height()>=3*window.fontMetrics().height(),'Wrapped row height was not reserved')
    saved=View.from_json(window.view.to_json());sidecar.unlink()
    expect(saved.format_rules[0].appearance['image']==encoded,'Named style image did not persist')
    if captures:window.grab().save(str(Path(captures)/'extended-layout-appearance.png'))
    window.set_view(View());settle()
    expect(not panel._tle_appearance.appearance,'Panel style leaked into a different view')
    window.set_view(saved);settle()
    expect(pixel(panel,panel.width()-3,3)=='#fe12ab','Restored view lost its embedded image')


def check_mixed_icon_layout(window,directory,settle,expect):
    """Import and render mixed-unit thresholds in the real standalone EXE."""
    from fireblade.core.models import Filter
    from fireblade.core.rule_store import RuleBook
    from fireblade.ui.advanced_dialogs import RulesDialog
    from fireblade.ui.visual_rules import ICON_ROLE
    column=window.case.headers.index('ID')
    icons=''.join(f'<property name="Item{i}"><property name="Value">{value}</property><property name="ValueType">{mode}</property><property name="ValueComparison">{comparison}</property><property name="Color">{color}</property></property>'
                  for i,(value,mode,comparison,color) in enumerate([('50','Percentile','Greater','#218739'),('5','Number','GreaterOrEqual','#c58b00'),('0','Percent','GreaterOrEqual','#c62828')]))
    path=Path(directory)/'mixed-icon-units.layout'
    path.write_text(f'<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">ID</property><property name="Fixed">Right</property></property></property><property name="FormatRules"><property name="Item1"><property name="ColumnName">ID</property><property name="RuleType">#FormatConditionRuleIconSet</property><property name="Rule"><property name="IconSet"><property name="ValueType">Number</property><property name="Icons">{icons}</property></property></property></property></property></XtraSerializer>',encoding='utf-8')
    layout=read_tle_layout(path,window.case.headers)
    window.apply_tle_layout(layout);settle()
    rule=window.view.format_rules[0]
    expect(rule.icon_threshold_modes==['number','percentile'],'Mixed icon units lost during XML import')
    expect(rule.icon_floor_mode=='percent','Icon floor unit override was lost')
    expect(RuleBook.from_bytes(RuleBook(window.case.headers,[rule]).to_bytes()).rules==[rule],'Mixed icon units lost in global rules')
    dialog=RulesDialog(window.case.headers,[rule],window)
    try:
        dialog.accept()
        expect(dialog.result()==1 and dialog.rules==[rule],'Rule editor modified mixed thresholds without an edit')
    finally:dialog.deleteLater()
    expected={'9007199254740993':2,'1':0,'5':1}
    for row in range(window.model.rowCount()):
        index=window.model.index(row,column+1);value=window.model.node(index).values[column+1]
        expect(index.data(ICON_ROLE)[2]==expected[value],'Wrong mixed-threshold icon level')
        tree=window.tree.right_frozen;rect=tree.visualRect(index);image=tree.viewport().grab().toImage();ratio=image.devicePixelRatio()
        actual=image.pixelColor(round((rect.right()-10)*ratio),round(rect.center().y()*ratio)).name()
        expect(actual==rule.icon_colors[expected[value]],'Mixed-threshold icon was not painted in the pinned grid')
    saved=View.from_json(window.view.to_json())
    window.view.filters=[Filter(column,'le','5')];window.apply();settle()
    expect([window.model.index(row,column+1).data(ICON_ROLE)[2] for row in range(window.model.rowCount())]==[0,2],'Mixed thresholds did not follow the filter')
    window.set_view(saved);settle()
    expect(window.view.format_rules[0]==rule,'Mixed thresholds changed after restoring the view')


def check_priority_layout(window,directory,settle,expect):
    """Check priority conflicts, selected-cell pixels and view restoration."""
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyle,QStyleOptionViewItem
    path=Path(directory)/'high-priority.layout'
    path.write_text('''<XtraSerializer><property name="Appearance">
      <property name="Row"><property name="BackColor">#aabbcc</property><property name="Options"><property name="HighPriority">true</property></property></property>
      <property name="SelectedRow"><property name="BackColor">#ffff00</property></property>
      <property name="HeaderPanel"><property name="BackColor">#123456</property><property name="Options.HighPriority">true</property></property>
      </property><property name="Columns"><property name="Item1"><property name="FieldName">ID</property><property name="Fixed">Right</property>
      <property name="AppearanceCell"><property name="BackColor">#00ff00</property></property>
      <property name="AppearanceHeader"><property name="BackColor">#654321</property></property>
      </property></property><property name="FormatRules"><property name="Item1"><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[ID] Is Not Null</property><property name="Appearance"><property name="BackColor">#0000ff</property></property></property></property></property></XtraSerializer>''',encoding='utf-8')
    layout=read_tle_layout(path,window.case.headers)
    expect(not layout.warnings,'HighPriority is still reported as unsupported')
    window.apply_tle_layout(layout);settle()
    column=window.case.headers.index('ID')+1;index=window.model.index(0,column)
    expect(index.data(Qt.BackgroundRole).name()=='#aabbcc','High-priority row lost to column or conditional background')
    expect(window.model.headerData(column,Qt.Horizontal,Qt.BackgroundRole).name()=='#123456','High-priority header lost to column appearance')
    for tree in (window.tree,window.tree.right_frozen):
        image=QImage(220,32,QImage.Format_ARGB32);image.fill(Qt.white)
        option=QStyleOptionViewItem();option.rect=image.rect();option.state|=QStyle.State_Selected
        painter=QPainter(image)
        try:tree.itemDelegate().paint(painter,option,index)
        finally:painter.end()
        expect(image.pixelColor(180,5).name()=='#aabbcc','Selected-cell pixels ignore high-priority appearance')
    saved=View.from_json(window.view.to_json())
    expect(saved.layout_styles['row']['high_priority'],'Appearance priority was not serialized')
    window.set_view(View());settle()
    window.set_view(saved);settle()
    expect(window.model.index(0,column).data(Qt.BackgroundRole).name()=='#aabbcc','Restored view lost appearance priority')
