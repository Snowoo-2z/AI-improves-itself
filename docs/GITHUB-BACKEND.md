# Base de données sur GitHub (repo privé)

Le projet peut stocker ses données — requêtes au dev, tâches/résultats de
recherche, base de connaissances — dans un **repo GitHub privé** au lieu des
fichiers JSON locaux. Un fichier par collection, versionné par git, lisible
dans l'onglet web de GitHub, gratuit.

``` 
ton-repo-de-données-privé/
└── data/
    ├── dev_requests.json      # /request
    ├── research_results.json  # résultats du notebook Colab
    ├── research_tasks.json    # tâches de recherche (file du serveur — Colab passe par l'API)
    └── knowledge.json         # base de connaissances (seedée auto au 1er appel)
```

## 1. Créer le repo de données (2 min)

1. Sur GitHub : **New repository** → nom au choix (ex. `ai-data-prive`) → **Private** → créer **sans README** (le serveur créera les fichiers tout seul au premier usage).
2. Note son nom complet : `TON-COMPTE/ai-data-prive`.

## 2. Créer le token (2 min)

1. <https://github.com/settings/personal-access-tokens> → **Generate new token** → **Fine-grained token**.
2. **Repository access** → *Only select repositories* → ton repo de données **uniquement**.
3. **Permissions** → *Repository permissions* → **Contents** : **Read and write**. Rien d'autre.
4. Generate → **copier le token** (`github_pat_...`). Il ne sera plus jamais affiché.

> 🔒 Le token vit **uniquement dans ton `.env` local** (jamais commité :
> `.gitignore` l'exclut). Le serveur ne l'envoie nulle part sauf à
> `api.github.com`, ne le journalise pas et ne l'expose dans aucune API
> (`/api/status` affiche le repo, jamais le token).

## 3. Brancher le projet

Dans `.env` (copié depuis `.env.example`) :

```bash
STORE_BACKEND=auto        # ou 'github' pour forcer (repli local si mal configuré)
GITHUB_TOKEN=github_pat_...
GITHUB_REPO=TON-COMPTE/ai-data-prive
# GITHUB_BRANCH=main          # optionnel
# GITHUB_DIR=data             # optionnel (dossier des *.json dans le repo)
# RESEARCH_TASKS_PATH=data/research_tasks.json   # optionnel (voir §5)
```

Puis **redémarrer** le serveur (`python core/server.py` — le `.env` est lu au démarrage).

## 4. Vérifier

- `GET /api/status` → `"store_backend": "github"`, `"store_repo": "TON-COMPTE/ai-data-prive"`.
- La sidebar du chat affiche `store: github · TON-COMPTE/ai-data-prive`.
- Ouvre une requête sur `/request` (ou demande à l'IA) : un commit `data: dev_requests (...)` apparaît dans le repo.

## Comportement détaillé

| Point | Comportement |
|---|---|
| Sélection | `STORE_BACKEND=auto` : supabase (si configuré) → github (si configuré) → local |
| Backend forcé KO | repli sur `local` + avertissement dans les logs (jamais de crash API) |
| 1er appel `knowledge` | le fichier est **créé** dans le repo depuis le seed local, puis relu depuis GitHub |
| Lectures | cache mémoire 15 s (un refresh `/api/status` = 4 listes → rapides, peu d'appels API) |
| Écritures | read-modify-write + rejeu sur conflit de `sha` (409), max 3 tentatives |
| Quotas GitHub | 5 000 req/heure authentifiées — largement assez pour ce projet |
| Prompts système | restent des fichiers locaux versionnés par **git** (`core/prompt_system/`) — pas dans le repo de données |
| Colab | `colab/main.py` rapatrie aussi les tâches via `GET /api/research/tasks` dès que `MAIN_SITE_URL` est défini, fusionne avec le fichier local (par id), et repousse statuts (`PATCH`) + résultats (`POST`) — indispensable sur Render où les tâches du chat ne sont plus dans un fichier local |


## 5. Synchroniser les tâches de recherche (IA et humain)

Toute tâche de recherche est écrite **où que l'API l'ait créée** :

- via le chat → skill `add_research_task` (auteur `ai`),
- via le formulaire de la page `/colab` → `POST /api/research/tasks` (auteur `human`).

Les deux passent par le même `Store` : en backend GitHub, chaque création fait
un **commit dans le repo de données** vers `data/research_tasks.json` (défaut,
avec les autres collections), et les changements de statut (`pending` →
`processing` → `done`/`failed`) sont aussi écrits. Le notebook Colab récupère
les tâches via l'API (`GET /api/research/tasks`) — le serveur est la seule
source de vérité ; aucun fichier n'est lu via git.

> **Migration v1 → v2** : les tâches vivaient dans `colab/tasks.json`. Si ce
> fichier existe encore et que `data/research_tasks.json` manque, il est lu en
> fallback puis migré automatiquement à la prochaine écriture (tu peux ensuite
> supprimer l'ancien fichier).

### Changer le dossier

Par défaut les tâches vivent dans `data/research_tasks.json` (comme les autres
collections). Pour les ranger ailleurs dans le repo (ex. `recherche/taches.json`) :

```bash
RESEARCH_TASKS_PATH=recherche/taches.json
```

Règles d'interprétation du chemin :

| `RESEARCH_TASKS_PATH` | fichier écrit dans le repo |
|---|---|
| `data/research_tasks.json` | `data/research_tasks.json` |
| `recherche/taches.json` | `recherche/taches.json` |
| `recherche` (dossier) | `recherche/research_tasks.json` |
| (vide) | `data/research_tasks.json` (défaut) |

> En mode **local** (pas de GitHub), les tâches vivent dans
> `core/data/research_tasks.json`, avec le reste de la base (l'ancien
> `colab/tasks.json` du repo est migré automatiquement au premier accès — il
> reste ensuite un simple seed de démo). La même variable `RESEARCH_TASKS_PATH`
> peut déplacer le fichier (relatif au repo ou absolu) pour partager un cache
> avec un script Colab lancé hors-ligne (même valeur des deux côtés).

## Limites assumées

- Pas fait pour du gros volume (chaque écriture = 1 commit + réécriture du fichier) : parfait pour des centaines/milliers d'entrées, pas des millions.
- Concurrence : le rejeu sur conflit protège les écritures simultanées occasionnelles, pas un trafic intense (verrou local + 3 essais).
- Le token a accès en écriture au repo de données : ne mets **que** des données dedans, jamais de code sensible — et garde le repo **privé**.
