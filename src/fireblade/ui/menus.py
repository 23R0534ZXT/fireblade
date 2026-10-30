"""Context menus for the grid. Actions delegate to the window's existing commands."""
from PySide6.QtWidgets import QApplication, QMenu


def header_menu(window, section):
    if not window.case or window.busy or not 1 <= section <= len(window.case.headers):
        return None
    column = section - 1
    menu = QMenu(window)
    menu.addAction("Trier par ordre croissant", lambda: window.set_sort(column, False))
    menu.addAction("Trier par ordre décroissant", lambda: window.set_sort(column, True))
    typed = menu.addMenu("Type de tri")
    for label, kind in [("Texte", "text"), ("Nombre", "number"), ("Date ISO", "timestamp")]:
        item = typed.addAction(label, lambda checked=False, value=kind: window.set_sort(column, window.view.descending, value))
        item.setCheckable(True)
        item.setChecked(window.view.sort_type == kind)
    menu.addAction("Tri sur plusieurs colonnes…", window.edit_sort)
    menu.addSeparator()
    menu.addAction("Grouper par cette colonne", lambda: window.group_column(column))
    if column not in window.view.groups:
        menu.addAction("Ajouter au groupement", lambda: window.group_column(column, append=True))
    else:
        menu.addAction("Retirer du groupement", lambda: window.group_column(column, remove=True))
    menu.addSeparator()
    menu.addAction("Filtrer cette colonne…", lambda: window.add_filter(column))
    menu.addSeparator()
    menu.addAction("Masquer cette colonne", lambda: window.tree.setColumnHidden(section, True))
    menu.addAction("Choisir les colonnes…", window.columns)
    return menu


def cell_menu(window, index):
    if not window.model or window.busy or not index.isValid():
        return None
    node = window.model.node(index)
    if node.group:
        return None
    row_id = node.values[0]
    menu = QMenu(window)
    if index.column() > 0:
        column, value = index.column() - 1, node.values[index.column()]
        def show_cell():
            window.tree.setCurrentIndex(index)
            window.cell_details()
        menu.addAction("Afficher la cellule / JSON…", show_cell)
        menu.addAction("Copier la valeur", lambda: QApplication.clipboard().setText("" if value is None else str(value)))
        menu.addAction("Filtrer sur cette valeur", lambda: window.filter_value(column, value))
        menu.addAction("Exclure cette valeur", lambda: window.filter_value(column, value, exclude=True))
        menu.addSeparator()
    menu.addAction("Copier les lignes sélectionnées", window.copy_rows)
    menu.addAction("Signet / note…", lambda: window.edit_bookmark(row_id))
    menu.addSeparator()
    menu.addAction("Marquer la sélection", lambda: window.annotate_selection("mark"))
    menu.addAction("Ajouter une note à la sélection…", lambda: window.annotate_selection("append"))
    menu.addAction("Retirer les signets de la sélection", lambda: window.annotate_selection("remove"))
    return menu
