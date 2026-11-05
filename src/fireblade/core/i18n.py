"""Interface language.

French is the source language: the menus are written in French in the code, and
this module substitutes the display text. English is the default, French stays
available in the preferences.

A label missing from the table is shown as written, so a new menu entry appears
in French until it is translated — never blank, never a raw key.
"""

EN = {
    "Nouveau case…": "New case…",
    "Cases…": "Cases…",
    "Enregistrer le case": "Save case",
    "Fermer le case": "Close case",
    "Historique et récupération du case…": "Case history and recovery…",
    "Importer un case portable…": "Import a portable case…",
    "Sauvegarde automatique du case (2 min)": "Case autosave (2 min)",
    "Sessions et compatibilité": "Sessions and compatibility",
    "Ouvrir une session…": "Open a session…",
    "Enregistrer la session…": "Save the session…",
    "Compatibilité Timeline Explorer": "Timeline Explorer compatibility",
    "Importer avec un plugin TLE (.NET)…": "Import with a TLE plugin (.NET)…",
    "Importer les préférences Timeline Explorer…": "Import Timeline Explorer preferences…",
    "Importer une session Timeline Explorer…": "Import a Timeline Explorer session…",
    "Exporter une session TLE (sources et signets)…": "Export a TLE session (sources and bookmarks)…",
    "Quitter": "Quit",
    "Importer un fichier…": "Import a file…",
    "Parser un dossier…": "Parse a folder…",
    "Analyser un disque…": "Analyze a disk…",
    "Ouvrir une analyse…": "Open an analysis…",
    "Calculs et conversions": "Calculations and conversions",
    "Charger des fonctions .NET…": "Load .NET functions…",
    "Convertir une date…": "Convert a date…",
    "Ajouter une colonne calculée…": "Add a computed column…",
    "Contrôler les colonnes dérivées…": "Check derived columns…",
    "Afficher la cellule / JSON…": "Show cell / JSON…",
    "Provenance et SHA-256…": "Provenance and SHA-256…",
    "Interrompre la requête": "Stop the query",
    "Chronologie & corrélations": "Timeline & correlations",
    "Gérer les analyses ouvertes": "Manage open analyses",
    "Vider la file d’ouverture": "Clear the open queue",
    "Fermer l’onglet": "Close the tab",
    "Rouvrir le dernier onglet fermé": "Reopen the last closed tab",
    "Imports": "Imports",
    "Analyser la collecte avec Hayabusa": "Analyze the collection with Hayabusa",
    "Voir le contexte EVTX de l’alerte": "Show the alert’s EVTX context",
    "Ouvrir la détection EVTX": "Open EVTX detection",
    "Rechercher des IOC": "Hunt IOCs",
    "Copier les lignes": "Copy rows",
    "Signet / note…": "Bookmark / note…",
    "Marquer la sélection": "Mark the selection",
    "Ajouter une note à la sélection…": "Add a note to the selection…",
    "Remplacer les notes de la sélection…": "Replace the selection’s notes…",
    "Retirer les signets de la sélection": "Remove bookmarks from the selection",
    "Palette de commandes…": "Command palette…",
    "Messages…": "Messages…",
    "Préférences…": "Preferences…",
    "Profils et compatibilité": "Profiles and compatibility",
    "Profils et plugins…": "Profiles and plugins…",
    "Légende des supertimelines…": "Supertimeline legend…",
    "Organiser l’espace de travail": "Organize the workspace",
    "Regrouper l’arbre par": "Group the tree by",
    "Disque → partition → dossiers": "Disk → partition → folders",
    "Collecte → type d’artefact": "Collection → artifact type",
    "Liste des analyses par collecte": "Analysis list by collection",
    "Position de l’arbre": "Tree position",
    "À gauche": "Left",
    "À droite": "Right",
    "Navigation des analyses": "Analysis navigation",
    "Détails de la ligne": "Row details",
    "Position des détails de ligne": "Row details position",
    "En bas": "Bottom",
    "En haut": "Top",
    "Déplier tout l’arbre": "Expand the whole tree",
    "Replier tout l’arbre": "Collapse the whole tree",
    "Barres d’outils": "Toolbars",
    "Fichier": "File",
    "Ajouter des données": "Add data",
    "Animation au démarrage": "Startup animation",
    "Colonnes et tri": "Columns and sorting",
    "Colonnes…": "Columns…",
    "Hauteur des lignes…": "Row height…",
    "Réinitialiser les largeurs": "Reset widths",
    "Tri sur plusieurs colonnes…": "Multi-column sort…",
    "Options de tri": "Sort options",
    "Groupes": "Groups",
    "Regrouper…": "Group…",
    "Résumés et tri des groupes…": "Group summaries and sorting…",
    "Déplier tous les groupes (vue paginée)": "Expand all groups (paged view)",
    "Replier tous les groupes": "Collapse all groups",
    "Vues et dispositions": "Views and layouts",
    "Enregistrer la vue…": "Save the view…",
    "Charger une vue…": "Load a view…",
    "Dispositions de la grille": "Grid layouts",
    "Exporter la disposition…": "Export the layout…",
    "Importer une disposition…": "Import a layout…",
    "Appliquer le profil détecté": "Apply the detected profile",
    "Réinitialiser la vue": "Reset the view",
    "Couleurs et règles": "Colours and rules",
    "Règles de coloration…": "Colour rules…",
    "Règles globales": "Global rules",
    "Modifier…": "Edit…",
    "Recharger depuis le disque": "Reload from disk",
    "Importer et remplacer…": "Import and replace…",
    "Exporter…": "Export…",
    "Appliquer à cette vue": "Apply to this view",
    "Surligner un texte…": "Highlight text…",
    "Navigation": "Navigation",
    "Analyses ouvertes…": "Open analyses…",
    "Onglet suivant": "Next tab",
    "Onglet précédent": "Previous tab",
    "Espace de travail": "Workspace",
    "Analyse": "Analysis",
    "Chronologie seule": "Timeline only",
    "Analyse + chronologie": "Analysis + timeline",
    "Rétablir les panneaux": "Restore the panels",
    "Enregistrer la disposition": "Save the layout",
    "Détacher / afficher un panneau": "Detach / show a panel",
    "Analyses": "Analyses",
    "Cases": "Cases",
    "Chasse IOC": "IOC hunting",
    "Détection EVTX": "EVTX detection",
    "Artefacts": "Artifacts",
    "&Fichier": "&File",
    "&Édition": "&Edit",
    "&Affichage": "&View",
    "Fi&ltres": "Fi&lters",
    "A&nalyse": "A&nalysis",
    "A&ide": "H&elp",
    "&Détection": "&Detection",
}

LANGUAGES = ("en", "fr")
DEFAULT = "en"
NAMES = {"en": "English", "fr": "Français"}

_language = DEFAULT


def current_language():
    return _language


def fallback_language():
    """What a stored or malformed code becomes."""
    return DEFAULT


def set_language(code):
    global _language
    if code not in LANGUAGES:
        raise ValueError(f"Langue inconnue : {code!r}")
    _language = code
    return _language


def translate(text):
    """Display text for the current language; French is the source."""
    if _language == "fr":
        return text
    return EN.get(text, text)
