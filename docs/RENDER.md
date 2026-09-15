# 📘 Tutoriel Render — déploiement complet de AI-improves-itself

Guide pas-à-pas pour déployer le projet sur [Render](https://render.com) à l'aide du
**Blueprint** (`render.yaml` à la racine). À la fin, tu auras :

```
https://aiis-core.onrender.com/      ← site + chat IA (le produit)
https://aiis-scraper.onrender.com/   ← service de scraping Chromium
```

> ⏱ Durée estimée : **30-45 minutes** (le build Docker du scraper prend 5-10 min).
> 💰 Coût : **0 $** — les 2 services du `render.yaml` sont sur le plan `free`
> (0,1 CPU / 512 Mo RAM), la **seule** machine gratuite de Render. Tout le reste
> est payant : `0.5c-512mb` = 7 $/mois, `1c-2g` (2 Go) = **25 $/mois par service**,
> `2c-4g` = 85 $/mois. Il n'existe même pas de machine web à 1 Go : l'échelle passe de
> 512 Mo à 2 Go (prix relevés sur [render.com/pricing](https://render.com/pricing) et
> [docs.render.com/compute-plans](https://render.com/docs/compute-plans) le 2026-09-14 ;
> détail + alternatives au §9).

---

## 0. Prérequis

| Ce qu'il faut | Où | Coût |
|---|---|---|
| Compte GitHub + ce repo poussé | ✅ déjà fait (contenu sur la branche `main`) | 0 $ |
| Compte Render | [render.com](https://render.com) → *Sign up with GitHub* → workspace **Hobby** | 0 $ (plan `free` : 512 Mo) |
| Clé API **Mistral** (moteur principal) | [console.mistral.ai/cle](https://console.mistral.ai/cle) → plan gratuit « La Plateforme » | 0 $ |
| (optionnel) Clé Gemini / Groq / OpenRouter | fallbacks automatiques | 0 $ |
| (optionnel) Compte Supabase (base de données, phase 2) | [supabase.com](https://supabase.com) | 0 $ (free tier) |

> **Important — repo privé ?** Le repo `AI-improves-itself` est actuellement privé.
> Quand tu connectes Render à GitHub, la pop-up d'autorisation doit autoriser Render à
> **lire les repos privés** (case « Private repositories »). Sans ça, le repo ne sera
> pas listé.

> **Quelle branche ?** Le Blueprint se déploie depuis **une seule branche** : `main`
> (tout le contenu est mergé dessus). Chaque push sur `main` redéploie les 2 services
> automatiquement (`autoDeploy: true`).

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
- **OpenRouter** : [openrouter.ai/keys](https://openrouter.ai/keys) (réglage par défaut : `openrouter/free`, l'auto-routeur officiel qui choisit un modèle gratuit compatible avec le tool calling — la liste des `:free` tourne en permanence, ne pas coder un ID en dur).
- **NVIDIA NIM** (5ᵉ secours optionnel) : [build.nvidia.com](https://build.nvidia.com/) → `NVIDIA_API_KEY`.

> ⚠️ Les IDs de modèles gratuits meurent vite (Groq a coupé `llama-3.3-70b-versatile` le
> 16/08/2026, Mistral a retiré Medium 3/3.1 le 31/08/2026 et la ligne Magistral le
> 31/07/2026). Avant chaque déploiement, comparer tes `*_MODEL` avec
> [docs/FREE-TIERS.md](FREE-TIERS.md) — le cœur affiche désormais un message explicite
> (« modèle retiré → remplacement conseillé ») au lieu d'un 429 trompeur.

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

> ⚠️ **Plan `free` = instance qui s'endort** : 15 min sans requête entrante et Render
> stoppe l'instance ; la requête suivante met **~1 min** à la réveiller (Render affiche
> une page de chargement pendant ce temps). Le 1er appel après un déploiement est donc
> lent : teste deux fois. Chaque spin-down efface aussi le filesystem local.

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
| Changer de plan | *Settings → Plan* : `free` (512 Mo, 0 $) → `0.5c-512mb` (7 $) → `1c-2g` (2 Go, 25 $) — changement appliqué au redéploiement |
| Arrêter / laisser dormir | bouton *Stop* ; en plan `free` l'instance s'endort seule après 15 min d'inactivité (pas de disque persistant sur ce plan) |
| Push → auto-déploiement | activé (`autoDeploy: true`) : chaque push sur la branche choisie déploie |

**Flux de travail recommandé :**
1. Tu modifies le code (ou l'IA propose via `/request`).
2. Tu pousses sur la branche du Blueprint.
3. Render redéploie automatiquement (2-5 min pour `aiis-core`, plus pour le scraper
   si le Dockerfile a changé).
4. Si souci → *Events → Redeploy from* le dernier bon commit (rollback en 30 s).

---

## 9. Coût & alternative 100 % gratuite

Règle de base Render (vérifiée sur [render.com/pricing](https://render.com/pricing)
et [docs.render.com/free](https://render.com/docs/free) le **2026-09-14**) :
**seule la machine de 512 Mo est gratuite** (`plan: free` = 0,1 CPU / 512 Mo).
Dès qu'on monte en CPU/RAM, c'est payant — et il n'existe **aucun** palier web à 1 Go :
l'échelle des web services est `free` (512 Mo) → `0.5c-512mb` (512 Mo, 7 $) → `1c-2g`
(2 Go, 25 $) → `2c-4g` (4 Go, 85 $). Le plan `0.5c-1g` (1 Go) n'existe qu'en **Postgres**
(19 $/mois).

| Solution | Coût | Notes |
|---|---|---|
| **Render × 2 en `free`** (ce tuto, réglage actuel) | **0 $** | 512 Mo par service. ⚠️ **750 h d'instance gratuites par workspace et par mois** : un mois = ~730 h, donc **les 2 services ne peuvent pas rester éveillés 24/7 ensemble** (~1 460 h). En pratique ils s'endorment après 15 min sans requête (les heures endormies ne comptent pas) → OK pour un usage ponctuel, sinon Render suspend les services gratuits jusqu'au mois suivant |
| **Render × 2 en `1c-2g`** | **50 $/mois** (2 × 25 $) | 2 Go + 1 vCPU chacun, always-on, disque persistant et scaling possibles. Étape intermédiaire : `0.5c-512mb` = 7 $/mois (512 Mo, <1 vCPU) — utile uniquement pour supprimer le spin-down, pas pour Chromium |
| **Oracle Cloud Free Tier** | **0 $** | VM ARM (4 OCPU / 24 Go) *toujours* gratuite → `aiis-core` + Chromium sur la même VM, sans quota horaire ; `SCRAPER_SERVICE_URL` = ta VM ; tu peux même ajouter le site sur le port 80 avec Caddy/nginx (reverse proxy) |
| **Fly.io** (scraper) | **≈ 2-3 $/mois — plus de tier gratuit** | ⚠️ Corrigé : Fly.io n'a **plus** d'offre gratuite pour les comptes créés après le 7 oct. 2024 (l'ancien quota « 3 machines shared-cpu-1x 256 Mo » ne vaut que pour les comptes antérieurs). Nouveau compte = court essai puis facturation à la seconde ; shared-cpu-1x 256 Mo ≈ 2 $/mois, et 256 Mo ne suffit de toute façon pas à Chromium |
| **GitHub Pages** (site seul) + Render (API en `free`) | 0 $ (ou 7 $ sans spin-down) | le site statique est gratuit sur Pages ; mais il faut définir `API_BASE` dans `site/js/config.js` vers l'API (aujourd'hui le site et l'API sont censés être sur la même origine) |

---

## 10. Dépannage (les 90 % des cas)

| Symptôme | Cause probable | Correction |
|---|---|---|
| Site affiche « MODE DÉMO » au lieu de MISTRAL | `MISTRAL_API_KEY` absente/vide/mal collée | *Environment* → vérifier la clé (pas d'espaces) → **Manual Deploy** |
| Réponses très lentes au 1er message | Plan `free` : l'instance s'est endormie (15 min sans requête) → ~1 min de réveil | Normal ; la 2ᵉ requête est rapide. Pour supprimer le réveil : plan `0.5c-512mb` (7 $) ou `1c-2g` (25 $) |
| Site/scraper muet en fin de mois, puis retour au 1er du mois | Quota **750 h d'instance gratuites** du workspace épuisé (2 services toujours éveillés ≈ 1 460 h) | Laisser les services s'endormir (pas de trafic permanent), ne garder qu'un seul service en `free`, ou passer un service en payant |
| `aiis-core` 502 après déploiement | Crashe au boot | *Logs* : souvent `ModuleNotFoundError` → vérifier que le commit a bien `requirements.txt` ; ou OOM en 512 Mo (plan `free`) → `1c-2g` (25 $/mois) |
| Build du scraper échoue | Étape `playwright install chromium` | Relire *Logs* ; relancer le déploiement (souvent transitoire) ; vérifier que le Dockerfile est bien dans `services/scraper/` |
| Scraper 502 / OOM (code 137) | Chromium dépasse les **512 Mo** du plan `free` sur une page lourde (risque assumé du scraper à 0 $) | Réduire `max_chars`/`wait_ms` côté appel ; `ALLOWED_DOMAINS` pour limiter ; si l'OOM persiste → `1c-2g` (2 Go, 25 $/mois) pour le scraper, ou Oracle Cloud Free Tier (0 $) |
| `POST /api/research/scrape` renvoie « SCRAPER_SERVICE_URL non configuré » | Variable vide dans `aiis-core` | §4 |
| Colab n'arrive pas à pousser les résultats | `MAIN_SITE_URL` vide ou http (Colab exige https pour certains domaines) | Mettre l'URL `https://…onrender.com` dans la cellule de config du notebook |
| Render ne voit pas le repo | Repo privé non autorisé | Reconnecter GitHub dans Render en cochant *Private repositories* |
| Push ne déclenche pas le déploiement | Le Blueprint a été créé sur une **autre branche** | *Settings → Branch* → choisir ta branche, ou merger sur la branche du Blueprint |

---

## 11. Checklist finale

- [ ] Blueprint créé (2 services : `aiis-core`, `aiis-scraper`)
- [ ] Les 2 services sont bien sur le plan **`free`** (512 Mo, 0 $) — *Settings → Instance Type*
- [ ] `MISTRAL_API_KEY` (+ fallbacks optionnels) renseignés
- [ ] Scraper live → `/health` OK
- [ ] `SCRAPER_SERVICE_URL` + `MAIN_SITE_URL` dans `aiis-core` → redéploié
- [ ] Site live → chip **MISTRAL** (pas MODE DÉMO)
- [ ] Test chat « dernier Zelda » ×2
- [ ] `/prompt.html` `/data.html` `/colab.html` `/request.html` `/contributeur.html` OK
- [ ] (opt) Supabase : `schema.sql` exécuté + 2 variables
- [ ] (opt) Colab : notebook lancé, `MAIN_SITE_URL` configurée
