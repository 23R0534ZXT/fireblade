"""Arrange commands around adding evidence, investigating and exporting."""
from PySide6.QtWidgets import QPushButton
from fireblade.ui.language import source_text


def organize_commands(window):
    bar = window.menuBar()
    menus = {source_text(a).replace('&', ''): a.menu() for a in bar.actions()}
    case, analysis, view = menus['Fichier'], menus['Analyse'], menus['Affichage']
    case.setTitle('&Case')
    detection = bar.addMenu('&Détection')
    exports = bar.addMenu('E&xporter')
    bar.removeAction(analysis.menuAction()); bar.insertMenu(menus['Édition'].menuAction(), analysis)
    bar.removeAction(detection.menuAction()); bar.insertMenu(menus['Édition'].menuAction(), detection)
    bar.removeAction(exports.menuAction()); bar.insertMenu(menus['Aide'].menuAction(), exports)

    def move(source, target, labels, anchor=None):
        moved = []
        for label in labels:
            item = next((a for a in source.actions() if source_text(a) == label), None)
            if item is None:continue
            source.removeAction(item)
            if item.property('caseGateEnabled'):
                item.setEnabled(True); item.setProperty('caseGateEnabled', False)
            if anchor is None:target.addAction(item)
            else:target.insertAction(anchor, item)
            moved.append(item)
        return moved

    anchor = analysis.actions()[0]
    imports = move(case, analysis, ['Ouvrir un fichier…', 'Importer un dossier de collecte…', 'Analyser un disque…'], anchor)
    labels = ['Importer un fichier…', 'Parser un dossier…', 'Analyser un disque…']
    for item, label in zip(imports, labels):item.setText(label)
    analysis.insertSeparator(anchor)
    move(case, analysis, ['Ouvrir une analyse…', 'Vider la file d’ouverture', 'Fermer l’onglet', 'Rouvrir le dernier onglet fermé'], anchor)
    move(analysis, view, ['Enregistrer la vue…', 'Charger une vue…', 'Dispositions de la grille',
                         'Règles de coloration…', 'Règles globales', 'Surligner un texte…'])
    move(analysis, detection, ['Analyser la collecte avec Hayabusa'])
    move(analysis, detection, ['Voir le contexte EVTX de l’alerte'])
    detection.addAction('Ouvrir la détection EVTX', lambda: window.workbench.setCurrentWidget(window.detection_panel))
    detection.addAction('Rechercher des IOC', lambda: window.workbench.setCurrentWidget(window.ioc_panel))
    menus['Aide'].addAction('Vérifier les imports et diagnostics…', window.coverage_panel.open)
    exports_list = ['Exporter…', 'Exporter les signets et notes…', 'Exporter le case portable…', 'Créer un rapport HTML / PDF…']
    move(case, exports, exports_list)
    sessions = case.addMenu('Sessions et compatibilité')
    move(case, sessions, ['Ouvrir une session…', 'Enregistrer la session…', 'Compatibilité Timeline Explorer'])
    quit_action = next(a for a in case.actions() if a.text() == 'Quitter')
    case.removeAction(quit_action); case.addSeparator(); case.addAction(quit_action)
    for title, labels in [
        ('Colonnes et tri', ['Colonnes…', 'Hauteur des lignes…', 'Réinitialiser les largeurs', 'Tri sur plusieurs colonnes…', 'Options de tri']),
        ('Groupes', ['Regrouper…', 'Résumés et tri des groupes…', 'Déplier tous les groupes (vue paginée)', 'Replier tous les groupes']),
        ('Vues et dispositions', ['Enregistrer la vue…', 'Charger une vue…', 'Dispositions de la grille', 'Appliquer le profil détecté', 'Réinitialiser la vue']),
        ('Couleurs et règles', ['Règles de coloration…', 'Règles globales', 'Surligner un texte…']),
        ('Navigation', ['Analyses ouvertes…', 'Onglet suivant', 'Onglet précédent', 'Navigation des analyses', 'Détails de la ligne']),
    ]:
        submenu = view.addMenu(title)
        move(view, submenu, labels)
    opened = analysis.addMenu('Gérer les analyses ouvertes')
    move(analysis, opened, ['Vider la file d’ouverture', 'Fermer l’onglet', 'Rouvrir le dernier onglet fermé'])
    window.workbench.addTab(window.detection_panel, 'Détection EVTX')
    # The report describes work in progress; it is also reachable while analysing.
    analysis.addAction('Imports', lambda: window.workbench.setCurrentIndex(1))
    window.collection_toolbar.setWindowTitle('Ajouter des données')
    window.collection_toolbar.addAction(imports[-1])
    for text, callback in [('Dossier…', window.parse_collection), ('Fichier…', window.import_csv),
                           ('Analyser un disque…', window.choose_disk)]:
        button = QPushButton(text)
        button.clicked.connect(callback)
        window.analysis_add_bar.layout().addWidget(button)
    window.update_case_gate()
