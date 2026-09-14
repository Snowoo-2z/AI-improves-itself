# Architecture — AI-improves-itself

Document de référence. Le README décrit le projet ; ce document décrit le **système**.

## 1. Vue d'ensemble

```
┌──────────────────────────────  SITE STATIQUE (site/)  ──────────────────────────────┐
│  / (chat)   /prompt   /data   /colab   /request   /contributeur                     │
└───────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │ fetch /api/* (même origine)
┌───────────────────────────────────────▼──────────────────────────────────────────────┐
│                          CŒUR IA (core/ — FastAPI)                                   │
│                                                                                      │
│  server.py ──► ai/chat.py (orchestration)                                            │
│                 │                                                                    │
│                 ├─► prompt_system/registry.py : assemble le prompt                   │
│                 │     (garde-fous mots-clés : main + code/recherche…)                │
│                 ├─► ai/providers.py : Mistral → Gemini → Groq → OpenRouter → démo    │
│                 ├─► skills/manager.py : whitelist d'outils (tool calling)            │
│                 └─► store.py : JSON local  ⇄  Supabase (PostgREST)                   │
│                                                                                      │
│  Pas de réflexion : après chaque réponse, défaut détecté →                           │
│  modify_prompt_system (versionné + historique + notif /request)                      │
└──────────────┬───────────────────────────────┬───────────────────────────────────────┘
               │ POST /scrape                  │ POST /api/research/results
┌──────────────▼──────────────┐   ┌────────────▼──────────────┐
│ services/scraper (Render)   │   │ colab/ (Google Colab)     │
│ FastAPI + Playwright/Chromium│  │ main.ipynb → main.py      │
│ rendu JS, texte de la page  │   │ search (DDG) / fetch      │
└─────────────────────────────┘   └───────────────────────────┘
               └────────────► base de connaissances ◄──────────
                    core/data/knowledge.json → Supabase (phase 2)
```

## 2. La boucle d'auto-amélioration (cœur du projet)

```
utilisateur ──question──► assemble prompt (main + modules par mots-clés)
                              │
                              ▼
                     appel LLM (tool calling)
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
        réponse finale                 appels de skills
              │                                │
              ▼                                ├─ search_knowledge (base de connaissances)
   PAS DE RÉFLEXION                           ├─ add_research_task (file /colab)
   analyser sa propre réponse                 ├─ request_to_dev (file /request)
              │                                ├─ list_research_results
    défaut détecté ?                          └─ update_skill_description
              ▼
   modify_prompt_system (scope, reason, new_content)
              │
   ┌──────────┼───────────────────────────────┐
   ▼          ▼                               ▼
version++  historique (30)            notif /request (type prompt_update)
   │          │                               │
   ▼          ▼                               ▼
page /prompt (visible, réversible)  └─────────► page /request (relecture humaine)
```

### Déclencheur du pas de réflexion

- **Mode démo (sans clé)** : règle déterministe dans `core/ai/chat.py`
  (`_demo_needs_reflection`) — reproduction exacte de l'exemple du README
  (question « dernier Zelda » → réponse 1986 → auto-corrige avec la règle
  `[REGLE-AJOUTEE-PAR-IA]` sur le tri par date).
- **Mode live (clé config)** : la mission 2 du prompt `main.json` instruit le modèle
  d'auto-analyser ses réponses et d'invoquer `modify_prompt_system`.
  **Phase suivante** : appel LLM dédié « analyse ta dernière réponse » (prompt de
  réflexion séparé, moins cher, plus fiable) + comparaison des versions.

## 3. Prompt système

- Stockage : `core/prompt_system/prompts/*.json` (versionné par git ET par `version` interne).
- Format : `{id, scope, version, content, keywords[], history[]}`.
- `scope: "global"` (main) toujours chargé ; les autres sont des **garde-fous** :
  chargés si un mot-clé du `keywords` apparaît dans le message utilisateur
  (`code.json` : code/bug/python/api… ; `recherche.json` : scrape/colab/veille…).
- Assemblage : `## PROMPT [id · scope · vN]` + contenu, un bloc par module.
- **Modifications IA** : skill `modify_prompt_system` → garde-fou sécurité
  (longueur 40–12 000 car, rejet si une clé API détectée y figure) → version++,
  historique (30 dernières) → notification `/request`.
- **Modifications humaines** : `POST /api/prompt-system/{scope}` (même pipeline, `author=human`).
- Réversibilité : l'historique garde le contenu complet de chaque version ;
  un `POST` avec l'ancien contenu restaure (roadmap : bouton « rollback » sur /prompt).

## 4. Skills (outils de l'IA)

