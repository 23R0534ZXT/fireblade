"""Render the small, validated appearance dictionaries stored in a View."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QFont,QBrush,QLinearGradient,QGradient


def font_for(style,base=None):
    font=QFont(base) if base else QFont()
    if style.get('font_family'):font.setFamily(style['font_family'])
    if style.get('font_size'):font.setPointSizeF(style['font_size'])
    for key,setter in [('bold',font.setBold),('italic',font.setItalic),('underline',font.setUnderline),('strikeout',font.setStrikeOut)]:
        if key in style:setter(style[key])
    return font


def role_value(style,role):
    if role==Qt.BackgroundRole and 'background' in style:
        if 'background2' not in style:return QColor(style['background'])
        endpoints={'Horizontal':(0,0,1,0),'Vertical':(0,0,0,1),'ForwardDiagonal':(0,0,1,1),'BackwardDiagonal':(1,0,0,1)}
        gradient=QLinearGradient(*endpoints[style.get('gradient','Horizontal')]);gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        gradient.setColorAt(0,QColor(style['background']));gradient.setColorAt(1,QColor(style['background2']))
        return QBrush(gradient)
    if role==Qt.ForegroundRole and 'foreground' in style:return QColor(style['foreground'])
    if role==Qt.FontRole and any(key in style for key in ('font_family','font_size','bold','italic','underline','strikeout')):return font_for(style)
    if role==Qt.TextAlignmentRole and ('horizontal' in style or 'vertical' in style):
        horizontal={'Near':Qt.AlignLeft,'Center':Qt.AlignHCenter,'Far':Qt.AlignRight,'Default':Qt.AlignLeft}
        vertical={'Top':Qt.AlignTop,'Center':Qt.AlignVCenter,'Bottom':Qt.AlignBottom,'Default':Qt.AlignVCenter}
        return horizontal[style.get('horizontal','Default')]|vertical[style.get('vertical','Default')]


def cell_style(view,node,column,row):
    styles=view.layout_styles
    if node.group:return styles.get('group_row',{})
    result=dict(styles.get('row',{}))
    result.update(styles.get('even_row' if row%2 else 'odd_row',{}))
    result.update(styles.get(f'cell:{column-1}',{}))
    return result
