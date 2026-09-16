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
  L'IA n'ajoute que des tâches ; elle n'exécute rien elle-même. En backend GitHub, ce fichier
  est **synchronisé dans le repo de données** (voir `docs/GITHUB-BACKEND.md` §5).
- `main.py` — le script. Exécute les tâches `pending` (recherche DuckDuckGo sans clé,
  fetch + extraction de texte), marque les `done`/`failed`, sauvegarde incrementale.
  L'URL du site est **détectée automatiquement** : variable `MAIN_SITE_URL` → fichier
  local `colab/main_site_url.txt` (gitignoré) → défaut versionné `https://aiis-core.onrender.com`.
- `main.ipynb` — wrapper Colab (2 cellules : config + exécution). La cellule de config
  est **pré-remplie** avec le site déployé.
- `results.json` — les résultats locaux (poussés au site dès que l'URL est résolue).

## Utilisation dans Google Colab

1. Sur ce repo GitHub : `colab/main.ipynb` → **File → Open notebook… → Colab**
   (ou créez un notebook vierge et collez `!pip install -q requests` puis le contenu de `main.py`).
2. Cellule 1 : l'URL du site est **pré-remplie** (`https://aiis-core.onrender.com`) —
   les résultats remontent automatiquement. Changez-la si vous déployez le vôtre
   (ou lancez `urlretrieve`/mode local sans URL pour des résultats locaux uniquement).
3. **Runtime → Run all**. Chaque exécution consomme de la RAM/temps gratuits Colab ;
   la session a une durée limitée (les sauvegardes incrementales évitent les pertes).
4. Vérifiez sur la page [/colab](../site/colab.html) du site : les tâches passent `done`,
   les résultats apparaissent, et l'IA peut maintenant les étudier.

## Synchronisation avec le serveur

- Si `MAIN_SITE_URL` est définie, le script **rapatrie les tâches depuis l'API**
  (`GET /api/research/tasks`) et les fusionne avec `tasks.json` (par id) — indispensable
  quand le backend est GitHub (les tâches créées par le chat vivent dans le repo de
  données, pas dans votre fichier local Colab). Statuts et résultats sont repoussés au site.
- En local (pas d'URL), le script lit `tasks.json` directement. Si le serveur écrit les
  tâches ailleurs (variable `RESEARCH_TASKS_PATH`), définissez la même variable en lançant
  le script pour lire/écrire le même fichier.

## Limites

- Colab : pas de rendu JS → idéal pour `search` (DuckDuckGo) et le `fetch` de pages
  simples (Wikipédia, blogs…). Les pages à rendu JS lourd ne sont pas supportées.
- Les sessions Colab sont limitées dans le temps ; les sauvegardes incrementales
  (`tasks.json`/`results.json` à jour après chaque tâche) évitent les pertes.