| id | rôle | notes |
|---|---|---|
| `search_knowledge` | interroge la base de connaissances | `use_date=true` → tri date décroissante. **Le bug documenté** (ordre d'insertion sinon) est le défaut que l'IA découvre et corrige. |
| `modify_prompt_system` | le cœur : édite son prompt | versionné, historisé, notifié. |
| `request_to_dev` | ouvre une requête /request | feature/ui/bug/skill/other. |
| `add_research_task` | programme une tâche /colab | search (requête) / fetch (URL). |
| `list_research_results` | lit les derniers résultats | exécutés par Colab/Chromium. |
| `update_skill_description` | affine la description d'une skill | persistée dans `core/skills/descriptions.json` (reviewable en git). |

Sécurité : whitelist stricte (n'importe quel nom non référencé = refus), arguments
validés par les handlers, aucune skill n'exécute de code arbitraire.

## 5. Multi-fournisseurs

`core/ai/providers.py` : chaîne construite à partir de `.env` —
**Mistral** (priorité, `mistral-small-latest`) → **Gemini** → **Groq** → **OpenRouter** →
**demo-local** (déterministe, toujours disponible).

Tous les providers cloud passent par le protocole OpenAI-compatible
(`chat/completions` + `tools`) → un seul client, bascule facile, et le
test de connexion d'un provider se fait avec un ping de 1 token avant la vraie
conversation (le premier provider échouant bascule automatiquement).

Clés (toutes optionnelles, offres gratuites) :
- Mistral « La Plateforme » : `MISTRAL_API_KEY`
- Google AI Studio : `GEMINI_API_KEY`
- Groq console : `GROQ_API_KEY`
- OpenRouter : `OPENROUTER_API_KEY`

## 6. Recherche web (2 exécutants, 1 file)

File unique : `research_tasks` (Supabase ou `core/data/research_tasks.json`).

| Exécutant | Tâches | Déploiement | Points forts |
|---|---|---|---|
| **Colab** (`colab/`) | `search` (DuckDuckGo, sans clé), `fetch` (pages simples) | 100 % gratuit, session limitée | RAM gratuite, idéal recherche documentaire |
| **Chromium** (`services/scraper/`) | `fetch` pages à rendu JS | Render Basic 512 Mo / Oracle Free / Fly.io | rendu complet (Playwright) |

Flux : IA → tâche `pending` → exécutant → `done` + `research_results` →
l'IA lit via `list_research_results` → décide (étude, mise à jour de la base).
Le scraper a une whitelist de domaines optionnelle (`ALLOWED_DOMAINS`) et un
plafond de caractères ; l'objectif est la **recherche ponctuelle**, pas le crawl.

## 7. Base de données

- **Phase 1 (actuel)** : `LocalStore` (JSON dans `core/data/`) — zéro config,
  `knowledge.json` seedée (Zelda, Mistral, Supabase…).
- **Phase 2** : `SupabaseStore` (déjà codé, PostgREST minimal, sans SDK) —
  bascule automatique si `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` sont dans `.env`.
  Schéma : `supabase/schema.sql` (prompts, prompt_versions, skills, dev_requests,
  research_tasks, research_results, knowledge + RLS lecture ouverte, écriture via
  clé service).
- Phase 3 : repo GitHub **privé** comme archive brute des données de recherche
  (suivant la vision du README).

## 8. Sécurité & garde-fous humains

1. **L'IA ne code jamais.** Elle ouvre des requêtes (`/request`, type `skill`/`feature`) ;
   le dev implémente ou rejette. Seuls les *descriptions* de skills sont auto-modifiables.
2. **Prompts** : versionnés, historisés, visibles (/prompt), réversibles ; filtre anti-clés
   API à l'écriture ; longueur bornée.
3. **Clés** : uniquement dans `.env` (gitignored) ; jamais injectées dans les prompts ;
   jamais renvoyées par l'API.
4. **API** : en l'état, publique en lecture (c'est un site de recherche).
   Écrire demande un `POST` — phase suivante : auth (Supabase Auth) + token pour
   l'écriture des résultats Colab, rate limiting.
5. **Scraping** : whitelist de domaines optionnelle, plafond de taille, UA honnête,
   usage ponctuel (robots.txt des cibles).

## 9. Déploiement (100 % gratuit, sauf le scraper)

| Brique | Où | Coût |
|---|---|---|
| Site statique + API (core/) | GitHub Pages (site seul) **ou** un seul web service Free (Render/Railway/Oracle) pour tout garder ensemble | 0 $ |
| Base | Supabase free tier | 0 $ |
| Recherche | Google Colab | 0 $ |
| Scraper Chromium | Render Basic 512 Mo **ou** Oracle Cloud Free Tier (ARM) / Fly.io | 5-7 $/mois **ou** 0 $ (Oracle) |

Recommandation v0 : tout tourner sur **Oracle Cloud Free Tier** (VM 4 ARM gratuite) :
serveur du projet + Chromium au même endroit, zéro coût, et `SCRAPER_SERVICE_URL`
pointe sur la même VM.

## 10. Extensions prévues

- **Évaluation** : jeu de questions de référence + score avant/après chaque version de prompt
  (l'auto-amélioration doit être *mesurable*, sinon c'est de la dérive).
- **Rollback 1 clic** sur /prompt (déjà possible via l'API).
- **Prompt de réflexion dédié** en mode live (analyse post-réponse avec un modèle cheap).
- **Skills humaines via /request** : template de PR + checklist.
- **Auth** (Supabase Auth) pour l'écriture (résultats Colab, édition prompts).
- **i18n** du site (FR → EN).
