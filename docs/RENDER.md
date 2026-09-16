# 📘 Tutoriel Render — déploiement de AI-improves-itself

Guide pas-à-pas pour déployer le projet sur [Render](https://render.com) à l'aide du
**Blueprint** (`render.yaml` à la racine). À la fin, tu auras :

```
https://aiis-core.onrender.com/   ← site + chat IA + API (le produit)
```

> ⏱ Durée estimée : **15-20 minutes** (build Python, pas de Docker).
> 💰 Coût : **0 $** — le service du `render.yaml` est sur le plan `free`
> (0,1 CPU / 512 Mo RAM), la **seule** machine gratuite de Render. Tout le reste
> est payant : `0.5c-512mb` = 7 $/mois, `1c-2g` (2 Go) = **25 $/mois**, `2c-4g` = 85 $/mois.
> Il n'existe même pas de machine web à 1 Go : l'échelle passe de 512 Mo à 2 Go
> (prix relevés sur [render.com/pricing](https://render.com/pricing) et
> [docs.render.com/compute-plans](https://render.com/docs/compute-plans) le 2026-09-14).

---

## 0. Prérequis

| Ce qu'il faut | Où | Coût |
|---|---|---|
| Compte GitHub + ce repo poussé | ✅ déjà fait (contenu sur la branche `main`) | 0 $ |
| Compte Render | [render.com](https://render.com) → *Sign up with GitHub* → workspace **Hobby** | 0 $ (plan `free` : 512 Mo) |
| Clé API **Mistral** (moteur principal, + vision) | [console.mistral.ai/cle](https://console.mistral.ai/cle) → plan gratuit « La Plateforme » | 0 $ |
| (optionnel) Clé Gemini / Groq / OpenRouter | fallbacks automatiques | 0 $ |
| (**recommandé**) Repo GitHub **privé** + token (base de données, §4) | [github.com/new](https://github.com/new) + [tokens](https://github.com/settings/personal-access-tokens) → Contents : Read and write sur ce seul repo | 0 $ |
| (optionnel) Compte Supabase (base de données alternative, §4) | [supabase.com](https://supabase.com) | 0 $ (free tier) |

> **Important — repo privé ?** Le repo `AI-improves-itself` est actuellement privé.
> Quand tu connectes Render à GitHub, la pop-up d'autorisation doit autoriser Render à
> **lire les repos privés** (case « Private repositories »). Sans ça, le repo ne sera
> pas listé.

> **Quelle branche ?** Le Blueprint se déploie depuis **une seule branche** : `main`
> (tout le contenu est mergé dessus). Chaque push sur `main` redéploie le service
> automatiquement (`autoDeploy: true`).

---

## 1. Créer le Blueprint (le service d'un coup)

1. Sur Render : **New → Blueprint** (pas « Web Service » — le Blueprint lit le `render.yaml`).
2. **Repository** : `Snowoo-2z/AI-improves-itself`.
3. **Branch** : `main` (ou la branche `arena/...` si tu déploies directement dessus).
4. Render détecte `render.yaml` et affiche le service à créer :
   - `aiis-core` (web, python)
5. C'est là que Render te demande les **env vars** marquées `sync: false`
   (table complète au §2). Tu peux aussi laisser vides puis les remplir dans le dashboard
   avant le premier déploiement.
6. **Confirm** → Render crée le service.

---

## 2. Les variables d'environnement (la partie qui compte)

### Service `aiis-core` (le site + l'API)

| Variable | Valeur | Obligatoire ? |
|---|---|---|
| `MISTRAL_API_KEY` | ta clé Mistral (`mI-…`) | **oui** (sinon mode démo — pas de vision) |
| `GEMINI_API_KEY` | clé Google AI Studio | non (fallback) |
| `GROQ_API_KEY` | clé Groq | non (fallback) |
| `OPENROUTER_API_KEY` | clé OpenRouter | non (fallback) |
| `STORE_BACKEND` | `auto` (défaut — déjà dans le Blueprint) | non (forcer : `local` / `github` / `supabase`) |
| `GITHUB_TOKEN` | token fine-grained → Contents Read+write sur le repo de données **uniquement** | **oui si backend GitHub** (§4) |
| `GITHUB_REPO` | `TON-COMPTE/ton-repo-data-prive` | **oui si backend GitHub** (§4) |
| `RESEARCH_TASKS_PATH` | chemin des tâches dans le repo de données (défaut `colab/tasks.json`) | non (voir §4) |
| `SUPABASE_URL` | `https://xxxx.supabase.co` (alternative au backend GitHub) | non |
| `SUPABASE_SERVICE_KEY` | `sb_…` (page projet → API keys → service_role) | non |
| `MAIN_SITE_URL` | URL publique de `aiis-core` lui-même (visible après déploiement) | non (utilisée par le notebook Colab pour tirer/pousser tâches et résultats) |

Où récupérer les clés :
- **Mistral** : [console.mistral.ai](https://console.mistral.ai) → *La Plateforme* (gratuit) → *My Keys* → *Create a new API Key*. Le modèle par défaut `ministral-8b-latest` est déjà configuré — il est **multimodal** : le chat accepte les images.
- **Gemini** : [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → *Create API key*.
- **Groq** : [console.groq.com/keys](https://console.groq.com/keys).
- **OpenRouter** : [openrouter.ai/keys](https://openrouter.ai/keys) (réglage par défaut : `openrouter/free`, l'auto-routeur officiel — la liste des `:free` tourne en permanence, ne pas coder un ID en dur).
- **NVIDIA NIM** (5ᵉ secours optionnel) : [build.nvidia.com](https://build.nvidia.com/) → `NVIDIA_API_KEY`.
- **GitHub (base de données)** : repo privé + token — procédure complète : [docs/GITHUB-BACKEND.md](GITHUB-BACKEND.md).

> ⚠️ Les IDs de modèles gratuits meurent vite (Groq a coupé `llama-3.3-70b-versatile` le
> 16/08/2026, Mistral a retiré Medium 3/3.1 le 31/08/2026 et la ligne Magistral le
> 31/07/2026). Avant chaque déploiement, comparer tes `*_MODEL` avec
> [docs/FREE-TIERS.md](FREE-TIERS.md) — le cœur affiche un message explicite
> (« modèle retiré → remplacement conseillé ») au lieu d'un 429 trompeur.

---

## 3. Déployer `aiis-core` et vérifier que tout marche

1. Ouvre `https://aiis-core.onrender.com/` → le site s'affiche, thème sombre.
2. Dans la **sidebar**, le chip de statut doit afficher **`MISTRAL`** et non
   « démo locale ». Sinon → revoir `MISTRAL_API_KEY` dans l'onglet *Environment*
   puis redéployer.
3. Teste le chat (la boucle d'auto-amélioration) :
   - **« Quel est le dernier jeu Zelda ? »** → 1ʳᵉ réponse peut être imparfaite ;
   - si l'IA détecte un défaut, elle s'auto-corrige (carte « L'IA a modifié son prompt » dans le chat) ;
   - la 2ᵉ question doit être correcte.
4. Teste la **vision** : clique 📎 (ou colle une image, ex. une capture d'écran) dans le
   composer, puis envoie « Décris cette image ». Le modèle `ministral-8b-latest` répond
   en décrivant l'image.
5. Vérifie les pages : `/prompt.html`, `/data.html`, `/colab.html`, `/request.html`,
   `/contributeur.html`.

> 💡 **Logs** : onglet *Logs* du service = temps réel. Les erreurs de skills
> s'affichent préfixées `[skills]`. Les warnings de chat (provider en échec, fallback)
> sont renvoyés dans la réponse API sous `warnings`.

---

## 4. Brancher une vraie base de données (indispensable sur Render !)

> ⚠️ **Pourquoi indispensable ?** Le plan `free` a un filesystem **éphémère** : sans
> backend distant, chaque redéploiement/redémarrage **efface** les requêtes, tâches,
> résultats et connaissances (retour aux JSON du repo git). Avec un backend, tout
> survit. À noter : les **prompts auto-modifiés** par l'IA restent eux éphémères
> (reset à la version git à chaque redéploiement) — garde-fou acceptable : l'humain
> garde le contrôle, et l'historique git fait foi.

### Option A — GitHub (recommandé : 0 $, aucun compte en plus)

1. Suivre **[docs/GITHUB-BACKEND.md](GITHUB-BACKEND.md)** (repo privé + token fine-grained
   Contents Read+write).
2. Dans `aiis-core` → *Environment* → renseigner `GITHUB_TOKEN` + `GITHUB_REPO`
   (`STORE_BACKEND` vaut déjà `auto` via le Blueprint) → **Manual Deploy**.
3. Vérifier : `GET /api/status` → `"store_backend": "github"`. Ouvre une requête sur
   Request : un commit `data: dev_requests (…)` doit apparaître dans le repo de données.
4. Les **tâches de recherche** (créées par l'IA ou le formulaire `/colab`) sont écrites
   dans le repo à `RESEARCH_TASKS_PATH` (défaut `colab/tasks.json`) — c'est ce fichier
   que le notebook Colab exécute.

### Option B — Supabase (alternative)

1. [supabase.com](https://supabase.com) → *New project* (free tier).
2. **SQL Editor** → New query → coller le contenu de **`supabase/schema.sql`** → *Run*.
   (7 tables : `prompts`, `prompt_versions`, `skills`, `dev_requests`,
   `research_tasks`, `research_results`, `knowledge` + RLS lecture ouverte.)
3. Onglet **Project Settings → API** :
   - `SUPABASE_URL` = `Project URL`
   - `SUPABASE_SERVICE_KEY` = `service_role` (⚠️ jamais dans le repo — env var Render uniquement)
4. Dans `aiis-core` → *Environment* → ajouter/modifier les 2 variables → *Manual Deploy*.
5. La persistance bascule **automatiquement** (le code détecte les 2 variables ;
   sinon backend GitHub si configuré, sinon JSON local).

---

## 5. (Optionnel) Brancher le notebook Colab

1. Sur GitHub, ouvre `colab/main.ipynb` → **File → Open notebook… → Colab**
   (ou *Import notebook* depuis un notebook vierge).
2. Cellule de config : `MAIN_SITE_URL` est **pré-remplie** avec
   `https://aiis-core.onrender.com` (= `MAIN_SITE_URL` du service, §2) —
   rien à changer. Le script la détecte de toute façon automatiquement
   (env → `colab/main_site_url.txt` → défaut versionné).
3. **Runtime → Run all** :
   - le script **tire les tâches depuis l'API** (`GET /api/research/tasks`) et les
     fusionne avec `tasks.json` local — c'est comme ça qu'il voit les tâches créées
     via le chat sur Render (backend GitHub, plus de fichier local partagé) ;
   - les tâches `pending` s'exécutent (recherche DuckDuckGo sans clé + fetch de pages simples) ;
   - statuts (`PATCH`) et résultats (`POST /api/research/results`) sont repoussés au site.
4. Sur le site : `/colab.html` → les tâches passent `done`, les résultats apparaissent.
   Dans le chat : **« Quelles sont les dernières recherches ? »** (skill `list_research_results`).

> ⏳ Les sessions Colab sont limitées dans le temps (RAM gratuite ~12 h max) :
> le script sauvegarde de façon incrémentale (`tasks.json`/`results.json` mis à jour
> après chaque tâche) → rien n'est perdu en cas de coupure.
> `MAIN_SITE_URL` est détectée automatiquement (défaut versionné
> `https://aiis-core.onrender.com`) — inutile de la configurer, sauf pour pointer
> une autre instance.

---

## 6. Vie quotidienne (après le déploiement)

| Besoin | Où |
|---|---|
| Modifier une env var | *Settings → Environment* → puis **Manual Deploy** obligatoire |
| Redéployer à la main | *Manual Deploy → Deploy latest commit* |
| **Rollback** | onglet **Events** → trouver le commit voulu → *Redeploy from this commit* |
| Logs temps réel | onglet **Logs** (recherche possible) |
| Renommer le sous-domaine | *Settings → Name* (l'URL `.onrender.com` suit) |
| Domaine custom | *Settings → Custom Domain* (DNS CNAME) |
| Changer de plan | *Settings → Plan* : `free` (512 Mo, 0 $) → `0.5c-512mb` (7 $) → `1c-2g` (2 Go, 25 $) — changement appliqué au redéploiement |
| Arrêter / laisser dormir | bouton *Stop* ; en plan `free` l'instance s'endort seule après 15 min d'inactivité (pas de disque persistant sur ce plan) |
| Push → auto-déploiement | activé (`autoDeploy: true`) : chaque push sur la branche choisie déploie |

**Flux de travail recommandé :**
1. Tu modifies le code (ou l'IA propose via `/request`).
2. Tu pousses sur la branche du Blueprint.
3. Render redéploie automatiquement (2-5 min pour `aiis-core`).
4. Si souci → *Events → Redeploy from* le dernier bon commit (rollback en 30 s).

---

## 7. Coût & alternative 100 % gratuite

Règle de base Render (vérifiée sur [render.com/pricing](https://render.com/pricing)
et [docs.render.com/free](https://render.com/docs/free) le **2026-09-14**) :
**seule la machine de 512 Mo est gratuite** (`plan: free` = 0,1 CPU / 512 Mo).
Dès qu'on monte en CPU/RAM, c'est payant — et il n'existe **aucun** palier web à 1 Go :
l'échelle des web services est `free` (512 Mo) → `0.5c-512mb` (512 Mo, 7 $) → `1c-2g`
(2 Go, 25 $) → `2c-4g` (4 Go, 85 $). Le plan `0.5c-1g` (1 Go) n'existe qu'en **Postgres**
(19 $/mois).

| Solution | Coût | Notes |
|---|---|---|
| **Render en `free`** (ce tuto) | **0 $** | 512 Mo, suffisant pour FastAPI + le site statique. ⚠️ l'instance s'endort après 15 min sans requête (~1 min au réveil) et le filesystem est éphémère → backend GitHub recommandé (§4) |
| **Render en `1c-2g`** | 25 $/mois | 2 Go + 1 vCPU, always-on, disque persistant. Étape intermédiaire : `0.5c-512mb` = 7 $/mois (512 Mo, <1 vCPU), utile pour supprimer le spin-down |
| **Oracle Cloud Free Tier** | **0 $** | VM ARM (4 OCPU / 24 Go) *toujours* gratuite → `aiis-core` sur la même VM, sans quota horaire ; tu peux même ajouter le site sur le port 80 avec Caddy/nginx |
| **GitHub Pages** (site seul) + Render (API en `free`) | 0 $ (ou 7 $ sans spin-down) | le site statique est gratuit sur Pages ; mais il faut définir `API_BASE` dans `site/js/config.js` vers l'API (aujourd'hui le site et l'API sont censés être sur la même origine) |

---

## 8. Dépannage (les 90 % des cas)

| Symptôme | Cause probable | Correction |
|---|---|---|
| Site affiche « démo locale » au lieu de MISTRAL | `MISTRAL_API_KEY` absente/vide/mal collée | *Environment* → vérifier la clé (pas d'espaces) → **Manual Deploy** |
| `store_backend` reste `local` malgré les vars GitHub | Env vars vides/mal nommées, ou pas de redéploiement après ajout | Vérifier `GITHUB_TOKEN` + `GITHUB_REPO=owner/repo` → **Manual Deploy** (les env vars exigent un redéploiement) |
| `/api/status` en 500, sidebar vide | Token GitHub invalide (401) ou repo/branch inexistant | *Logs* → corriger `GITHUB_TOKEN`/`GITHUB_REPO`/`GITHUB_BRANCH` → redéployer. En attendant, `STORE_BACKEND=local` rétablit le site (données éphémères) |
| Données effacées après chaque déploiement | Pas de backend distant (filesystem éphémère du plan `free`) | §4 : brancher GitHub ou Supabase |
| Réponses très lentes au 1er message | Plan `free` : l'instance s'est endormie (15 min sans requête) → ~1 min de réveil | Normal ; la 2ᵉ requête est rapide. Pour supprimer le réveil : plan `0.5c-512mb` (7 $) ou `1c-2g` (25 $) |
| Site muet en fin de mois, puis retour au 1er du mois | Quota **750 h d'instance gratuites** du workspace épuisé | Laisser le service s'endormir (pas de trafic permanent) ou passer en payant |
| `aiis-core` 502 après déploiement | Crashe au boot | *Logs* : souvent `ModuleNotFoundError` → vérifier que le commit a bien `requirements.txt` |
| Image refusée dans le chat | > 2 Mo, plus de 4 images, ou format non image | Réduire l'image (capture d'écran, redimensionner) — le serveur valide avant l'appel LLM |
| Colab ne voit pas les tâches du chat | `MAIN_SITE_URL` pointe vers une autre instance ou le notebook est ancien | Vérifier la cellule de config (§5) : elle doit pointer `https://aiis-core.onrender.com` |
| Colab n'arrive pas à pousser les résultats | `MAIN_SITE_URL` vide ou http (Colab exige https pour certains domaines) | Mettre l'URL `https://…onrender.com` dans la cellule de config du notebook (pré-remplie par défaut) |
| Render ne voit pas le repo | Repo privé non autorisé | Reconnecter GitHub dans Render en cochant *Private repositories* |
| Push ne déclenche pas le déploiement | Le Blueprint a été créé sur une **autre branche** | *Settings → Branch* → choisir ta branche, ou merger sur la branche du Blueprint |

---

## 9. Checklist finale

- [ ] Blueprint créé (service `aiis-core`)
- [ ] Le service est sur le plan **`free`** (512 Mo, 0 $) — *Settings → Instance Type*
- [ ] `MISTRAL_API_KEY` (+ fallbacks optionnels) renseignés
- [ ] Site live → chip **MISTRAL** dans la sidebar (pas démo locale)
- [ ] Backend GitHub : `GITHUB_TOKEN` + `GITHUB_REPO` → redéployé → `/api/status` dit `"store_backend": "github"`
- [ ] Test chat « dernier Zelda » ×2
- [ ] Test vision : image jointe → description par `ministral-8b-latest`
- [ ] `/prompt.html` `/data.html` `/colab.html` `/request.html` `/contributeur.html` OK
- [ ] (alternative) Supabase : `schema.sql` exécuté + 2 variables
- [ ] (opt) Colab : notebook lancé, `MAIN_SITE_URL` configurée
