# colab/ — les scripts Colab du projet

> C'est la pièce du README : *« l'IA met par exemple "j'ai besoin de vérifier
> tatata" et le script pour Colab se met à jour avec des tasks »*.

Trois scripts :

| Script | Rôle | Clé API |
|---|---|---|
| `main.ipynb` → `main.py` (v2) | exécute les **tâches de recherche** programmées par l'IA, pousse les résultats au site | optionnelle (résumé local) |
| `agent_search.ipynb` / `agent_search.py` | **Recherche agentique (1 cellule)** : 2 modes — question libre **ou** file de tâches du site ; dit ce qu'il fait, HTTP search/fetch (pas de navigateur JS), hits, étape suivante | optionnelle (Mistral pour enchaîner) |
| `analyze_discussions.ipynb` / `analyze_discussions.py` | **Analyseur automatique de discussions** : vérifie les infos de TES discussions web et met à jour la base de connaissances | **requise — Mistral only** (fournie par l'utilisateur) |

## Recherche agentique (1 cellule)

Colab n'a **pas** de vrai navigateur. `agent_search.py` (copier depuis `/colab` → bouton **Copier le code (1 cellule)**) propose **2 modes** au lancement :

1. **recherche personnalisée** (défaut) : tu colles la question (« dernier modèle Anthropic ») ;
2. **tâches du site** : la file `pending` est rapatriée (`GET /api/research/tasks`) et
   l'agent traite chaque tâche — statuts poussés (`PATCH`), résultats poussés avec le
   vrai `task_id` (`POST /api/research/results`). `AGENT_MAX_TASKS` (défaut 3) borne le
   run ; une tâche fetch commence par un fetch, une tâche note est poussée telle quelle.

Dans les deux modes, le script **dit** l'étape (« je cherche … ») puis exécute HTTP
(DDG / Wikipédia / fetch) ; les hits s'affichent ; avec une clé Mistral optionnelle, le
modèle choisit fetch/search/stop (max 4 étapes) ; le résultat est poussé — visible sur
`/colab` et via `list_research_results`.

Sans clé : une seule recherche + push. Pages 100 % JS → texte vide (normal).

**Clé API robuste (bug v1 corrigé)** : une clé collée peut contenir des caractères
typographiques (« — », apostrophe courbe, retour à la ligne) que HTTP refuse dans ses
en-têtes (latin-1 seulement) — cela faisait planter tout le run avec
`UnicodeEncodeError`. La clé est maintenant nettoyée automatiquement (avec
avertissement), et un appel LLM qui échoue (clé refusée, réseau…) arrête proprement
l'agent au lieu de lever un traceback.

## Analyseur automatique de discussions (1 cellule)

L'analyseur est un **seul bloc de code** (`analyze_discussions.py`, collable tel
quel dans une cellule Colab, ou `analyze_discussions.ipynb` = 1 cellule) que
l'utilisateur pilote avec **sa** clé Mistral (`ministral-8b-latest` par défaut).
Le script est **entièrement piloté par Mistral** : c'est le modèle qui extrait
les affirmations, qui écrit les requêtes de recherche (et les reformule si la
première ne donne rien) et qui décide du patch de base ; le script exécute
(pleine puissance Colab : recherche multi-moteurs sans clé + lecture de pages).

```
Browser (site) — localStorage "aiis.convos.v1"
   │ ① sélection 1 à N discussions (bouton 📤 ou snippet console) → 1 ligne base64
   ▼
Colab — 1 cellule
   │ ② clé Mistral (getpass, RAM seule) + ping (1 appel)
   │ ③ base de connaissances : GET /api/data/entries du site (repli : collage / vide)
   │ ④ par discussion : extraction des claims (Mistral) → recherche web (sans clé)
   │    → verdict sourcé par claim (Mistral, +1 reformulation si invérifiable)
   │    → patch de la base (Mistral : corrections si fausses, ajouts si absentes)
   │ ⑤ push : POST /api/data/entries (repli : note de recherche si serveur ancien)
   │ ⑥ rendu structuré : console + rapport .md + JSON complet + knowledge_base_maj.json
   ▼
Site — base corrigée/étendue (visible sur /data.html)
```

