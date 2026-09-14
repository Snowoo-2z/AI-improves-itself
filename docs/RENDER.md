# 📘 Tutoriel Render — déploiement complet de AI-improves-itself

Guide pas-à-pas pour déployer le projet sur [Render](https://render.com) à l'aide du
**Blueprint** (`render.yaml` à la racine). À la fin, tu auras :

```
https://aiis-core.onrender.com/      ← site + chat IA (le produit)
https://aiis-scraper.onrender.com/   ← service de scraping Chromium
```

> ⏱ Durée estimée : **30-45 minutes** (le build Docker du scraper prend 5-10 min).
> 💰 Coût : 2 × `1c-2g` (1 vCPU / 2 Go) ≈ 16-24 $/mois (détail + alternative gratuite en §9).

---

## 0. Prérequis

| Ce qu'il faut | Où | Coût |
|---|---|---|
| Compte GitHub + ce repo poussé | ✅ déjà fait (branche `arena/01a0a0aa-ai-improves-itself`) | 0 $ |
| Compte Render | [render.com](https://render.com) → *Sign up with GitHub* | — |
| Clé API **Mistral** (moteur principal) | [console.mistral.ai/cle](https://console.mistral.ai/cle) → plan gratuit « La Plateforme » | 0 $ |
| (optionnel) Clé Gemini / Groq / OpenRouter | fallbacks automatiques | 0 $ |
| (optionnel) Compte Supabase (base de données, phase 2) | [supabase.com](https://supabase.com) | 0 $ (free tier) |

> **Important — repo privé ?** Le repo `AI-improves-itself` est actuellement privé.
> Quand tu connectes Render à GitHub, la pop-up d'autorisation doit autoriser Render à
> **lire les repos privés** (case « Private repositories »). Sans ça, le repo ne sera
> pas listé.

> **Quelle branche ?** Le Blueprint se déploie depuis **une seule branche**.
> - Soit tu choisis la branche `arena/01a0a0aa-ai-improves-itself` (le contenu actuel),
> - soit tu crées d'abord une **Pull Request** (GitHub propose le lien automatiquement à
>   chaque push) et la merges sur `main`, puis tu déploies depuis `main` (recommandé pour
>   la suite — tout le repo pointe sur `main`).

---

## 1. Créer le Blueprint (les 2 services d'un coup)

1. Sur Render : **New → Blueprint** (pas « Web Service » — le Blueprint lit le `render.yaml`).
2. **Repository** : `Snowoo-2z/AI-improves-itself`.
3. **Branch** : `main` (ou la branche `arena/...` si tu déploies directement dessus).
4. Render détecte `render.yaml` et affiche les 2 services à créer :
   - `aiis-core` (web, python)
   - `aiis-scraper` (web, Docker)
5. C'est là que Render te demande les **env vars** marquées `sync: false`
   (table complète au §2). Tu peux aussi laisser vides puis les remplir dans le dashboard
   avant le premier déploiement.
6. **Confirm** → Render crée les 2 services.

---

## 2. Les variables d'environnement (la partie qui compte)

### Service `aiis-core` (le site + l'API)

| Variable | Valeur | Obligatoire ? |
|---|---|---|
| `MISTRAL_API_KEY` | ta clé Mistral (`mI-…`) | **oui** (sinon mode démo) |
| `GEMINI_API_KEY` | clé Google AI Studio | non (fallback) |
| `GROQ_API_KEY` | clé Groq | non (fallback) |
| `OPENROUTER_API_KEY` | clé OpenRouter | non (fallback) |
| `SUPABASE_URL` | `https://xxxx.supabase.co` (phase 2) | non (JSON local en attendant) |
| `SUPABASE_SERVICE_KEY` | `sb_…` (page projet → API keys → service_role) | non |
| `SCRAPER_SERVICE_URL` | URL publique de `aiis-scraper` → **remplir au §5** | non (le scraping en sera juste désactivé) |
| `MAIN_SITE_URL` | URL publique de `aiis-core` lui-même (visible après déploiement) | non (utilisée par le notebook Colab pour renvoyer les résultats) |

Où récupérer les clés :
- **Mistral** : [console.mistral.ai](https://console.mistral.ai) → *La Plateforme* (gratuit) → *My Keys* → *Create a new API Key*. Le modèle par défaut `mistral-small-latest` est déjà configuré ; pour changer : variable `MISTRAL_MODEL`.
- **Gemini** : [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → *Create API key*.
- **Groq** : [console.groq.com/keys](https://console.groq.com/keys).
- **OpenRouter** : [openrouter.ai/keys](https://openrouter.ai/keys) (modèle par défaut gratuit : `meta-llama/llama-3.3-70b-instruct:free`).

### Service `aiis-scraper` (Chromium)

| Variable | Valeur | Obligatoire ? |
|---|---|---|
| `ALLOWED_DOMAINS` | ex. `wikipedia.org,wikimedia.org,example.com` | non — vide = tous les domaines |

---

## 3. Déployer d'abord le scraper

L'ordre compte : `aiis-core` a besoin de l'URL du scraper.

1. Ouvre le service **`aiis-scraper`** → l'image Docker se build (5-10 min :
   `pip install` + téléchargement de **Chromium** et de ses dépendances — c'est normal,
   surveille les *Logs* : l'étape `playwright install chromium` est la plus longue).
2. Quand le statut passe à **Live**, note l'URL : `https://aiis-scraper.onrender.com`.
3. Teste : ouvre `https://aiis-scraper.onrender.com/health` dans le navigateur →
   tu dois voir `{"ok":true,"service":"scraper-chromium","ts":…}`.

> ⚠️ **First deploy = instance « froide »** : le 1er appel au scraper peut prendre
> 30-60 s (mise en route de l'instance). Teste deux fois.

---

## 4. Renseigner l'URL du scraper dans `aiis-core`

1. Service **`aiis-core`** → onglet **Environment** (dans *Settings*).
2. **Add Environment Variable** → `SCRAPER_SERVICE_URL` = `https://aiis-scraper.onrender.com`.
3. (recommandé) `MAIN_SITE_URL` = l'URL publique de `aiis-core`
   (visible en haut du service, ex. `https://aiis-core.onrender.com`).
   → Utilisée par le notebook Colab pour renvoyer automatiquement les résultats (§7).
4. Render propose de **redéployer** (les changements d'env var exigent un nouveau déploiement) → *Manual Deploy*.

---

## 5. Déployer `aiis-core` et vérifier que tout marche

1. Ouvre `https://aiis-core.onrender.com/` → le site s'affiche, thème sombre.
2. En haut à droite, le chip de statut doit afficher **`MISTRAL`** (et non « MODE DÉMO »).
   Sinon → revoir `MISTRAL_API_KEY` dans l'onglet *Environment* puis redéployer.
3. Teste le chat (la boucle d'auto-amélioration) :
   - **« Quel est le dernier jeu Zelda ? »** → 1ʳᵉ réponse peut être imparfaite ;
   - si l'IA détecte un défaut, elle s'auto-corrige (événement 🧬 dans le chat) ;
   - la 2ᵉ question doit être correcte.
4. Vérifie les pages : `/prompt.html`, `/data.html`, `/colab.html`, `/request.html`,
   `/contributeur.html`.
5. Teste le scraping de bout en bout : dans le chat,
   **« Cherche sur le web https://en.wikipedia.org/wiki/Autonomous_agent »** →
   une tâche `fetch` apparaît sur `/colab.html` (statut `pending`) ; exécuter la tâche
   passe par le notebook Colab ou un futur appel API (voir roadmap).

> 💡 **Logs** : onglet *Logs* de chaque service = temps réel. Les erreurs de skills
> s'affichent préfixées `[skills]`. Les warnings de chat (provider en échec, fallback)
> sont renvoyés dans la réponse API sous `warnings`.

---

## 6. (Optionnel) Brancher Supabase — la base de données

Le projet tourne en JSON local sans rien configurer. Pour passer sur Supabase :

1. [supabase.com](https://supabase.com) → *New project* (free tier).
2. **SQL Editor** → New query → coller le contenu de **`supabase/schema.sql`** → *Run*.
   (7 tables : `prompts`, `prompt_versions`, `skills`, `dev_requests`,
   `research_tasks`, `research_results`, `knowledge` + RLS lecture ouverte.)
3. Onglet **Project Settings → API** :
   - `SUPABASE_URL` = `Project URL`
   - `SUPABASE_SERVICE_KEY` = `service_role` (⚠️ jamais dans le repo — env var Render uniquement)
4. Dans `aiis-core` → *Environment* → ajouter/modifier les 2 variables → *Manual Deploy*.
5. La persistance bascule **automatiquement** (le code détecte les 2 variables ;
   sinon JSON local).

> 📌 La migration des données existantes (JSON → tables) et l'écriture des prompts
> versionnés dans Supabase sont à la roadmap : aujourd'hui, en mode Supabase, les tables
> `prompts`/`prompt_versions` restent en lecture — le prompt vit toujours dans les
> fichiers du repo (versionnés par git, ce qui est déjà un historique fiable).

---

## 7. (Optionnel) Brancher le notebook Colab

1. Sur GitHub, ouvre `colab/main.ipynb` → **File → Open notebook… → Colab**
   (ou *Import notebook* depuis un notebook vierge).
2. Cellule de config : `MAIN_SITE_URL = "https://aiis-core.onrender.com"`
   (= `MAIN_SITE_URL` du service `aiis-core`, §4).
3. **Runtime → Run all** → les tâches `pending` de `colab/tasks.json` s'exécutent
   (recherche DuckDuckGo sans clé + fetch de pages simples), les résultats sont poussés
   vers `POST /api/research/results` du site.
4. Sur le site : `/colab.html` → les tâches passent `done`, les résultats apparaissent.
   Dans le chat : **« Quelles sont les dernières recherches ? »** (skill `list_research_results`).

> ⏳ Les sessions Colab sont limitées dans le temps (RAM gratuite ~12 h max) :
> le script sauvegarde de façon incrémentale (`tasks.json`/`results.json` mis à jour
> après chaque tâche) → rien n'est perdu en cas de coupure.
> Les tâches ajoutées par l'IA via le chat vivent dans `colab/tasks.json` **du repo** :
> pousse la branche avant de relancer Colab pour qu'il voie les dernières tâches.

---

## 8. Vie quotidienne (après le déploiement)

| Besoin | Où |
|---|---|
| Modifier une env var | *Settings → Environment* → puis **Manual Deploy** obligatoire |
| Redéployer à la main | *Manual Deploy → Deploy latest commit* |
| **Rollback** | onglet **Events** → trouver le commit voulu → *Redeploy from this commit* |
| Logs temps réel | onglet **Logs** (recherche possible) |
| Renommer le sous-domaine | *Settings → Name* (l'URL `.onrender.com` suit) |
| Domaine custom | *Settings → Custom Domain* (DNS CNAME) |
| Changer de plan / arrêter | *Settings → Plan* / bouton *Stop* (l'instance dort, les disques restent) |
| Push → auto-déploiement | activé (`autoDeploy: true`) : chaque push sur la branche choisie déploie |

**Flux de travail recommandé :**
1. Tu modifies le code (ou l'IA propose via `/request`).
2. Tu pousses sur la branche du Blueprint.
3. Render redéploie automatiquement (2-5 min pour `aiis-core`, plus pour le scraper
   si le Dockerfile a changé).
4. Si souci → *Events → Redeploy from* le dernier bon commit (rollback en 30 s).

---

## 9. Coût & alternative 100 % gratuite

| Solution | Coût | Notes |
|---|---|---|
| **Render × 2** (ce tuto) | ~16-24 $/mois | le plus simple ; le scraper peut tourner au mode « stop » la nuit pour économiser |
| **Oracle Cloud Free Tier** | **0 $** | VM ARM (4 OCPU / 24 Go) *toujours* gratuite → `aiis-core` + Chromium sur la même VM ; `SCRAPER_SERVICE_URL` = ta VM ; tu peux même ajouter le site sur le port 80 avec Caddy/nginx (reverse proxy) |
| **Fly.io** (scraper) + Render (core) | ~0-7 $/mois | Fly a un plan gratuit small ; Chromium y fonctionne |
| **GitHub Pages** (site seul) + Render (API) | ~5-7 $/mois | le site statique est gratuit sur Pages ; mais il faut définir `API_BASE` dans `site/js/config.js` vers l'API (aujourd'hui le site et l'API sont censés être sur la même origine) |

---

## 10. Dépannage (les 90 % des cas)

| Symptôme | Cause probable | Correction |
|---|---|---|
| Site affiche « MODE DÉMO » au lieu de MISTRAL | `MISTRAL_API_KEY` absente/vide/mal collée | *Environment* → vérifier la clé (pas d'espaces) → **Manual Deploy** |
| Réponses très lentes au 1er message | Instance froide de Render (~30-60 s au réveil) | Normal ; 2ᵉ requête rapide |
| `aiis-core` 502 après déploiement | Crashe au boot | *Logs* : souvent `ModuleNotFoundError` → vérifier que le commit a bien `requirements.txt` ; ou mémoire insuffisante → plan plus haut |
| Build du scraper échoue | Étape `playwright install chromium` | Relire *Logs* ; relancer le déploiement (souvent transitoire) ; vérifier que le Dockerfile est bien dans `services/scraper/` |
| Scraper 502 / OOM (code 137) | Chromium dépasse les 2 Go sur une page lourde | Réduire `max_chars`/`wait_ms` côté appel ; plan `2c-4g` (4 Go) pour le scraper ; `ALLOWED_DOMAINS` pour limiter |
| `POST /api/research/scrape` renvoie « SCRAPER_SERVICE_URL non configuré » | Variable vide dans `aiis-core` | §4 |
| Colab n'arrive pas à pousser les résultats | `MAIN_SITE_URL` vide ou http (Colab exige https pour certains domaines) | Mettre l'URL `https://…onrender.com` dans la cellule de config du notebook |
| Render ne voit pas le repo | Repo privé non autorisé | Reconnecter GitHub dans Render en cochant *Private repositories* |
| Push ne déclenche pas le déploiement | Le Blueprint a été créé sur une **autre branche** | *Settings → Branch* → choisir ta branche, ou merger sur la branche du Blueprint |

---

## 11. Checklist finale

- [ ] Blueprint créé (2 services : `aiis-core`, `aiis-scraper`)
- [ ] `MISTRAL_API_KEY` (+ fallbacks optionnels) renseignés
- [ ] Scraper live → `/health` OK
- [ ] `SCRAPER_SERVICE_URL` + `MAIN_SITE_URL` dans `aiis-core` → redéploié
- [ ] Site live → chip **MISTRAL** (pas MODE DÉMO)
- [ ] Test chat « dernier Zelda » ×2
- [ ] `/prompt.html` `/data.html` `/colab.html` `/request.html` `/contributeur.html` OK
- [ ] (opt) Supabase : `schema.sql` exécuté + 2 variables
- [ ] (opt) Colab : notebook lancé, `MAIN_SITE_URL` configurée
