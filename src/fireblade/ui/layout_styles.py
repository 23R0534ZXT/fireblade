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
    if node.group:return dict(styles.get('group_row',{}))
    result=dict(styles.get('row',{}))
    result.update(styles.get('even_row' if row%2 else 'odd_row',{}))
    result.update(styles.get(f'cell:{column-1}',{}))
    return result


# Decoding is shared across cells and pinned views; never cache per row.
from functools import lru_cache
from PySide6.QtGui import QImage,QPen,QPainter,QPalette,QFontMetrics
from PySide6.QtCore import QRect, QEvent, QObject

@lru_cache(maxsize=8)
def layout_image(encoded):
    from fireblade.core.layout_images import image_bytes
    return QImage.fromData(image_bytes(encoded))


def paint_image(painter,rect,style):
    if not style.get('image'):return
    image=layout_image(style['image']);size=image.size().boundedTo(rect.size())
    image=image.scaled(size,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    align=style.get('image_align','MiddleCenter')
    x=rect.left() if align.endswith('Left') else rect.right()-image.width()+1 if align.endswith('Right') else rect.center().x()-image.width()//2
    y=rect.top() if align.startswith('Top') else rect.bottom()-image.height()+1 if align.startswith('Bottom') else rect.center().y()-image.height()//2
    painter.drawImage(x,y,image)


def paint_border(painter,rect,style):
    if not style.get('border_color'):return
    width=style.get('border_width',1)
    pen=QPen(QColor(style['border_color']),width,{'Solid':Qt.SolidLine,'Dash':Qt.DashLine,'Dot':Qt.DotLine}[style.get('border_style','Solid')])
    painter.setPen(pen);painter.setBrush(Qt.NoBrush)
    inset=width//2;painter.drawRect(rect.adjusted(inset,inset,-1-inset,-1-inset))


def paint_text(painter,rect,text,style,alignment=None):
    flags=alignment or role_value(style,Qt.TextAlignmentRole) or (Qt.AlignLeft|Qt.AlignVCenter)
    if style.get('hotkey')=='Show':flags|=Qt.TextShowMnemonic
    elif style.get('hotkey')=='Hide':flags|=Qt.TextHideMnemonic
    if style.get('word_wrap'):
        flags|=Qt.TextWordWrap
    else:
        mode=style.get('trimming','EllipsisCharacter')
        elide={'None':Qt.ElideNone,'Character':Qt.ElideNone,'Word':Qt.ElideNone,'EllipsisCharacter':Qt.ElideRight,'EllipsisWord':Qt.ElideRight,'EllipsisPath':Qt.ElideMiddle}[mode]
        if mode in ('Word','EllipsisWord') and painter.fontMetrics().horizontalAdvance(text)>rect.width():
            suffix='…' if mode=='EllipsisWord' else ''
            text=painter.fontMetrics().elidedText(text,Qt.ElideRight,max(0,rect.width()-painter.fontMetrics().horizontalAdvance(suffix))).rstrip('…')
            text=(text.rsplit(' ',1)[0] if ' ' in text else text)+suffix
        else:text=painter.fontMetrics().elidedText(text,elide,max(0,rect.width()))
    painter.save();painter.setClipRect(rect,Qt.IntersectClip);painter.drawText(rect,flags,text);painter.restore()


class PanelAppearance(QObject):
    """Paint label panels without changing their drag/drop or text updates."""
    def __init__(self,widget):
        super().__init__(widget);self.widget=widget;self.appearance={};self.base_height=widget.minimumHeight()
        widget.installEventFilter(self)

    def set_style(self,style):
        self.appearance=dict(style)
        height=QFontMetrics(font_for(style,self.widget.font())).height()+8 if style else self.base_height
        self.widget.setMinimumHeight(max(self.base_height,height));self.widget.update()

    def eventFilter(self,widget,event):
        if event.type()!=QEvent.Paint or not self.appearance:return False
        style=self.appearance;painter=QPainter(widget);rect=widget.rect()
        background=role_value(style,Qt.BackgroundRole)
        if background is not None:painter.fillRect(rect,background)
        paint_image(painter,rect,style)
        painter.setFont(font_for(style,widget.font()))
        painter.setPen(QColor(style['foreground']) if 'foreground' in style else widget.palette().color(QPalette.WindowText))
        paint_text(painter,rect.adjusted(4,2,-4,-2),widget.text(),style)
        paint_border(painter,rect,style);painter.end();return True


def apply_panel_styles(window):
    for role,name in [('group_panel','groups_label'),('footer_panel','count_label'),('view_caption','source')]:
        widget=getattr(window,name)
        if not hasattr(widget,'_tle_appearance'):widget._tle_appearance=PanelAppearance(widget)
        widget._tle_appearance.set_style(window.view.layout_styles.get(role,{}))
    for role,name in [('preview','details'),('filter_panel','filters'),('find_panel','search')]:
        apply_control_style(getattr(window,name),window.view.layout_styles.get(role,{}))
    for tree in (window.tree,window.tree.frozen,window.tree.right_frozen):
        if not hasattr(tree,'_tle_empty'):tree._tle_empty=EmptyAppearance(tree)
        tree._tle_empty.appearance=window.view.layout_styles.get('empty',{})
        tree.viewport().update()


class EmptyAppearance(QObject):
    def __init__(self,tree):
        super().__init__(tree);self.tree=tree;self.appearance={};tree.viewport().installEventFilter(self)

    def eventFilter(self,widget,event):
        if event.type()!=QEvent.Paint or not self.appearance or self.tree.model().rowCount():return False
        painter=QPainter(widget);rect=widget.rect();style=self.appearance
        background=role_value(style,Qt.BackgroundRole)
        painter.fillRect(rect,background if background is not None else widget.palette().brush(QPalette.Base))
        paint_image(painter,rect,style);paint_border(painter,rect,style);painter.end();return True


_image_directory=None

def image_url(encoded):
    """Qt stylesheets require an image URL; keep the validated raster in a private temp dir."""
    import hashlib
    from pathlib import Path
    from PySide6.QtCore import QTemporaryDir
    global _image_directory
    if _image_directory is None:_image_directory=QTemporaryDir()
    if not _image_directory.isValid():raise ValueError('Répertoire temporaire des images indisponible')
    path=Path(_image_directory.path())/(hashlib.sha256(encoded.encode('ascii')).hexdigest()+'.png')
    if not path.exists() and not layout_image(encoded).save(str(path),'PNG'):raise ValueError('Image de panneau non enregistrable')
    return path.as_posix()


def apply_control_style(widget,style):
    """Retain native editing/selection for the analogous search/filter/detail controls."""
    if not hasattr(widget,'_tle_base'):
        widget._tle_base=(QPalette(widget.palette()),widget.font(),widget.styleSheet())
    palette,font,stylesheet=widget._tle_base
    palette=QPalette(palette)
    for role,key in [(QPalette.Base,'background'),(QPalette.Text,'foreground')]:
        if key in style:palette.setBrush(role,QBrush(role_value(style,Qt.BackgroundRole if key=='background' else Qt.ForegroundRole)))
    widget.setPalette(palette);widget.setFont(font_for(style,font))
    if style.get('border_color'):
        line={'Solid':'solid','Dash':'dashed','Dot':'dotted'}[style.get('border_style','Solid')]
        stylesheet+=f"; border: {style.get('border_width',1)}px {line} {style['border_color']};"
    if 'background' in style:
        if 'background2' in style:
            endpoints={'Horizontal':(0,0,1,0),'Vertical':(0,0,0,1),'ForwardDiagonal':(0,0,1,1),'BackwardDiagonal':(1,0,0,1)}
            x1,y1,x2,y2=endpoints[style.get('gradient','Horizontal')]
            stylesheet+=f"; background: qlineargradient(x1:{x1}, y1:{y1}, x2:{x2}, y2:{y2}, stop:0 {style['background']}, stop:1 {style['background2']});"
        else:stylesheet+=f"; background: {style['background']};"
    if 'foreground' in style:stylesheet+=f"; color: {style['foreground']};"
    if style.get('image') and not isinstance(widget,AppearanceTextEdit):
        align=style.get('image_align','MiddleCenter')
        vertical='top' if align.startswith('Top') else 'bottom' if align.startswith('Bottom') else 'center'
        horizontal='left' if align.endswith('Left') else 'right' if align.endswith('Right') else 'center'
        stylesheet+=f'; background-image: url("{image_url(style["image"])}"); background-repeat: no-repeat; background-attachment: fixed; background-position: {vertical} {horizontal};'
    if hasattr(widget,'setWordWrap'):widget.setWordWrap(style.get('word_wrap',False))
    if isinstance(widget,AppearanceTextEdit):widget.setLineWrapMode(QPlainTextEdit.WidgetWidth if style.get('word_wrap',True) else QPlainTextEdit.NoWrap)
    widget._tle_style=dict(style)
    if isinstance(widget,AppearanceTextEdit) and style.get('image'):
        stylesheet+='; background: transparent;'
    widget.setStyleSheet(stylesheet)
    if hasattr(widget,'setAlignment'):
        alignment=role_value(style,Qt.TextAlignmentRole)
        widget.setAlignment(alignment or (Qt.AlignLeft|Qt.AlignVCenter))


from PySide6.QtWidgets import QPlainTextEdit

class AppearanceTextEdit(QPlainTextEdit):
    def paintEvent(self,event):
        style=getattr(self,'_tle_style',{})
        if style.get('image'):
            painter=QPainter(self.viewport())
            background=role_value(style,Qt.BackgroundRole)
            painter.fillRect(self.viewport().rect(),background if background is not None else self.palette().brush(QPalette.Base))
            paint_image(painter,self.viewport().rect(),style);painter.end()
        super().paintEvent(event)
