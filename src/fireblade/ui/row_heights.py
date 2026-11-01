"""Shared row heights for the bounded model window and all pinned views."""
from PySide6.QtCore import Qt,QRect,QTimer
from PySide6.QtGui import QFontMetrics
from copy import deepcopy
from PySide6.QtWidgets import QAbstractItemView,QCheckBox,QDialog,QDialogButtonBox,QFormLayout,QSpinBox

from fireblade.ui.layout_styles import merge_styles,font_for


class RowHeights:
    def __init__(self,tree):
        self.tree=tree
        self.columns=()
        self.configuration=None
        self.revision=0
        self.pending=False

    def schedule(self,*_):
        if self.pending:return
        self.pending=True
        QTimer.singleShot(0,self.configure)

    def geometry(self):
        tree=self.tree;model=tree.model()
        if model is None:return ()
        return tuple((column,max(1,tree.frozen_for(column).columnWidth(column)-8))
            for column in range(model.columnCount()) if column in tree.all_pinned or not tree.isColumnHidden(column))

    def configure(self):
        self.pending=False
        tree=self.tree;model=tree.model()
        if model is None:
            self.configuration=None;self.columns=();return
        view=model.view;columns=self.geometry()
        configuration=(id(model),model.generation,columns,tree.font().toString(),view.auto_row_height,view.row_height,view.group_row_height,model.date_format,model.date_pattern)
        if configuration==self.configuration:return
        self.configuration=configuration;self.columns=columns;self.revision+=1
        uniform=not view.auto_row_height and not (view.group_row_height and view.group_row_height!=view.row_height)
        for panel in (tree,*tree.frozen_views):
            panel.setUniformRowHeights(uniform)
            panel.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel if view.auto_row_height or view.row_height or view.group_row_height else QAbstractItemView.ScrollPerItem)
        for panel in (tree,*tree.frozen_views):
            panel.doItemsLayout();panel.viewport().update()

    def height(self,index):
        tree=self.tree;model=index.model();node=model.node(index);view=model.view
        key=(self.revision,tree.font().toString())
        if node.height_key==key:return node.height
        columns=self.columns or self.geometry()
        minimum=view.group_row_height if node.group and not node.footer else view.row_height
        height=max(22,minimum,tree.fontMetrics().height()+6)
        for column,width in columns:
            cell=index.siblingAtColumn(column)
            style=merge_styles(*model.appearance_layers(cell))
            effective=cell.data(Qt.FontRole)
            font=effective.resolve(tree.font()) if effective is not None else font_for(style,tree.font())
            variants=[font]
            for role in ('selected_row','focused_row','focused_cell'):
                state=view.layout_styles.get(role,{})
                if any(key in state for key in ('font_size','font_family','bold','italic')):variants.append(font_for(state,font))
            for variant in variants:
                metrics=QFontMetrics(variant)
                height=max(height,metrics.height()+6)
                if style.get('word_wrap'):
                    text=str(cell.data(Qt.DisplayRole) or '')
                    # Measure only cells already held by the bounded Qt model.
                    # All three views use this same width, font and cached result.
                    rect=metrics.boundingRect(QRect(0,0,width,16777215),Qt.TextWordWrap|Qt.AlignLeft,text)
                    height=max(height,rect.height()+8)
        node.height=height;node.height_key=key
        return height


class RowHeightDialog(QDialog):
    def __init__(self,view,parent=None):
        super().__init__(parent)
        self.view=deepcopy(view)
        self.setWindowTitle('Hauteur des lignes')
        form=QFormLayout(self)
        self.auto=QCheckBox('Adapter la hauteur au texte affiché')
        self.auto.setChecked(view.auto_row_height)
        self.wrap=QCheckBox('Renvoyer le texte à la ligne par défaut')
        self.wrap.setChecked(view.layout_styles.get('row',{}).get('word_wrap',False))
        self.auto.toggled.connect(lambda checked:self.wrap.setChecked(True) if checked else None)
        form.addRow(self.auto);form.addRow(self.wrap)
        self.heights={}
        for label,key in [('Lignes (pixels)','row_height'),('En-têtes de groupes (pixels)','group_row_height'),('En-têtes de colonnes (pixels)','header_height')]:
            box=QSpinBox();box.setRange(0,10000);box.setSpecialValueText('Par défaut');box.setValue(getattr(view,key))
            form.addRow(label,box);self.heights[key]=box
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)

    def accept(self):
        self.view.auto_row_height=self.auto.isChecked()
        for key,box in self.heights.items():setattr(self.view,key,box.value())
        if self.wrap.isChecked() or 'word_wrap' in self.view.layout_styles.get('row',{}):
            self.view.layout_styles.setdefault('row',{})['word_wrap']=self.wrap.isChecked()
        super().accept()
