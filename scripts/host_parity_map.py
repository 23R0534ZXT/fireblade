"""Build the Host parity map from the desktop's own command inventory.

One entry per label `scripts/parity_inventory.py` finds in the Qt sources, with
the Host edition's status for it. The file is the source of truth:
`docs/development/HOST-PARITY.md` is rendered from it, and
`tests/web/test_host_parity.py` refuses a claim that points at no test.

Statuses
  covered  — present in the browser, and named by a test that exists
  declared — cannot or must not exist behind a browser, with the reason
  todo     — real desktop work the Host edition does not do yet, with a plan
"""

T = "covered"
D = "declared"
Q = "todo"

# label: (kind, status, where, test, reason, plan)
COMMANDS = {
    # ---- menu containers: they carry commands, they are not commands ----
    "&Affichage": ("container", D, "", "", "The menu bar of the desktop window.", ""),
    "&Fichier": ("container", D, "", "", "The menu bar of the desktop window.", ""),
    "&Édition": ("container", D, "", "", "The menu bar of the desktop window.", ""),
    "A&ide": ("container", D, "", "", "The menu bar of the desktop window.", ""),
    "A&nalyse": ("container", D, "", "", "The menu bar of the desktop window.", ""),
    "Aide": ("container", D, "", "", "The menu bar of the desktop window.", ""),
    "Fi&ltres": ("container", D, "", "", "The menu bar of the desktop window, HTML-escaped.", ""),
    "E&xporter": ("container", D, "", "", "A submenu of the desktop window.", ""),
    "Affichage": ("container", D, "", "", "A submenu of the desktop window.", ""),
    "Espace de travail": ("container", D, "", "", "A submenu of the desktop window.", ""),
    "1. Quand ?": ("container", D, "", "", "A step caption inside the desktop's rule dialog.", ""),
    "2. Appliquer à": ("container", D, "", "", "A step caption inside the desktop's rule dialog.", ""),
    "3. Apparence": ("container", D, "", "", "A step caption inside the desktop's rule dialog.", ""),

    # ---- parameters: values a dialog offers, not actions ----
    "Active": ("parameter", D, "", "", "A value of a condition, not a command.", ""),
    "Inactive": ("parameter", D, "", "", "A value of a condition, not a command.", ""),
    "En bas": ("parameter", D, "", "", "A position value, not a command.", ""),
    "En haut": ("parameter", D, "", "", "A position value, not a command.", ""),
    "À droite": ("parameter", D, "", "", "A position value, not a command.", ""),
    "Dans l’en-tête du groupe": ("parameter", D, "", "", "A placement value of a grouped chart.", ""),
    "Par groupe": ("parameter", D, "", "", "A placement value of a grouped chart.", ""),
    "Pied global": ("parameter", D, "", "", "A placement value of a grouped chart.", ""),
    "Toute la ligne": ("parameter", D, "", "", "A scope value of a note.", ""),
    "Ordre source": ("parameter", D, "", "", "A sort value, not a command.", ""),
    "Type de tri": ("parameter", D, "", "", "A sort value, not a command.", ""),
    "Détection automatique": ("parameter", D, "", "", "A profile value of the import.", ""),
    "Valeurs du champ cible": ("parameter", D, "", "", "A value list inside the pivot dialog.", ""),
    "Colonne de valeurs": ("parameter", D, "", "", "A field of the pivot dialog.", ""),
    "champs de reconnaissance ·": ("parameter", D, "", "", "A counter label of the profiles panel.", ""),
    "dates ·": ("parameter", D, "", "", "A counter label of the profiles panel.", ""),
    "booléens": ("parameter", D, "", "", "A counter label of the profiles panel.", ""),
    "niveaux": ("parameter", D, "", "", "A level list, not a command.", ""),
    "active": ("parameter", D, "", "", "A status value, not a command.", ""),
    "all": ("parameter", D, "", "", "A scope value, not a command.", ""),
    "append": ("parameter", D, "", "", "A parameter value of a rule, not a command.", ""),
    "artifacts": ("parameter", D, "", "", "A layout identifier, not a command.", ""),
    "auto": ("parameter", D, "", "", "An encoding value, not a command.", ""),
    "bottom": ("parameter", D, "", "", "A position value, not a command.", ""),
    "case": ("parameter", D, "", "", "A scope value, not a command.", ""),
    "dark": ("parameter", D, "", "", "A palette value, not a command.", ""),
    "details": ("parameter", D, "", "", "A panel identifier, not a command.", ""),
    "label": ("parameter", D, "", "", "A field name, not a command.", ""),
    "left": ("parameter", D, "", "", "A position value, not a command.", ""),
    "light": ("parameter", D, "", "", "A palette value, not a command.", ""),
    "mark": ("parameter", D, "", "", "A rule operation, not a command.", ""),
    "name": ("parameter", D, "", "", "A field name, not a command.", ""),
    "path": ("parameter", D, "", "", "A field name, not a command.", ""),
    "process": ("parameter", D, "", "", "A field name, not a command.", ""),
    "remove": ("parameter", D, "", "", "A rule operation, not a command.", ""),
    "replace": ("parameter", D, "", "", "A rule operation, not a command.", ""),
    "right": ("parameter", D, "", "", "A position value, not a command.", ""),
    "started": ("parameter", D, "", "", "A field name of a saved hunt, not a command.", ""),
    "status": ("parameter", D, "", "", "A field name, not a command.", ""),
    "top": ("parameter", D, "", "", "A position value, not a command.", ""),

    # ---- covered: the browser does it, and a test says where ----
    "&Détection": (T, T, "Detection menu and the EVTX detection tab.",
                   "test_detection_refuses_with_a_readable_reason", "", ""),
    "Actions": (T, T, "Actions & tracking tab.", "test_tracking_actions_are_created_updated_and_exported", "", ""),
    "Actions & suivi": (T, T, "Actions & tracking tab.", "test_tracking_actions_are_created_updated_and_exported", "", ""),
    "Afficher la cellule / JSON…": (T, T, "Row menu > Show the whole cell…", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Ajouter au groupement": (T, T, "Row menu > Group by this column, and the Group… dialog.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Ajouter une note à la cellule…": (T, T, "Row details > note, per column.", "test_bookmarks_and_cell_notes_round_trip", "", ""),
    "Ajouter une note à la sélection…": (T, T, "Row details note applied to the whole selection.", "test_the_grid_selects_a_range_and_a_selection", "", ""),
    "Analyses": (T, T, "Analyses tab and the analysis tree.", "test_analysis_columns_and_rows", "", ""),
    "Apparence": (T, T, "Display settings: text size, row height, palette.", "test_display_layout_is_saved_in_the_analysis", "", ""),
    "Artefact actif": (D, D, "", "", "The desktop's artifact tree is a window layout; the browser lists the analyses of the case instead.", ""),
    "Artefacts": (D, D, "", "", "The desktop's artifact tree is a window layout; the browser lists the analyses of the case instead.", ""),
    "Attack graph": (T, T, "Attack graph tab, with the ATT&CK layer and the PNG.", "test_the_attack_graph_refuses_on_an_empty_case", "", ""),
    "Automatique (BOM)": (T, T, "Import dialog: CSV options, encoding.", "test_preview_reads_the_chosen_encoding_and_separator", "", ""),
    "Basculer l’affichage booléen": (T, T, "Column manager and display settings.", "test_display_layout_is_saved_in_the_analysis", "", ""),
    "Calculs et conversions": (T, T, "Derived columns dialog.", "test_a_derived_column_is_added_to_the_analysis", "", ""),
    "Case courant": (T, T, "The open case in the toolbar.", "test_cases_are_listed", "", ""),
    "Cases": (T, T, "Cases tab.", "test_cases_are_listed", "", ""),
    "Chasse IOC": (T, T, "IOC hunting tab.", "test_an_ioc_scan_matches_the_pasted_indicator", "", ""),
    "Chasses enregistrées…": (T, T, "IOC hunting > Saved hunts…", "test_an_ioc_hunt_is_saved_and_replayed", "", ""),
    "Choisir les colonnes…": (T, T, "Columns… dialog.", "test_display_layout_is_saved_in_the_analysis", "", ""),
    "Chronologie & corrélations": (T, T, "Timeline & correlations tab.", "test_the_timeline_counts_the_dated_rows", "", ""),
    "Clair": (T, T, "Display settings > palette.", "test_display_layout_is_saved_in_the_analysis", "", ""),
    "Sombre": (T, T, "Display settings > palette.", "test_display_layout_is_saved_in_the_analysis", "", ""),
    "Client et mission…": (T, T, "Client report dialog: title and description.", "test_the_client_report_is_written_and_served_back", "", ""),
    "Compatibilité Timeline Explorer": (Q, Q, "", "", "",
                                        "Upload a .NET Timeline Explorer reader, inspect the readers it declares, and run a source through it."),
    "Copier la valeur": (T, T, "Row menu > Copy this value.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Copier la valeur complète": (T, T, "Show the whole cell… then Copy.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Copier les lignes sélectionnées": (T, T, "Row menu > Copy the selected rows, over the selection.", "test_the_grid_selects_a_range_and_a_selection", "", ""),
    "Corréler dans toutes les analyses": (T, T, "Global search across every analysis of the case.", "test_a_global_search_finds_the_value_and_names_its_analysis", "", ""),
    "Couche ATT&CK Navigator…": (T, T, "Attack graph > Export an ATT&CK layer…", "test_the_attack_graph_refuses_on_an_empty_case", "", ""),
    "Créer une règle pour cette valeur…": (T, T, "Row menu > Colour rule for this value…", "test_colour_rules_round_trip", "", ""),
    "Dispositions de la grille": (T, T, "Column layout remembered in the analysis.", "test_display_layout_is_saved_in_the_analysis", "", ""),
    "Désépingler la colonne": (T, T, "Row menu > Pin / unpin this column.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Épingler la colonne": (T, T, "Row menu > Pin / unpin this column.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Épingler à gauche": (T, T, "Pinned columns freeze on the left.", "test_display_layout_is_saved_in_the_analysis", "", ""),
    "Détails de la ligne": (T, T, "Row details panel.", "test_the_grid_selects_a_range_and_a_selection", "", ""),
    "Détection EVTX": (T, T, "EVTX detection tab.", "test_detection_refuses_with_a_readable_reason", "", ""),
    "Ouvrir la détection EVTX": (T, T, "EVTX detection tab.", "test_detection_refuses_with_a_readable_reason", "", ""),
    "Exclure cette valeur": (T, T, "Row menu > Exclude this value.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Exporter PNG…": (T, T, "Attack graph > Export PNG…", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Exporter le suivi…": (T, T, "Actions & tracking > Export CSV.", "test_actions_export_is_a_csv", "", ""),
    "Expression ET / OU / NON · ouvrir l’éditeur pour modifier": (T, T, "Advanced filter…, with nested groups.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Filtrer cette colonne…": (T, T, "The filter row under the headers.", "test_search_and_column_filter", "", ""),
    "Filtrer sur ce champ": (T, T, "The filter row under the headers.", "test_search_and_column_filter", "", ""),
    "Filtrer sur cette valeur": (T, T, "Row menu > Filter on this value.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Filtrer une date…": (T, T, "Advanced filter on a timestamp column, or group it by interval.", "test_search_and_column_filter", "", ""),
    "Grouper par cette colonne": (T, T, "Row menu > Group by this column, and the Group… dialog.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Hayabusa + AI": (T, T, "Hayabusa + AI tab; no model is connected and the tab says so.", "test_detection_refuses_with_a_readable_reason", "", ""),
    "Importer une liste…": (T, T, "IOC hunting: paste indicators.", "test_an_ioc_scan_matches_the_pasted_indicator", "", ""),
    "Imports": (T, T, "Imports tab, file by file, with the reader and the reason.", "test_the_import_history_lists_the_files_of_the_case", "", ""),
    "Indicateurs": (T, T, "IOC hunting results.", "test_an_ioc_scan_matches_the_pasted_indicator", "", ""),
    "Machines et comptes": (T, T, "Attack graph inputs.", "test_the_attack_graph_refuses_on_an_empty_case", "", ""),
    "Marquer la sélection": (T, T, "Row menu > Mark the selection.", "test_the_grid_selects_a_range_and_a_selection", "", ""),
    "Retirer les signets de la sélection": (T, T, "Row menu > Remove marks from the selection.", "test_the_grid_selects_a_range_and_a_selection", "", ""),
    "Masquer cette colonne": (T, T, "Row menu > Hide this column, and Columns…", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Modifier…": (T, T, "Actions & tracking > edit.", "test_tracking_actions_are_created_updated_and_exported", "", ""),
    "Qu’est-ce qui a lancé {} ?": (T, T, "Row menu > What launched this process?", "test_pivot_answers_what_launched_a_process", "", ""),
    "Recherche globale": (T, T, "Global search in the toolbar.", "test_a_global_search_finds_the_value_and_names_its_analysis", "", ""),
    "Rechercher dans tous les artefacts": (T, T, "Global search in the toolbar.", "test_a_global_search_finds_the_value_and_names_its_analysis", "", ""),
    "Rechercher des IOC": (T, T, "IOC hunting tab.", "test_an_ioc_scan_matches_the_pasted_indicator", "", ""),
    "Regrouper les dates par": (T, T, "Group… with a date interval.", "test_search_and_column_filter", "", ""),
    "Retirer": (T, T, "Actions & tracking > remove.", "test_tracking_actions_are_created_updated_and_exported", "", ""),
    "Retirer du groupement": (T, T, "Group… > Remove grouping.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Règles": (T, T, "Colour rules…", "test_colour_rules_round_trip", "", ""),
    "Règles globales": (T, T, "Colour rules…, stored with the analysis.", "test_colour_rules_round_trip", "", ""),
    "Signet / note…": (T, T, "Row details: bookmark note.", "test_bookmarks_and_cell_notes_round_trip", "", ""),
    "Tous les artefacts": (T, T, "Analyses tree: every analysis of the case.", "test_analysis_columns_and_rows", "", ""),
    "Tous les cases": (T, T, "Cases tab.", "test_cases_are_listed", "", ""),
    "Tri sur plusieurs colonnes…": (T, T, "Shift-click a header for a second sort key.", "test_search_and_column_filter", "", ""),
    "Trier par ordre croissant": (T, T, "Row menu > Sort ascending, or a header click.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Trier par ordre décroissant": (T, T, "Row menu > Sort descending, or a header click.", "test_the_row_menu_offers_every_cell_action", "", ""),
    "Éditer la note de la cellule…": (T, T, "Row details > note, per column.", "test_bookmarks_and_cell_notes_round_trip", "", ""),
    "Éditer la note de la sélection…": (T, T, "Row details note applied to the whole selection.", "test_the_grid_selects_a_range_and_a_selection", "", ""),
    "Vérifier les imports et diagnostics…": (T, T, "Imports tab, with the Not imported / Error filters.", "test_the_import_history_lists_the_files_of_the_case", "", ""),

    # ---- declared: a browser has no system explorer, no window manager ----
    "Afficher dans l’Explorateur": (D, D, "", "", "There is no system file manager behind a browser, and the server's folders are not the analyst's machine.", ""),
    "Ouvrir le dossier parent": (D, D, "", "", "There is no system file manager behind a browser.", ""),
    "Ouvrir avec…": (D, D, "", "", "The server's file associations are not the analyst's.", ""),
    "Animation au démarrage": (D, D, "", "", "A browser tab has no splash screen; the desktop keeps its ident.", ""),
    "Barres d’outils": (D, D, "", "", "The browser owns the window chrome; the toolbar is fixed and always visible.", ""),
    "Détacher / afficher un panneau": (D, D, "", "", "Window management does not exist in a browser tab; the panels are fixed.", ""),
    "Détacher le panneau": (D, D, "", "", "Window management does not exist in a browser tab.", ""),
    "Rattacher": (D, D, "", "", "Window management does not exist in a browser tab.", ""),
    "Organiser l’espace de travail": (D, D, "", "", "The workspace presets rearrange docks; a browser tab has none.", ""),
    "Position de l’arbre": (D, D, "", "", "A dock position; the browser has one layout.", ""),
    "Position des détails de ligne": (D, D, "", "", "A dock position; the browser has one layout.", ""),
    "Regrouper l’arbre par": (D, D, "", "", "The desktop's artifact tree is a window layout the browser does not have.", ""),
    "Guide de l’espace de travail": (D, D, "", "", "The guides are desktop markdown windows; the Host edition documents itself in Help > About.", ""),
    "New conversation": (D, D, "", "", "The AI assistant is not connected in this edition, on purpose.", ""),

    # ---- todo: real work, with a plan ----
    "(date et heure dans la même colonne)": (T, T, "Timeline: the date selector of each analysis, or a named column.",
                                              "test_the_timeline_reads_a_date_the_way_the_analyst_chooses", "", ""),
    "Date + heure (colonnes séparées)": (T, T, "Timeline: the 'date + time (separate columns)' option of a source.",
                                         "test_the_timeline_can_read_two_columns_as_one_date", "", ""),
    "Sans date / corrélation uniquement": (T, T, "Timeline: the 'no date (correlation only)' option of a source.",
                                           "test_the_timeline_reads_a_date_the_way_the_analyst_chooses", "", ""),
    "Bookmark every alert of this finding": (T, T, "Hayabusa tab, the Mark button of a finding.",
                                             "test_a_finding_marks_every_alert_it_names", "", ""),
    "Show the alerts in the grid": (T, T, "Hayabusa tab, the Show button: the alert analysis, filtered on the rule.",
                                    "test_a_hayabusa_finding_opens_and_marks_its_alerts", "", ""),
    "Exporter les sources Hayabusa…": (T, T, "Hayabusa tab, the export link of a run.",
                                       "test_the_alert_sources_of_a_run_can_be_taken_away", "", ""),
    "Graphique": (T, T, "The grouped view draws the counts of the page as bars.",
                  "test_the_grouped_view_draws_its_chart", "", ""),
    "Gérer les analyses ouvertes": (T, T, "The ✕ on the analysis tab closes it; the tree switches.",
                                    "test_closing_an_analysis_leaves_the_others_and_its_file", "", ""),
    "Nœud libre…": (Q, Q, "", "", "", "Add a free node to the attack graph, which needs the graph to be editable and stored."),
    "Ouvrir l’événement EVTX source": (T, T, "Alert row menu: the EVTX analysis, filtered on the record.",
                                       "test_an_alert_points_to_its_source_event", "", ""),
    "Voir le contexte EVTX de cette alerte": (T, T, "Alert row menu: a context analysis, built by the core's alert_context.",
                                              "test_the_evtx_actions_only_appear_for_an_alert_analysis", "", ""),
    "Plugins": (T, T, "Preferences > Profiles and plugins…: catalogue, installed plugins, errors.",
                "test_a_presentation_plugin_is_installed_and_listed", "", ""),
    "Profils et compatibilité": ("container", D, "", "",
                                 "The desktop's expert-view submenu; its one command, Profils et plugins…, is the Profiles and compatibility dialog of the Host.", ""),
    "Sessions et compatibilité": ("container", D, "", "",
                                  "The desktop's case submenu: open a session file, save one, import a Timeline Explorer reader. The Host keeps sessions with the case instead.", ""),
    "Standard / personnalisé": (Q, Q, "", "", "", "Custom palette colours, not only the desktop's two themes."),
    "Épingler à droite": (T, T, "Row menu > Pin on the right, and Columns… > pin right.",
                          "test_a_column_can_be_frozen_on_either_edge", "", ""),
}


KINDS = {"parameter", "container"}


def build():
    """Entries carry (kind, status, where, test, reason, plan).

    A tuple whose first field is not a parameter or a container describes a
    command: the first field then repeats the status, which keeps the literal
    readable (T, T, ...) instead of a bare string repeated twice.
    """
    entries = []
    for label, (kind, status, where, test, reason, plan) in COMMANDS.items():
        entries.append(dict(label=label,
                            kind=kind if kind in KINDS else "command",
                            status=status, where=where, test=test,
                            reason=reason, plan=plan))
    return entries


if __name__ == "__main__":
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs" / "development" / "host-parity.json"
    path.write_text(json.dumps({"format": "fireblade-host-parity", "version": 1,
                                "commands": build()}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    counts = {}
    for entry in build():
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    print(sum(counts.values()), "labels:", counts, "->", path)
