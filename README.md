# AI-improves-itself

> *L'IA s'améliore d'elle-même* — projet de recherche : et si on donnait à une IA les outils pour
> modifier son propre prompt système, affiner ses skills et programmer sa propre recherche web ?
> Où pourra-t-elle aller si on lui donne assez d'outils pour « entre guillemets » modifier le code
> et les informations qu'elle connaît ?

Projet à but **recherche** : offres API gratuites (Mistral en priorité, + Gemini/Groq/OpenRouter en
fallback), hébergement gratuit (site statique + Supabase free tier + Colab gratuit), et la
**vision** (analyse d'images) par le moteur multimodal `ministral-8b-latest`.

---

## 🏗 Monorepo — les 2 parties

```
AI-improves-itself/
├── site/                     # PARTIE 1 — interface générale (site statique)
│   ├── index.html            #   chat avec l'IA (l'interface principale)
│   ├── prompt.html           #   le prompt système versionné + historique d'auto-modifs
│   ├── data.html             #   base de connaissances + redirections vers les datas
│   ├── colab.html            #   /colab — tâches & résultats de recherche web
│   ├── request.html          #   /request — file de requêtes IA → dev
│   ├── contributeur.html     #   page contributeur
│   ├── css/ js/              #   thème + scripts (vanilla, zéro framework)
│
├── core/                     # PARTIE 2 — le cœur IA (FastAPI)
│   ├── server.py             #   sert le site statique + l'API /api/*
│   ├── ai/                   #   multi-fournisseurs + orchestration + pas de réflexion
│   ├── prompt_system/        #   ★ prompt versionné, modifiable par l'IA, garde-fous mots-clés
│   ├── skills/               #   les outils de l'IA (whitelist stricte)
│   ├── research/             #   pipeline recherche (tâches, résultats, notebook Colab)
│   └── data/                 #   base locale (JSON) → Supabase en phase 2
│
├── colab/                    # notebook + script exécuté dans Google Colab (tâches de recherche)
├── supabase/schema.sql       # base de données (phase 2, schéma complet prêt)
├── tests/                    # suite sans réseau (bouchons httpx) : repli, 429, quotas, modèles retirés
├── render.yaml               # blueprint Render : 1 service créé en one-click
└── docs/                     # ARCHITECTURE.md · FREE-TIERS.md (offres gratuites vérifiées) · RENDER.md
```

## 🧬 Le cœur du concept : comment l'IA modifie-t-elle l'ensemble ?

| Mécanisme | Où | Comment |
|---|---|---|
| **Prompt système** | `core/prompt_system/` | L'IA peut modifier son propre prompt (ex. après une réponse où elle a ignoré une date, elle ajoute elle-même la règle « trier par date quand on demande le plus récent »). Chaque modif = **version + historique + notification /request + garde-fou anti-fuite de clés API**. Les garde-fous par **mots-clés** chargent des modules spécialisés (`code`, `recherche`, …). |
| **Skills** | `core/skills/` | L'IA peut affiner les **descriptions** de ses skills (auto-amélioration légère). De **nouvelle** skill = code humain : l'IA ouvre une requête sur `/request`. |
| **Recherche web** | `colab/` | L'IA programme des tâches (`search`/`fetch`) ; le notebook Colab (script mis à jour par les tâches) les exécute ; les résultats reviennent au site et l'IA les étudie. |
| **Base de données** | `core/data/` → `supabase/` | JSON local pour l'instant, schéma Supabase prêt (phase 2), repo GitHub privé prévu pour les données. |

**Démo intégrée sans aucune clé API** : le mode démo reproduit fidèlement l'exemple du README —
demande « quel est le dernier jeu Zelda ? », l'IA répond avec le Zelda de 1986 (première ligne de la
base), se rend compte de son défaut, et **modifie son propre prompt système** pour se corriger.
Repose la question : bonne réponse.

## 🚀 Démarrer (3 minutes)

```bash
# 1. dépendances (Python 3.11+)
pip install -r requirements.txt

# 2. configuration (optionnel mais recommandé)
cp .env.example .env      # renseigner au moins MISTRAL_API_KEY

# 3. lancer
python core/server.py     # → http://localhost:8000
```

