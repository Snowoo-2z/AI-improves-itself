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
│                 │     (+ vision : blocs image_url → `ministral-8b-latest`)           │
│                 ├─► skills/manager.py : whitelist d'outils (tool calling)            │
│                 └─► store.py : JSON local  ⇄  GitHub  ⇄  Supabase (PostgREST)        │
│                                                                                      │
│  Pas de réflexion : après chaque réponse, défaut détecté →                           │
│  modify_prompt_system (versionné + historique + notif /request)                      │
└──────────────┬───────────────────────────────────────────────────────────────────────┘
               │ POST /api/research/tasks (pull)  ·  POST /api/research/results (push)
┌──────────────▼──────────────────────┐
│ colab/ (Google Colab)               │
│ main.ipynb → main.py                │
│ search (DDG) / fetch / note         │
└──────────────┬──────────────────────┘
               └────────────► base de connaissances ◄──────────
                    core/data/knowledge.json → GitHub/Supabase (phase 2)
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
    défaut détecté ?                          ├─ add_knowledge (mémoriser une info)
              ▼                                └─ update_skill_description
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
- Assemblage : `## DATE DU JOUR (…)` en tête (l'IA sait « aujourd'hui » ; ce
  bloc est généré par `registry.current_date_header()`) puis
  `## PROMPT [id · scope · vN]` + contenu, un bloc par module.
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
| `list_research_results` | lit les derniers résultats | exécutés par le notebook Colab. |
| `add_knowledge` | ajoute une entrée à la base | `{title, category, date, summary, source}` — l'IA mémorise une info vérifiée. |
| `update_skill_description` | affine la description d'une skill | persistée dans `core/skills/descriptions.json` (reviewable en git). |

