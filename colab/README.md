# colab/ — le script de recherche que l'IA met à jour (v2)

> C'est la pièce du README : *« l'IA met par exemple "j'ai besoin de vérifier
> tatata" et le script pour Colab se met à jour avec des tasks »*.

## Principe : les tâches vivent sur le serveur, avec la base de données

Le serveur (quel que soit son backend actif — local, GitHub ou Supabase) est la
**seule source de vérité** des tâches. Le notebook Colab n'est qu'un **client de
l'API** : il tire les tâches (`GET /api/research/tasks`), les exécute, et
repousse statuts (`PATCH`) + résultats (`POST /api/research/results`). Plus
aucun fichier de tâches ne transite via git.

## Mécanique

```
IA (chat)  ──skill add_research_task──▶  API /api/research/tasks  (file du serveur,
                                          │  ▲                    stockée avec la base)
                notebook Colab (main.ipynb) ──┘  │  push statuts (PATCH) + résultats (POST)
                                              ▼  │
                                        main.py v2 → results.json
                                              │  ▲      (+ tasks_cache.json : cache local)
                                              │  └── attente du bilan d'étude serveur
                                              ▼
                    site /colab + IA (skill list_research_results)
```

- `tasks.json` (ce dossier) — **seed de démo versionné** : 3 tâches d'exemple.
  Il ne sert qu'à initialiser le cache local au premier run hors-ligne. Il
  n'est jamais écrit par le script et jamais synchronisé.
- `main.py` — le script v2. Réveille le serveur, rapatrie les tâches depuis
  l'API, fusionne avec le cache local, exécute les `pending` (recherche
  multi-moteurs sans clé, fetch + extraction titre/texte, robots.txt honoré),
  résume optionnellement par LLM (clé fournie à la main), pousse statuts +
  résultats, puis attend le bilan de l'étude serveur.
- `main.ipynb` — le notebook : 1 cellule de config, 1 de diagnostic
  (pré-vol : backend, file fusionnée, test clé), 1 d'exécution, 1 de résultats.
- `tasks_cache.json` / `results.json` — cache local + résultats (gitignorés).
  Chaque résultat porte `pushed` / `study` pour les retries et l'affichage.

L'URL du site est **détectée automatiquement** : variable `MAIN_SITE_URL` →
fichier local `colab/main_site_url.txt` (gitignoré) → défaut versionné
`https://aiis-core.onrender.com`.

## Utilisation dans Google Colab

1. Sur ce repo GitHub : `colab/main.ipynb` → **Ouvrir dans Colab**
   (ou uploade le fichier `.ipynb` téléchargé dans Colab).
2. Cellule 1 : vérifie `MAIN_SITE_URL` (l'URL de **ton** site, sans `/` final).
   Pour tester une branche de dev : `BRANCH = "nom-de-branche"`.
3. **Runtime → Run all** : diagnostic → exécution → résultats. Chaque run
   consomme du temps gratuit Colab ; les sauvegardes incrémentales + les
   retries de push évitent les pertes.
4. Vérifiez sur la page `/colab` du site : les tâches passent `done`, les
   résultats apparaissent avec leur bilan d'étude, et l'IA peut les utiliser.

## Synchronisation avec le serveur (v2, robuste)

- **Source de vérité = le serveur** : `GET /api/research/tasks` puis fusion
  avec le cache local (par id). Le **statut le plus avancé gagne** (`pending` <
  `processing` < `done`/`failed`) : une tâche `done` ne ressuscite jamais en
  `pending` — ni par le seed de démo (chargé uniquement si aucun cache), ni par
  un pull distant en retard.
- **Render gratuit s'endort** (15 min sans requête, ~1 min au réveil) : le
  script attend le réveil (jusqu'à ~2 min) au lieu d'échouer en 20 s comme la v1.
- **Push idempotent** : statuts (PATCH, 3 essais) + résultats (POST). Chaque
  résultat porte `pushed` : les échecs sont **repoussés au run suivant** (plus
  de perte silencieuse), et ceux déjà présents côté serveur sont sautés
  (déduplication, via `GET /api/research/results?task_id=…`).
- **Étude serveur suivie** : après le push, le script attend le bilan
  (structuration + vérification, ~30-60 s) et l'affiche ; sinon, recharge
  `/colab` dans 1 min — rien n'est perdu.
- En local (pas d'URL), le script travaille sur son cache seul (initialisé
  depuis le seed). Pour partager un fichier avec un serveur local hors-ligne,
  définissez la même valeur `RESEARCH_TASKS_PATH` des deux côtés (avancé).

## Rendre Colab plus intelligent

| Levier | Coût | Effet |
|---|---|---|
| `FETCH_TOP = 1` (défaut) | 0 € | chaque `search` lit aussi le texte du top-1 (extraits + contenu) |
| kind `deep` | 0 € | recherche + lecture auto des 3 meilleures pages (idéal état de l'art) |
| `SUMMARIZE = True` + clé API | ~1 appel/tâche (tier gratuit) | résumé local `{title, summary, key_points, confidence}` par tâche |

Clé API (optionnelle) : `LLM_PROVIDER` = `mistral` (défaut, `ministral-8b-latest`)
`gemini` · `groq` · `openrouter` · `nvidia`, `LLM_MODEL` vide = modèle économe
du provider. La clé est saisie via `getpass` (jamais affichée), vit **en RAM
uniquement** — jamais écrite sur disque, jamais poussée au site (les payloads
sont expurgés avant envoi), jamais dans les logs. Sans clé, le site étudie
quand même les résultats après le push (2 appels serveur).

## Dépannage

Voir le tableau en fin de notebook (`main.ipynb`). Cas fréquents : URL du site
fausse, DuckDuckGo bloqué (fallback Wikipédia automatique — normal), quota LLM
atteint (le brut est quand même poussé), étude serveur pas encore prête (recharger
`/colab` dans 1 min).

## Limites

- Colab : pas de rendu JS → idéal pour `search`/`deep` et le `fetch` de pages
  simples (Wikipédia, blogs…). Les pages à rendu JS lourd donnent un texte vide
  (signalé dans le rapport).
- Les sessions Colab sont limitées dans le temps ; les sauvegardes
  incrémentales (`tasks_cache.json`/`results.json` à jour après chaque tâche) +
  les retries de push évitent les pertes.
- Volume raisonnable : 1 s entre deux fetchs, robots.txt honoré — c'est de la
  recherche ponctuelle, pas du crawl massif.
