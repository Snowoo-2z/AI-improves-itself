# services/scraper — web service Chromium (scraping)

Service FastAPI + Playwright (Chromium headless) : reçoit une URL, rend la page
(complet avec JS), renvoie le texte. C'est l'exécutant « fetch » du pipeline
de recherche du projet (page [/colab](../../site/colab.html)).

## Déploiement

### Option A — Blueprint Render (one-click, recommandé)

Le `render.yaml` à la racine du repo déclare les 2 services du projet
(`aiis-core` + `aiis-scraper`) : sur Render, **New → Blueprint** → sélectionner
le repo → les 2 services sont créés, l'image Docker du scraper est buildée
automatiquement. Il ne reste qu'à renseigner les env vars proposées à la création.

### Option B — Manuelle (web service Render)

1. **New → Web Service** sur [render.com](https://render.com).
2. **Repo** : ce mono-repo, **Root Directory : `services/scraper`**.
3. **Build & Run** : détection automatique via le `Dockerfile`
   (ou manuellement : Build `pip install -r requirements.txt && playwright install --with-deps chromium`,
   Start `uvicorn main:app --host 0.0.0.0 --port $PORT`).
4. **Plan** : `free` (512 Mo RAM) — c'est **la seule machine gratuite de Render**
   et c'est le réglage du `render.yaml`.
   > Note budget (vérifiée le 2026-09-14 sur [render.com/pricing](https://render.com/pricing)) :
   > le plan web gratuit existe toujours, mais **uniquement en 512 Mo**. Tout le reste est
   > payant : `0.5c-512mb` 7 $/mois, `1c-2g` (1 vCPU / 2 Go) **25 $/mois**, `2c-4g` 85 $/mois.
   > ⚠️ 512 Mo est tendu pour Chromium → risque d'OOM (code 137) sur une page lourde :
   > garder `max_chars`/`wait_ms` modestes. Si l'OOM persiste, deux issues :
   > **Oracle Cloud Free Tier** (VM ARM gratuite, Chromium y tourne à l'aise) ou
   > `1c-2g` (25 $/mois). ~~Fly.io~~ n'est plus une option gratuite : plus aucun tier
   > gratuit pour les comptes créés après le 7 oct. 2024 (~2 $/mois pour 256 Mo, insuffisant).
5. **Env vars** :
   - `ALLOWED_DOMAINS` (optionnel) : whitelist, ex. `wikipedia.org,wikimedia.org,example.com`.

## Lier au projet

Dans le `.env` du projet principal :

```
SCRAPER_SERVICE_URL=https://ton-scraper.onrender.com
```

L'IA peut alors déclencher un scraping via `POST /api/research/scrape`
(skill future) et le notebook Colab peut l'appeler pour les tâches `fetch`.

## API

| Route | Méthode | Body | Retour |
|---|---|---|---|
| `/health` | GET | — | `{ok, service, ts}` |
| `/scrape` | POST | `{url, wait_ms?, max_chars?}` | `{ok, url, title, text, chars_total, fetched_at}` |

## Limites & bonnes pratiques

- `max_chars` plafonné à 60 000 (l'IA n'a pas besoin de plus pour étudier).
- Respecter les `robots.txt` et les CGU du site cible : ce service est fait
  pour de la **recherche ponctuelle**, pas du crawl massif.
- Ajouter une auth simple en production (header `X-Scrape-Key`) quand le service
  sera public.