Sécurité : whitelist stricte (n'importe quel nom non référencé = refus), arguments
validés par les handlers, aucune skill n'exécute de code arbitraire.

## 5. Multi-fournisseurs

`core/ai/providers.py` (+ le catalogue `core/ai/limits.py`) : chaîne construite à
partir de `.env` — **Mistral** (priorité, `ministral-8b-latest` puis
`mistral-small-latest`, `mistral-large-2411`, `ministral-3b-latest`) → **Gemini** →
**Groq** → **OpenRouter** → **NVIDIA NIM** (optionnel) → **demo-local**
(déterministe, toujours disponible).

Tous les providers cloud passent par le protocole OpenAI-compatible
(`chat/completions` + `tools`) → un seul client, bascule facile.

Gestion des tiers gratuits (chiffres et sources dans [FREE-TIERS.md](FREE-TIERS.md)) :

| Mécanisme | Pourquoi |
|---|---|
| **Throttle en amont** (intervalle minimal déduit du débit publié) | la rafale crée le 429 ; sur OpenRouter les requêtes refusées comptent dans le quota du jour |
| **Rotation de modèles dans le même provider** | les quotas gratuits sont souvent séparés par modèle (pool isolé pour `mistral-large-2411`) |
| **Aucun retry sur 429** (on tourne tout de suite) | mitrailler un modèle en 429 brûle du quota pour rien |
| **Repli en cascade** (`chat_with_failover`) | un 429 Mistral ne bascule plus le site en démo si une clé Groq/Gemini valide existe |
| **Disjoncteur par moteur** (`HealthRegistry`) | repos calé sur l'annonce de l'API : `Retry-After`, `x-ratelimit-reset-*`, fenêtre du jour (minuit Pacifique pour Google), mois (1er), ou 1 h pour une erreur de configuration |
| **Classification des erreurs** (`classify_failure`) | 401/403/404/402 = configuration (rien d'attendre, message actionnable) ; 429 = quota ; 5xx/réseau = passager ; **200 + corps d'erreur** (OpenRouter) = échec à replier |
| **`RETIRED_MODELS`** | un ID mort devient « modèle retiré le JJ/MM → remplacement conseillé » au lieu d'un 429 trompeur |
| **Visibilité** | `/api/status` (état, repos restant, modèle, en-têtes de quota), `warnings`/`attempts`/`provider_retry_in_human` dans `/api/chat`, `POST /api/providers/retest` |

Le test de connexion (ping de 1 token) n'est plus systématique à chaque message :
il coûte un appel sur des tiers à 50 req/jour. Il sert au re-test forcé
(`/api/providers/retest`) et au premier choix de moteur.

Clés (toutes optionnelles, offres gratuites) :
- Mistral « La Plateforme » : `MISTRAL_API_KEY`
- Google AI Studio : `GEMINI_API_KEY`
- Groq console : `GROQ_API_KEY`
- OpenRouter : `OPENROUTER_API_KEY`

## 6. Recherche web (1 exécutant, 1 file)

File unique : `research_tasks`, stockée AVEC la base de données (table
`research_tasks` sur Supabase, `data/research_tasks.json` sur le backend GitHub,
`core/data/research_tasks.json` en local — l'ancien `colab/tasks.json` est migré
automatiquement). Le **scraper Chromium (`services/scraper/`) a été retiré** : il ne
servait plus, la recherche s'exécute uniquement via le notebook Colab.

| Exécutant | Tâches | Déploiement | Points forts |
|---|---|---|---|
| **Colab** (`colab/`, v2) | `search` (multi-moteurs sans clé : DDG HTML → DDG lite → Wikipédia, avec extraits), `deep` (search + lecture auto des meilleures pages), `fetch` (titre + texte, robots.txt honoré), `note` | 100 % gratuit, session limitée | RAM gratuite, idéal recherche documentaire |

Flux : IA → tâche `pending` → Colab (réveil serveur, fusion monotone des files,
exécution, résumé local optionnel par clé API, push idempotent avec retry,
attente du bilan d'étude) → `done` + `research_results` → l'IA lit via
`list_research_results` → décide (étude, mise à jour de la base).

**Étude des résultats (sur le site)** — `core/research/service.py` :
quand Colab pousse un résultat (`POST /api/research/results`), le site déclenche
l'étude **en arrière-plan** (le POST répond immédiatement ; le bilan `study` est
réécrit sur le résultat, visible sur /colab). Deux appels LLM par résultat, sans
aucune clé dans Colab :
1. **structuration** (1er appel) : le brut est transformé en entrée de base
   `{title, category, date, summary, source}` + une confiance de 0 à 1 ;
2. **vérification** (2e appel) : pertinence/cohérence/source de l'entrée
   proposée — `approve=false` ou confiance < 0,55 ⇒ rien n'est écrit.
Chaque appel reçoit explicitement la **date du jour** (sinon l'IA ne sait pas
dater une info web). Écriture seulement si les deux passes acceptent et si
l'entrée n'est pas un doublon (titre/summary identiques).
Le `fetch` honore les robots.txt de la cible ; l'objectif est la
**recherche ponctuelle**, pas le crawl.

### Vision (analyse d'images)

Le chat accepte les images (bouton 📎 ou collage) : le front les encode en
data-URL base64 (max 4 / 2 Mo, aucun stockage serveur) et les envoie dans le
`content` du message (`{type:"image_url", image_url:{url}}`). Le moteur
`ministral-8b-latest` (multimodal) les reçoit et les décrit. En mode démo
(aucune clé), la réponse explique que la vision n'est pas disponible.

## 7. Base de données

- **Phase 1 (actuel)** : `LocalStore` (JSON dans `core/data/`, tâches dans
  `core/data/research_tasks.json`) — zéro config, `knowledge.json` seedée (Zelda,
  Mistral, Supabase…).
- **Backend GitHub** : `GitHubStore` (déjà codé) — un fichier JSON par collection
  dans un repo GitHub privé, activé par `GITHUB_TOKEN` + `GITHUB_REPO`. Les tâches
  de recherche y sont **synchronisées** (créées par l'IA ou par un humain), au
  chemin `RESEARCH_TASKS_PATH` (voir `docs/GITHUB-BACKEND.md` §5).
- **Phase 2** : `SupabaseStore` (déjà codé, PostgREST minimal, sans SDK) —
  bascule automatique si `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` sont dans `.env`.
  Schéma : `supabase/schema.sql` (prompts, prompt_versions, skills, dev_requests,
  research_tasks, research_results, knowledge + RLS lecture ouverte, écriture via
  clé service).

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
5. **Recherche web** : tasks `search`/`fetch` ponctuelles, UA honnête, usage
   raisonnable (robots.txt des cibles). Les images du chat sont validées (4 max,
   2 Mo, format image) avant tout appel LLM.
6. **Boucle d'outils bornée** : UN SEUL appel d'outil exécuté par réponse de
   l'IA (`MAX_PARALLEL_TOOL_CALLS = 1` dans `core/ai/chat.py`) — une rafale
   d'appels parallèles multiplie les allers-retours LLM, grille les quotas des
   tiers gratuits et finissait par « bloquer » le chat ; les appels groupés
   au-delà du premier reçoivent un refus pédagogique (protocole OpenAI respecté)
   invitant l'IA à les rejouer un par un. Au plus 3 tours d'outils sur un même
   message (`TOOL_ITERATION_HARD_LIMIT`) : au-delà, l'historique d'outil est
   coupé et l'excès signalé au dev (/request).

## 9. Déploiement (100 % gratuit)

| Brique | Où | Coût |
|---|---|---|
| Site statique + API (core/) | GitHub Pages (site seul) **ou** un seul web service `free` (Render/Railway/Oracle) pour tout garder ensemble | 0 $ |
| Base | backend GitHub (repo privé, un fichier par collection) **ou** Supabase free tier | 0 $ |
| Recherche | Google Colab | 0 $ |
| Vision | incluse dans l'appel Mistral (`ministral-8b-latest`), aucun service en plus | 0 $ |

> Rappel tarifs Render (vérifié le 2026-09-14 sur render.com/pricing et
> docs.render.com/compute-plans) : seule la machine **0,1 CPU / 512 Mo** est gratuite
> (`plan: free`). Payant : `0.5c-512mb` 7 $/mois, `1c-2g` (2 Go) 25 $/mois, `2c-4g`
> 85 $/mois — pas de palier web à 1 Go (l'échelle saute de 512 Mo à 2 Go).
> Fly.io n'a plus de tier gratuit pour les comptes créés après le 7 oct. 2024.

Recommandation v0 : tout faire tourner sur **Oracle Cloud Free Tier** (VM ARM 4/24 Go
toujours gratuite) : serveur du projet au même endroit, zéro coût.

## 10. Extensions prévues

- **Évaluation** : jeu de questions de référence + score avant/après chaque version de prompt
  (l'auto-amélioration doit être *mesurable*, sinon c'est de la dérive).
- **Rollback 1 clic** sur /prompt (déjà possible via l'API).
- **Prompt de réflexion dédié** en mode live (analyse post-réponse avec un modèle cheap).
- **Skills humaines via /request** : template de PR + checklist.
- **Auth** (Supabase Auth) pour l'écriture (résultats Colab, édition prompts).
- **i18n** du site (FR → EN).
