#!/usr/bin/env bash
# Lance toute la batterie de tests du jeu (VM Scratch headless).
#   cd tools && npm install && bash test.sh
set -e
cd "$(dirname "$0")"
for t in t_air.json t_save.json t_planche.json t_preview.json; do
  echo "=== scénario $t ==="
  node play.js ../dist/ArenaClash.sb3 "$t" 2>&1 | grep -vE "No audio engine|Translation|^\[90m"
done
for t in _t_sb3.js _t_armes.js _t_upgrade.js _t_botniv.js _t_garde.js _t_round.js _t_salve.js _t_shots.js _t_ecrans.js; do
  echo "=== test $t ==="
  node "$t" 2>&1 | grep -vE "No audio engine|Translation|^\[90m"
done
