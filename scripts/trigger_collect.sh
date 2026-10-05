#!/usr/bin/env bash
# Lance la collecte des flux sur GitHub Actions et attend qu'elle arrive sur main.
#
# Utilisé par la routine Claude (ROUTINE.md, étape 1). Pousse sur la branche `collecte` un
# commit vide posé sur main, ce qui déclenche .github/workflows/collect.yml, puis attend que
# le workflow ait poussé sur main son commit « collecte: ... (demande <id>) ».
# Sortie 0 : collecte arrivée et main local à jour. Sortie 1 : délai dépassé.
set -euo pipefail

ATTENTE_MAX=${ATTENTE_MAX:-480}   # secondes, à garder sous le délai de 10 min de l'outil Bash
INTERVALLE=20

cd "$(dirname "$0")/.."
git fetch -q origin main
DEMANDE=$(git commit-tree "origin/main^{tree}" -p origin/main \
  -m "demande de collecte $(date -u +'%Y-%m-%d %H:%M:%S') UTC")
ID=${DEMANDE:0:12}
git push -q -f origin "$DEMANDE:refs/heads/collecte"
echo "Collecte demandée (demande $ID), attente du workflow GitHub..."

debut=$(date +%s)
while (( $(date +%s) - debut < ATTENTE_MAX )); do
  sleep "$INTERVALLE"
  git fetch -q origin main || continue
  ligne=$(git log origin/main -n 50 --format=%s | grep -F "(demande $ID)" || true)
  if [[ -n $ligne ]]; then
    git pull -q --rebase origin main
    echo "Collecte terminée : $ligne"
    exit 0
  fi
done
echo "ERREUR : aucun commit de collecte pour la demande $ID après ${ATTENTE_MAX} s" \
  "(voir l'onglet Actions du dépôt)." >&2
exit 1
