# Contribuer à Fireblade

Pour un bug, utiliser le [formulaire de signalement](https://github.com/23R0534ZXT/fireblade/issues/new/choose). Pour les premiers essais, suivre [le parcours des testeurs](https://github.com/23R0534ZXT/fireblade/issues/6).

Pour contribuer au code :

1. Suivre le [guide d’installation et de développement](docs/development/CONTRIBUER.md).
2. Lire la [carte de l’architecture](docs/development/ARCHITECTURE.md).
3. Décrire le problème et le comportement attendu dans une issue ou une PR.
4. Exécuter les tests concernés et `python -m ruff check src scripts tests` ; indiquer les résultats et leurs limites dans la PR.

Utiliser des données synthétiques ou publiques avec leur provenance. Les sources, annotations et sessions existantes doivent rester protégées lors d’un échec ou d’une annulation.
