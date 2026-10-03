# veille-cyber

Veille cyber automatisée : collecte de 30 flux RSS (éditeurs de sécurité, CERT, presse
spécialisée), synthèse en français par Claude centrée sur le vecteur d'intrusion, publication
d'un flux RSS groupé par sujet.

**Flux à ajouter dans ton lecteur RSS :** https://nikxo.github.io/veille-cyber/veille.xml

## Fonctionnement

| Étape | Qui | Quand | Fichiers |
|---|---|---|---|
| Collecte des flux (sans IA) | GitHub Actions, `scripts/collect.py` | toutes les heures à hh:05 UTC | écrit `data/inbox/`, `data/seen.json`, `data/health.json` |
| Lecture, tri, regroupement, synthèse | Tâche planifiée Claude, `ROUTINE.md` | toutes les heures | lit `data/inbox/`, écrit `data/stories.json`, `data/skipped.json` |
| Génération du flux | `scripts/build_feed.py` (lancé par Claude) | à chaque synthèse | écrit `docs/veille.xml`, `docs/index.html` |
| Publication | GitHub Pages (branche `main`, dossier `/docs`) | à chaque push | |

## Modifier les sources

Édite `feeds.json` (champ `enabled` pour désactiver un flux sans le supprimer).
L'état de chaque flux au dernier passage est dans `data/health.json`.

## Règles de synthèse

Voir `ROUTINE.md` : aucune déduction, chaque point attribué à sa source,
« Non précisé par les sources » quand le vecteur d'accès n'est pas documenté.
