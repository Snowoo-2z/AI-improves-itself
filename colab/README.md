# colab/ — le script de recherche que l'IA met à jour

> C'est la pièce du README : *« l'IA met par exemple "j'ai besoin de vérifier
> tatata" et le script pour Colab se met à jour avec des tasks »*.

## Mécanique

```
IA (chat)  ──skill add_research_task──▶  tasks.json  (file de tâches)
                                              │
                vous lancez le notebook ──────┤
                                              ▼
                                        main.py  → results.json
                                              │
                POST /api/research/results ───┘ (si MAIN_SITE_URL défini)
                                              ▼
                    site /colab + IA (skill list_research_results)
```

- `tasks.json` — la file. Chaque tâche : `{id, kind: search|fetch|note, target, reason, by, status}`.
  L'IA n'ajoute que des tâches ; elle n'exécute rien elle-même.
- `main.py` — le script. Exécute les tâches `pending` (recherche DuckDuckGo sans clé,
  fetch + extraction de texte), marquer les `done`/`failed`, sauvegarde incremental.
- `main.ipynb` — wrapper Colab (2 cellules : config + exécution).
- `results.json` — les résultats locaux (poussés aussi au site si `MAIN_SITE_URL` est défini).

## Utilisation dans Google Colab

1. Sur ce repo GitHub : `colab/main.ipynb` → **File → Open notebook… → Colab**
   (ou créez un notebook vierge et collez `!pip install -q requests` puis le contenu de `main.py`).
2. Cellule 1 : collez l'URL du site si vous voulez que les résultats remontent automatiquement
   (`!env MAIN_SITE_URL=https://votre-site.onrender.com`), ou lancez sans (résultats locaux uniquement).
3. **Runtime → Run all**. Chaque exécution consomme de la RAM/temps gratuits Colab ;
   la session a une durée limitée (les sauvegardes incrementales évitent les pertes).
4. Vérifiez sur la page [/colab](../site/colab.html) du site : les tâches passent `done`,
   les résultats apparaissent, et l'IA peut maintenant les étudier.

## Limites (et pourquoi Render existe aussi)

- Colab : pas de Chromium fiable (rendu JS incomplet) → idéal pour `search` et `fetch` de pages simples (Wikipédia, blogs…).
- Pour les pages à rendu JS lourd : le service Chromium de `services/scraper` (web service, 2 Go).
- Les deux exécutants se complètent ; les tâches restent les mêmes.
