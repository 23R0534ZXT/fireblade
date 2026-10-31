# Profils de présentation et schémas forensic

Les profils sont de simples données : nom, colonnes de reconnaissance, dates, booléens et ordre des colonnes. Leur code est dans `core/profiles.py` ; le catalogue embarqué dans `core/profile_catalog.py`. Ces profils ne chargent aucun code. Un pont .NET séparé existe pour les lecteurs et fonctions binaires sélectionnés explicitement.

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

Il est également possible de déposer le fichier dans `%LOCALAPPDATA%\Fireblade\Plugins`. Le gestionnaire signale les fichiers invalides. Limites : 100 fichiers, 2 Mo par fichier, 1024 noms par liste. Aucun code du fichier JSON n’est exécuté. Les DLL ne sont pas chargées depuis ce dossier de profils ; leur utilisation passe par les commandes explicites ci-dessous.

Pour un nouveau traitement qui dépasse une présentation, créer un module Python distinct dans `core/`, avec un test sur un petit export représentatif, puis le raccorder explicitement. Un moteur de script général dans l’interface n’est pas nécessaire.

## Transformations déclaratives

Les profils acceptent aussi une liste `transforms` : colonnes UTC à partir d’une date ISO, Unix, FILETIME, WebKit, .NET ou OLE ; expression scalaire ; indicateurs MACB ; catégories de timeline. Le registre et les limites sont décrits dans [COMPATIBILITE.md](COMPATIBILITE.md). Une vue SQL persistante ajoute ces résultats à la grille, aux filtres, regroupements et exports. Le CSV et les valeurs source ne sont pas réécrits.

Les adaptations intégrées couvrent les traitements temporels et catégories des familles Plaso/L2T, Psort, ForensicTimeline et mactime, ainsi que les dates séparées de PeScan/Wisp. Des métadonnées d’alias facilitent la migration des layouts de 45 profils. Le catalogue de 193 noms reste un catalogue de reconnaissance : il n’exécute pas 193 parsers binaires ou de textes spécialisés.


## Lecteurs et fonctions .NET TLE

**Fichier → Importer avec un plugin TLE (.NET)…** : choisir la DLL, le lecteur détecté et la source. Les classes doivent avoir un constructeur sans argument et exposer le contrat `ProcessFile(string)` / `DataList`, directement ou via `IFileSpec`. Le helper recherche les dépendances dans le dossier de la DLL puis son parent (organisation habituelle de TLE). Conserver les dépendances de votre plugin avec lui ; elles ne font pas partie des fichiers nécessaires pour lancer Fireblade seul.

Les propriétés typées, `ITypedList` et les dictionnaires dynamiques sont convertis en CSV UTF-8 puis importés dans DuckDB. Le champ de ligne source du lecteur est conservé comme `TLE_SourceLine`. La source originale reste inchangée et identifiée par SHA-256 ; la DLL et le type sont enregistrés dans la provenance. Le `Tag` interne TLE n’écrase pas les signets Fireblade. Les transformations de type sont signalées.

**Analyse → Charger des fonctions .NET…** détecte les fonctions avec `Name` et `Evaluate(object[])`, ainsi que `ResultType(Type[])` lorsqu’il existe. Leur nom est utilisable dans les expressions ; `Custom('Nom', …)` et `PluginNumber('Nom', …)` sont aussi disponibles. Le processus persiste durant l’analyse et est arrêté à sa fermeture. Les DLL déjà choisies pour cette analyse sont rechargées automatiquement à la réouverture, après contrôle SHA-256 et vérification du registre local. Les déclarations d’une analyse reçue ne suffisent pas à exécuter une DLL non approuvée.

Un plugin sélectionné est du code exécuté avec les droits de l’utilisateur. Ce processus séparé n’est pas un bac à sable. Les DLL .NET Framework utilisent un helper CLR4 distinct ; les DLL .NET récentes utilisent le helper autonome moderne. Les bibliothèques tierces doivent rester accessibles dans le dossier de la DLL ou son parent. La mémoire et les performances d’un lecteur dépendent de son implémentation ; préférer l’import natif pour un CSV volumineux. Le coût interprocessus des fonctions par cellule est supérieur au SQL natif.

Le binaire distribué intègre le runtime Windows du helper : rien à installer chez le destinataire. Pour construire les sources, installer le SDK .NET 10. Le build teste un lecteur de qualification et compile/exécute aussi le vrai **TLEFileGenericCsv** du dépôt public, à la révision `7199c81ba45a97be74b4e05da43cbaabecccf5ca`. Ce contrôle ne qualifie pas toutes les DLL tierces.


## Reprise automatique et ancien CLR

Le registre `%LOCALAPPDATA%\Fireblade\tle-plugins.json` mémorise les DLL explicitement choisies, leurs empreintes, les analyses autorisées et les associations source/lecteur. Une DLL modifiée n’est pas exécutée silencieusement. Les objets imbriqués peuvent être utilisés par `[Details.Name]`, `[Details].[Children].Count()` ou `[Details.Children].Sum([Amount])`.

Un helper .NET Framework 4.8 partage le même code et les mêmes contrats avec le helper moderne. Le CLR4 est celui des versions récentes de Windows 10/11 ; les fichiers auxiliaires du helper restent intégrés au fichier unique distribué. Le build Windows vérifie une vraie DLL nécessitant System.Web, son lecteur, sa fonction et sa reprise après réouverture. La compilation de ce lot a été vérifiée ; sa qualification Windows est publiée dans Actions avant mise à disposition d’un nouvel EXE.