Sans `.env` : le serveur démarre en **mode démo local** (moteur déterministe, montre quand même
toute la boucle d'auto-amélioration). Avec `MISTRAL_API_KEY` : le vrai moteur Mistral prend le
relais (les autres clés = fallback automatique).

> 💡 **Tiers gratuits — l'état vérifié (2026-09-15) est dans
> [docs/FREE-TIERS.md](docs/FREE-TIERS.md)** : limites réelles par fournisseur, IDs de
> modèles vivants **et retirés**, sources (docs officielles + retours Reddit).
> En bref : Mistral = ~1 req/s globale par clé + pool partagé de 50 000 tokens/min et
> 4 M tokens/mois (d'où le **Ministral 8B essayé en premier** : même pool que Small 4,
> mais ~10× moins de tokens par réponse) ; Groq = 200 000 tokens/**jour** sur
> gpt-oss-120b ; Gemini = 1 500 req/jour remis à minuit heure du Pacifique ;
> OpenRouter = 20 req/min et 50 req/jour (les 429 comptent dans le quota !).
> Le cœur gère tout ça seul : throttle en amont, rotation de modèles, repli en cascade
> vers le moteur suivant, et repos par moteur calé sur ce que l'API annonce
> (`Retry-After`, fenêtre du jour, mois, ou erreur de configuration à corriger dans `.env`).

## 🔌 Brancher le reste

- **Supabase** : créer un projet → SQL Editor → exécuter `supabase/schema.sql` → renseigner
  `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` dans `.env` (la persistance bascule automatiquement).
- **GitHub comme base** (alternative à Supabase, sans compte supplémentaire) : repo **privé**
  dédié + token fine-grained (Contents lecture/écriture sur ce seul repo) → `GITHUB_TOKEN` +
  `GITHUB_REPO` dans `.env` → 📘 **[docs/GITHUB-BACKEND.md](docs/GITHUB-BACKEND.md)**.
  Le backend actif est visible dans `/api/status` (`store_backend`) et dans la sidebar du chat.
- **Render** : **`render.yaml`** — sur Render, *New → Blueprint* crée le service
  `aiis-core` (site + API) en one-click sur le plan `free` (512 Mo, 0 $), la seule
  machine gratuite de Render (tout ce qui est ≥ 2 Go est payant : `1c-2g` = 25 $/mois).
  → 📘 **Tutoriel Render détaillé pas-à-pas : [docs/RENDER.md](docs/RENDER.md)**
- **Colab** : ouvrir `colab/main.ipynb` dans Google Colab → Run all (voir `colab/README.md`).
- **Vision** : joindre une image (bouton 📎 ou collage) dans le chat — le moteur Mistral
  `ministral-8b-latest` est multimodal et la décrit. Rien à configurer côté `.env`.

## 🔒 Garde-fous humains (non négociables)

1. L'IA ne code **jamais** : elle *request* (`/request`), le dev implémente ou rejette.
2. Chaque auto-modif de prompt est versionnée, visible (`/prompt`), **réversible** par un humain.
3. Aucune clé API dans le prompt, dans le repo, ni dans les données (filtres à l'écriture).
4. Whitelist stricte de skills ; fetch de recherche limité en volume.
5. Le mode démo est déterministe et 100 % local : rien ne part sur le réseau sans clé configurée.

## 🗺 Roadmap

- [x] Monorepo + site statique (chat, /prompt, /data, /colab, /request, /contributeur)
- [x] Cœur IA multi-fournisseurs (Mistral prioritaire) + mode démo de la boucle d'auto-amélioration
- [x] Repli en cascade + disjoncteur par moteur (429/quota journalier/mensuel/modèle retiré/réseau)
- [x] Catalogue des offres gratuites vérifié ([docs/FREE-TIERS.md](docs/FREE-TIERS.md)) + suite de tests
- [x] Prompt système versionné + garde-fous mots-clés + auto-modification
- [x] Skills (search, modify_prompt, request_to_dev, add_research_task, …)
- [x] Notebook Colab (recherche web) + synchronisation GitHub des tâches
- [x] Vision : analyse d'images via `ministral-8b-latest`
- [x] Streaming (SSE) des réponses Mistral
- [x] Schéma Supabase
- [ ] Migrer les données vers Supabase (client déjà codé)
- [ ] Pas de réflexion LLM en mode live (aujourd'hui : l'IA se corrige via sa mission dans le prompt ; v2 : appel dédié d'analyse post-réponse)
- [ ] Évaluation des auto-modifs (le prompt v2 est-il mieux que v1 ? métriques sur un jeu de questions)
- [ ] Export CSV/JSON de l'historique des prompts (idée de requête déjà dans /request 😉)

---

### La vision (texte d'origine)

> L'AI s'améliore d'elle-même. On utilise des clés de fournisseurs qui proposent des offres gratuites
> et des solutions d'hébergement gratuites. Le projet est avant tout pour la recherche et répondre à
> la question : *où pourra aller l'AI si nous lui donnons assez d'outils pour modifier le code et les
> informations qu'elle connaît ?* L'IA a la possibilité de modifier le prompt système actuel notamment
> lors de l'analyse de ses propres réponses ; une page /request existe où l'AI peut envoyer des
> requêtes au développeur pour des fonctionnalités utiles et des modifications UI ; et la base de
> données & recherche est un repo GitHub (privé pour l'instant).
