# AI-improves-itself

> *L'IA s'améliore d'elle-même* — projet de recherche : et si on donnait à une IA les outils pour
> modifier son propre prompt système, affiner ses skills et programmer sa propre recherche web ?
> Où pourra-t-elle aller si on lui donne assez d'outils pour « entre guillemets » modifier le code
> et les informations qu'elle connaît ?

Projet à but **recherche** : offres API gratuites (Mistral en priorité, + Gemini/Groq/OpenRouter en
fallback), hébergement gratuit (site statique + Supabase free tier + Colab gratuit), un service
Chromium léger (Render/Oracle/Fly) pour le scraping.

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
│   ├── research/             #   pipeline recherche (tâches, résultats, client Chromium)
│   └── data/                 #   base locale (JSON) → Supabase en phase 2
│
├── services/scraper/         # web service Chromium (Playwright) — déployable sur Render (512 Mo)
├── colab/                    # notebook + script exécuté dans Google Colab (tâches de recherche)
├── supabase/schema.sql       # base de données (phase 2, schéma complet prêt)
├── render.yaml               # blueprint Render : 2 services créés en one-click
└── docs/ARCHITECTURE.md      # architecture détaillée + règles de sécurité
```

## 🧬 Le cœur du concept : comment l'IA modifie-t-elle l'ensemble ?

| Mécanisme | Où | Comment |
|---|---|---|
| **Prompt système** | `core/prompt_system/` | L'IA peut modifier son propre prompt (ex. après une réponse où elle a ignoré une date, elle ajoute elle-même la règle « trier par date quand on demande le plus récent »). Chaque modif = **version + historique + notification /request + garde-fou anti-fuite de clés API**. Les garde-fous par **mots-clés** chargent des modules spécialisés (`code`, `recherche`, …). |
| **Skills** | `core/skills/` | L'IA peut affiner les **descriptions** de ses skills (auto-amélioration légère). De **nouvelle** skill = code humain : l'IA ouvre une requête sur `/request`. |
| **Recherche web** | `colab/` + `services/scraper/` | L'IA programme des tâches (`search`/`fetch`) ; le notebook Colab (script mis à jour par les tâches) ou le service Chromium les exécute ; les résultats reviennent au site et l'IA les étudie. |
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

## 🔌 Brancher le reste

- **Supabase** : créer un projet → SQL Editor → exécuter `supabase/schema.sql` → renseigner
  `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` dans `.env` (la persistance bascule automatiquement).
- **Scraper Chromium** : **`render.yaml`** — sur Render, *New → Blueprint* crée les 2
  services du projet en one-click (ou manuellement : voir `services/scraper/README.md`) →
  `SCRAPER_SERVICE_URL=https://ton-scraper.onrender.com` dans `.env`.
  → 📘 **Tutoriel Render détaillé pas-à-pas : [docs/RENDER.md](docs/RENDER.md)**
- **Colab** : ouvrir `colab/main.ipynb` dans Google Colab → Run all (voir `colab/README.md`).

## 🔒 Garde-fous humains (non négociables)

1. L'IA ne code **jamais** : elle *request* (`/request`), le dev implémente ou rejette.
2. Chaque auto-modif de prompt est versionnée, visible (`/prompt`), **réversible** par un humain.
3. Aucune clé API dans le prompt, dans le repo, ni dans les données (filtres à l'écriture).
4. Whitelist stricte de skills ; scraping limité en volume, whitelist de domaines optionnelle.
5. Le mode démo est déterministe et 100 % local : rien ne part sur le réseau sans clé configurée.

## 🗺 Roadmap

- [x] Monorepo + site statique (chat, /prompt, /data, /colab, /request, /contributeur)
- [x] Cœur IA multi-fournisseurs (Mistral prioritaire) + mode démo de la boucle d'auto-amélioration
- [x] Prompt système versionné + garde-fous mots-clés + auto-modification
- [x] Skills (search, modify_prompt, request_to_dev, add_research_task, …)
- [x] Service Chromium (Docker, prêt à déployer) + notebook Colab
- [x] Schéma Supabase
- [ ] Brancher `SCRAPER_SERVICE_URL` et tester un vrai scraping end-to-end
- [ ] Migrer les données vers Supabase (client déjà codé)
- [ ] Pas de réflexion LLM en mode live (aujourd'hui : l'IA se corrige via sa mission dans le prompt ; v2 : appel dédié d'analyse post-réponse)
- [ ] Évaluation des auto-modifs (le prompt v2 est-il mieux que v1 ? métriques sur un jeu de questions)
- [ ] Auth sur le scraper + file d'attente des tâches
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
