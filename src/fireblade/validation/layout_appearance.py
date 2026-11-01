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