**Utilisation (3 minutes)** :

1. **Exporter ses discussions** — sur le site : bouton **📤** (barre du haut) →
   cocher 1 à N conversations → « Copier la ligne base64 ». Sans le bouton
   (vieux déploiement) : le script Colab affiche un snippet à coller dans la
   console du navigateur (F12) qui fait la même chose.
2. **Colab** — ouvrir `colab/analyze_discussions.ipynb` (ou coller
   `analyze_discussions.py` dans une cellule vierge) → Run → coller la ligne
   base64 quand demandé → saisir sa clé Mistral (masquée, RAM uniquement).
3. **Résultat** — rapport structuré dans la cellule + 3 fichiers
   téléchargés (`rapport_analyse_discussions_*.md`, `analyse_discussions_*.json`,
   `knowledge_base_maj.json`) ; la base du site est poussée et visible sur
   `/data.html`.

**Règles de sécurité** : la clé est saisie en `getpass` (jamais affichée), vit
en RAM uniquement, est expurgée de tous les logs/rappports/payloads (`redact()`)
et n'est **jamais poussée au site**. Les discussions ne partent que vers
l'API Mistral (analyse) — jamais vers les moteurs de recherche. Les écritures
sur la base passent par l'endpoint dédié `POST /api/data/entries` (5 champs de
la base uniquement, dédoublonnage par titre/summary, provenance
`colab-analyseur` / URL de la preuve dans `source`).

**Coût** (tier gratuit Mistral, cf. `docs/FREE-TIERS.md`) : 1 ping + par
discussion ~1 extraction + 1 verdict par affirmation (≤ 6, 1 reformulation max)
+ 1 patch de base ≈ **8 appels max/discussion** sur `ministral-8b-latest`
(le modèle le plus économe du pool), throttle ≥ 1,05 s entre appels intégré.

---

## main.ipynb → main.py — le script de recherche que l'IA met à jour (v2)

### Principe : les tâches vivent sur le serveur, avec la base de données

Le serveur (quel que soit son backend actif — local, GitHub ou Supabase) est la
**seule source de vérité** des tâches. Le notebook Colab n'est qu'un **client de
l'API** : il tire les tâches (`GET /api/research/tasks`), les exécute, et
repousse statuts (`PATCH`) + résultats (`POST /api/research/results`). Plus
aucun fichier de tâches ne transite via git.

### Mécanique

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

### Utilisation dans Google Colab

1. Sur ce repo GitHub : `colab/main.ipynb` → **Ouvrir dans Colab**
   (ou uploade le fichier `.ipynb` téléchargé dans Colab).
2. Cellule 1 : vérifie `MAIN_SITE_URL` (l'URL de **ton** site, sans `/` final).
   Pour tester une branche de dev : `BRANCH = "nom-de-branche"`.
3. **Runtime → Run all** : diagnostic → exécution → résultats. Chaque run
   consomme du temps gratuit Colab ; les sauvegardes incrémentales + les
   retries de push évitent les pertes.
4. Vérifiez sur la page `/colab` du site : les tâches passent `done`, les
   résultats apparaissent avec leur bilan d'étude, et l'IA peut les utiliser.

### Synchronisation avec le serveur (v2, robuste)

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

### Rendre Colab plus intelligent

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

### Dépannage

Voir le tableau en fin de notebook (`main.ipynb`). Cas fréquents : URL du site
fausse, DuckDuckGo bloqué (fallback Wikipédia automatique — normal), quota LLM
atteint (le brut est quand même poussé), étude serveur pas encore prête (recharger
`/colab` dans 1 min).

### Limites

- Colab : pas de rendu JS → idéal pour `search`/`deep` et le `fetch` de pages
  simples (Wikipédia, blogs…). Les pages à rendu JS lourd donnent un texte vide
  (signalé dans le rapport).
- Les sessions Colab sont limitées dans le temps ; les sauvegardes
  incrémentales (`tasks_cache.json`/`results.json` à jour après chaque tâche) +
  les retries de push évitent les pertes.
- Volume raisonnable : 1 s entre deux fetchs, robots.txt honoré — c'est de la
  recherche ponctuelle, pas du crawl massif.
