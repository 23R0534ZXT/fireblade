# Profils de présentation et schémas forensic

Les profils sont de simples données : nom, colonnes de reconnaissance, dates, booléens et ordre des colonnes. Leur code est dans `core/profiles.py` ; le catalogue embarqué dans `core/profile_catalog.py`. Aucun serveur, moteur .NET ou système de dépendances de plugins n’est ajouté.

## Catalogue intégré

Le catalogue contient **222 signatures d’en-têtes pour 193 noms de formats**, relevées dans les déclarations publiques de TLEFilePlugins, révision [`7199c81`](https://github.com/EricZimmerman/TLEFilePlugins/tree/7199c81ba45a97be74b4e05da43cbaabecccf5ca). Les fichiers consultés sont EZTools.cs, KAPE.cs, Microsoft.cs, Misc.cs, Timelines.cs et TZWorks.cs. Les noms de champs et leurs types constituent les métadonnées de formats ; les implémentations C# des parseurs ne sont pas exécutées. La notice MIT d’origine est conservée dans `licenses/TLEFilePlugins-MIT.txt`.

La reconnaissance est insensible à la casse et recherche la présence des champs requis. Une signature complète est prioritaire sur les cinq premiers profils génériques historiques. Les profils personnels sont prioritaires sur les profils intégrés.

Ce catalogue couvre notamment les familles EZ Tools, KAPE, Microsoft/Sysinternals, Hayabusa, Chainsaw, timelines Plaso/mactime et TZWorks. **Reconnaître un schéma ne signifie pas avoir qualifié tous les formats ni reproduire chaque transformation des plugins TLE.** Les formats sans signature restent lisibles comme CSV génériques. Les champs non reconnus ne sont jamais supprimés.

Les profils peuvent présenter des dates et des booléens, ordonner les colonnes et proposer un tri. Certains profils Hayabusa et supertimeline ajoutent des règles de couleur. Les valeurs sources ne sont pas transformées ; le détail et l’export conservent leur texte. Le format ISO à sept décimales conserve aussi les fractions sources plus précises.

## Ajouter un profil sans modifier le programme

Menu **Affichage → Profils et plugins → Installer un profil JSON**. Exemple :

```json
{
  "name": "Mon export",
  "signature": ["Event", "Time"],
  "timestamp": ["Time"],
  "booleans": ["Deleted"],
  "columns": ["Time", "Event", "Deleted"]
}
```

Il est également possible de déposer le fichier dans `%LOCALAPPDATA%\Fireblade\Plugins`. Le gestionnaire signale les fichiers invalides. Limites : 100 fichiers, 2 Mo par fichier, 1024 noms par liste. Aucun code du fichier JSON n’est exécuté. Les DLL C# de Timeline Explorer ne sont pas chargées.

Pour un nouveau traitement qui dépasse une présentation, créer un module Python distinct dans `core/`, avec un test sur un petit export représentatif, puis le raccorder explicitement. Un moteur de script général dans l’interface n’est pas nécessaire.
