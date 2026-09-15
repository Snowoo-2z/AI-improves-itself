# Offres gratuites des fournisseurs IA — état vérifié le 2026-09-15

> Recherche documentaire (docs officielles + retours terrain Reddit/forums) qui a
> servi à corriger la chaîne de providers du projet. Les chiffres bougent :
> ce document indique **où vérifier** autant que les valeurs elles-mêmes.
> Le code qui les applique : `core/ai/limits.py` (catalogue) et
> `core/ai/providers.py` (repli, disjoncteur, throttle).

## 0. Pourquoi ce document existe

Le projet tourne sur des offres gratuites. Trois constats répétés partout
(Reddit r/MistralAI, docs fournisseurs, retours d'agents open-source) :

1. **Le 429 n'est pas une panne** — c'est une fenêtre de quota. Le mitrailler
   aggrave les choses : chez OpenRouter, *les requêtes refusées en 429 comptent
   dans le quota journalier*.
2. **Le plafond qui tombe en premier n'est pas celui qu'on croit** : c'est
   presque toujours les **tokens/jour** (Groq) ou les **tokens/mois** (Mistral),
   pas les requêtes/minute.
3. **Ne JAMAIS coder un seul ID de modèle en dur.** Groq a coupé deux familles
   Llama le 16/08/2026, Mistral a retiré Medium 3/3.1 le 31/08/2026 et toute la
   ligne Magistral le 31/07/2026, GitHub Models a fermé le 30/07/2026.

## 1. Tableau comparatif (valeurs vérifiées le 2026-09-15)

| Fournisseur | Modèles gratuits par défaut du projet | Débit | Plafond qui tombe en premier | Fenêtre de remise à zéro | Carte bancaire |
|---|---|---|---|---|---|
| **Mistral** (La Plateforme, mode gratuit) | `ministral-8b-latest` → `mistral-small-latest` → `mistral-large-2411` → `ministral-3b-latest` | ~**1 req/s globale par clé** | pool standard : **50 000 tokens/min** puis **4 M tokens/mois** | glissante ~1 min ; mensuel au 1er | non (téléphone vérifié) |
| **Google AI Studio** (Gemini) | `gemini-2.5-flash` → `gemini-3-flash-preview` → `gemini-2.5-flash-lite` | 10-15 req/min | 250 000 tokens/min, **1 500 req/jour** | **minuit heure du Pacifique** | non |
| **Groq** (GroqCloud) | `openai/gpt-oss-120b` → `qwen/qwen3.6-27b` → `openai/gpt-oss-20b` | 30 req/min (60 sur qwen3.6-27b) | **200 000 tokens/jour** + 1 000 req/jour | minuit UTC | non |
| **OpenRouter** (`:free`) | `openrouter/free` (auto-routeur) | 20 req/min | **50 req/jour** (1 000 après 10 $ de crédits achetés une fois) | minuit UTC | non |
| **NVIDIA NIM** (optionnel) | `openai/gpt-oss-120b` | ~40 req/min | crédit mensuel offert (~1 000 crédits/mois selon périodes) | 1er du mois | non |

Détails par fournisseur ci-dessous.

## 2. Mistral — ce qui a changé et ce qu'on en fait

**Limites réelles du mode gratuit** (mesures publiées sur r/MistralAI le
20-23/02/2026 via les en-têtes `x-ratelimit-*`, recoupées avec la doc officielle) :

- **limite globale ~1 requête/seconde par clé**, tous modèles confondus ;
- **pool « standard » partagé** entre `mistral-small-*`, `mistral-large-2512`,
  `codestral-2508`, `open-mistral-nemo`, `ministral-{3b,8b,14b}-2512`,
  `devstral-*-2507`, `pixtral-large-2411` : **50 000 tokens/min** et
  **4 000 000 tokens/mois** ;
- **pool isolé** pour `mistral-large-2411` : **600 000 tokens / 5 min** et
  60 req/min — le seul modèle gratuit en fenêtre de 5 minutes ;
- Mistral ne publie plus ses nombres exacts : les tiens sont sur
  <https://admin.mistral.ai/plateforme/limits> ;
- les paliers payants montent avec le **cumul facturé** (Tier 2 > 20 $, Tier 3
  > 100 $…) : **recharger des crédits ne change rien aux limites**.

**Retraits récents** (un ID mort renvoie une erreur, pas un 429 → attendre ne
sert à rien) :

| ID | Statut | Remplacement |
|---|---|---|
| `magistral-small-2506/2507` | retirés le 30/11/2025 | `mistral-small-latest` |
| `magistral-small-2509`, `magistral-medium-2509` (+ les alias `-latest`) | retirés le 31/07/2026 | Small 4 / Medium 3.5 avec `reasoning_effort` |
| `devstral-2512`, `devstral-small-latest` | retirés le 31/07/2026 (et 31/03/2026 pour labs) | `mistral-medium-latest` |
| `mistral-small-2501/2503` | retirés le 30/11/2025 | `mistral-small-latest` |
| `mistral-small-2506` | retiré le 31/07/2026 | `mistral-small-latest` (Small 4) |
| `mistral-medium-2505`, `mistral-medium-2508` | retirés le 31/08/2026 | `mistral-medium-latest` (Medium 3.5) |
| `open-mistral-nemo`, `pixtral-large-2411` | retirés/dépréciés (31/07/2026, 27/02/2026) | `ministral-8b-latest`, `mistral-medium-latest` |

**Choix du projet — pourquoi le 8B en premier ?** Retour d'usage réel :
`mistral-small-latest` (Small 4, 119B MoE) sort en erreur/429 sur le mode
gratuit alors que le Ministral 8B passe. Les deux sont dans le **même pool**
(50 000 tokens/min), mais Small 4 produit des milliers de tokens par réponse là
où le 8B en produit quelques centaines : à quota égal, le petit modèle tient
environ dix fois plus longtemps. D'où l'ordre
`ministral-8b-latest → mistral-small-latest → mistral-large-2411 → ministral-3b-latest`
(le 3ᵉ change de pool, ce qui peut suffire à repartir).

**Raisonnement** : la ligne Magistral est morte ; elle est remplacée par le
paramètre `reasoning_effort` (`high`/`none`) sur `mistral-small-latest` et
`mistral-medium-3-5`. L'envoyer à un autre modèle vaut une **422**. Le projet ne
l'active que sur demande (`MISTRAL_REASONING=1`) car les tokens de réflexion
partent du même quota gratuit.

> ⚠️ Les requêtes du mode gratuit peuvent servir à entraîner les modèles
> Mistral (opt-out possible) : ne rien y envoyer de sensible.

## 3. Google AI Studio (Gemini)

- Le tier gratuit est devenu une **famille Flash** : les modèles Pro sont
  passés derrière la facturation (mai 2026), et Google a **réduit les quotas
  sans préavis en décembre 2025** (des comptes sont passés de 250 à ~20 req/jour
  sur 2.5-flash selon les retours).
- Valeurs généralement observées : `gemini-3-flash-preview` 10 RPM / 1 500 RPD /
  250 000 TPM ; `gemini-3.1-flash-lite` 15 RPM / 1 000 RPD ;
  `gemini-2.5-flash` 10-15 RPM / 250-500 RPD ; `gemini-2.5-pro` ~5 RPM / 50 RPD
  (quasi inutilisable en gratuit).
- **Remise à zéro à minuit heure du Pacifique**, pas UTC — le projet calcule le
  repos en conséquence (`daily_quota_tz="us_pacific"`).
- Endpoint compatible OpenAI : `https://generativelanguage.googleapis.com/v1beta/openai`.
  Des retours (forum Google AI, avril 2026) signalent un **tool calling
  multi-tours instable** sur cette couche ; via OpenRouter le même modèle est
  stable. À surveiller : le projet utilise le tool calling pour ses skills.
- Les prompts du tier gratuit peuvent être utilisés pour améliorer les produits
  Google.

## 4. Groq

| Modèle | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | 1 000 | 8 000 | 200 000 |
| `openai/gpt-oss-20b` | 30 | 1 000 | 8 000 | 200 000 |
| `qwen/qwen3.6-27b` | 60 | 1 000 | 6 000 | 500 000 |
| `groq/compound` | 30 | 250 | 70 000 | — |

- **Coupures du 16/08/2026** : `llama-3.3-70b-versatile` et
  `llama-3.1-8b-instant` (remplacements officiels : `openai/gpt-oss-120b`,
  `qwen/qwen3.6-27b`, `openai/gpt-oss-20b`). Le 17/07/2026 : `qwen/qwen3-32b`
  et `meta-llama/llama-4-scout-17b-16e-instruct`.
- Les plafonds **journaliers de tokens** sont la vraie limite : 200 000 TPD sur
  gpt-oss-120b ≈ une centaine d'appels de chat moyens par jour.
- Les modèles de raisonnement (gpt-oss) consomment des **tokens de réflexion**
  qui comptent dans TPM/TPD et ne sont pas renvoyés en `content` → ne pas mettre
  `max_tokens` trop bas (réponse vide sinon).
- Paramètre de sortie : `max_completion_tokens` (pas `max_tokens`) sur les
  gpt-oss — géré par le code.
- En-têtes utiles au debugging : `x-ratelimit-remaining-requests`,
  `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-tokens: 7.66s` (le projet
  les lit pour caler son repos).
- Vérifier avant de déployer : <https://console.groq.com/docs/deprecations> et
  <https://console.groq.com/docs/rate-limits>.

## 5. OpenRouter (modèles `:free`)

- **20 req/min** sur toute variante `:free` (inchangé par un achat de crédits)
  et **50 req/jour** ; **1 000/jour** dès qu'on a acheté **une fois** ≥ 10 $ de
  crédits (l'augmentation est définitive même si le solde retombe à 0).
- **Les tentatives échouées en 429 comptent dans le quota journalier** : un
  retry en rafale brûle la journée. Le projet throttle à ~3 s et met un
  disjoncteur.
- Le quota est **par compte**, pas par clé : créer plusieurs clés n'ajoute rien.
- La capacité gratuite est un **pool partagé** : saturé aux heures de pointe
  (soirées US, week-ends) → 429/503 même avec du quota restant.
- **`openrouter/free`** (auto-routeur, février 2026) : choisit un modèle
  gratuit compatible avec la demande (tool calling, images, sorties
  structurées). C'est le réglage par défaut du projet : la liste des `:free`
  tourne en permanence et un ID codé en dur finit par mourir (le précédent
  défaut du projet, `meta-llama/llama-3.3-70b-instruct:free`, en est
  l'illustration).
- Particularité piégeuse : OpenRouter renvoie des **erreurs upstream dans un
  corps HTTP 200** (`{"error": {...}}`) — traité comme un échec par le code.
- En-têtes d'attribution `HTTP-Referer` / `X-Title` envoyés par le projet
  (demandés pour les modèles gratuits ; sans secret dedans).
- Un solde **négatif** peut produire des 402 même sur du `:free`.

## 6. NVIDIA NIM (5ᵉ secours, optionnel)

- OpenAI-compatible : `https://integrate.api.nvidia.com/v1`, sans carte,
  crédit mensuel offert (~1 000 crédits/mois selon les périodes), débit de
  l'ordre de 40 req/min.
- Catalogue et plafonds **très volatils** : vérifier les IDs sur
  <https://build.nvidia.com> avant de compter dessus. D'où son statut de
  secours optionnel (`NVIDIA_API_KEY` vide par défaut).

## 7. Pistes écartées (et pourquoi)

| Option | Verdict du projet |
|---|---|
| **Cerebras Cloud** | 5 req/min et crédit de 5 $ **conditionné à une carte bancaire** → pas « gratuit sans carte », contraire à la règle du projet |
| **GitHub Models** | **fermé le 30/07/2026** — rappel que ces offres disparaissent |
| **Cohere (trial)** | 1 000 appels/mois mais **usage non commercial** et peu d'intérêt pour du chat outillé |
| **DeepInfra** | plus de tier gratuit permanent (crédit mensuel récurrent annoncé) |
| **Ollama / llama.cpp en local** | excellente réponse « zéro quota », mais hors périmètre d'un déploiement Render free à 512 Mo ; à garder en tête pour une VM Oracle gratuite |
| **Puter.js (sans clé)** | intéressant pour un front 100 % statique, mais la consommation est imputée au visiteur et le projet veut un moteur côté serveur |

## 8. Règles appliquées dans le code

1. **Throttle en amont** plutôt que retry en aval : intervalle minimal par
   moteur déduit du débit publié (1,05 s Mistral, 2,25 s Groq, 3,25 s OpenRouter,
   6,25 s Gemini, 1,75 s NVIDIA).
2. **Rotation de modèles dans le même provider** avant de changer de provider
   (les quotas sont souvent séparés par modèle). Un 429 ne déclenche **aucun
   retry sur le même modèle** : on passe directement au suivant.
3. **Repli en cascade** : le moteur suivant répond, la démo locale n'arrive
   qu'en dernier.
4. **Disjoncteur par moteur**, repos calculé d'après ce que l'API annonce
   (`Retry-After`, `x-ratelimit-reset-*`), sinon d'après la nature de la limite :
   fenêtre ~1 min, jour → minuit (Pacifique pour Google), mois → 1er,
   configuration (clé morte, modèle retiré) → 1 h avec message actionnable.
5. **Classification des erreurs** : 401/403/404/402/« unsupported parameter » =
   configuration (rien d'attendre) ; 429 = quota ; 5xx/réseau = passager ;
   200 + corps d'erreur = échec à replier.
6. **Visibilité** : `/api/status` expose l'état de chaque moteur (repos restant,
   nature de l'échec, modèle, en-têtes de quota) ; le chat renvoie
   `warnings`, `attempts` et `provider_retry_in_human` ; `POST
   /api/providers/retest` force un re-test.
7. **Veille** : `core/ai/limits.py` contient un dictionnaire `RETIRED_MODELS`
   — quand un fournisseur retire un modèle, l'ajouter là transforme une erreur
   opaque en message qui dit quoi mettre dans `.env`.

## 9. Sources

**Docs officielles**

- Mistral — 429 et paliers : <https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them>
- Mistral — catalogue et retraits : <https://docs.mistral.ai/models>
- Mistral — raisonnement réglable : <https://docs.mistral.ai/studio/conversations/reasoning>
- Mistral — console des limites : <https://admin.mistral.ai/plateforme/limits>
- Google — limites de débit : <https://ai.google.dev/gemini-api/docs/rate-limits>
- Google — tarifs (tier gratuit par modèle) : <https://ai.google.dev/gemini-api/docs/pricing>
- Google — famille Gemini 3 (IDs et tier gratuit) : <https://ai.google.dev/gemini-api/docs/gemini-3>
- Groq — dépréciations : <https://console.groq.com/docs/deprecations>
- Groq — limites de débit : <https://console.groq.com/docs/rate-limits>
- OpenRouter — limites : <https://openrouter.ai/docs/api-reference/limits>
- OpenRouter — auto-routeur gratuit : <https://openrouter.ai/docs/cookbook/get-started/free-models-router-playground>

**Retours terrain (Reddit / forums / benchmarks)**

- r/MistralAI — « Mistral API quota and rate limits pools analysis for Free Tier » (pools partagés, en-têtes réels, 1 req/s global) : <https://www.reddit.com/r/MistralAI/comments/1rc8rwf/mistral_api_quota_and_rate_limits_pools_analysis/>
- r/MistralAI — « Hermès Agent » (429 en rafale sur `mistral-small-latest`, limites par modèle dans la console) : <https://www.reddit.com/r/MistralAI/comments/1u4x4wk/herm%C3%A8s_agent/>
- r/MistralAI — « Le Chat Pro API quota » (chaque modèle a son propre compteur) : <https://www.reddit.com/r/MistralAI/comments/1s37gj7/le_chat_pro_api_quota/>
- r/MistralAI — « Rooting for Mistral AI » (1 Md tokens/mois annoncés, vérification par téléphone) : <https://www.reddit.com/r/MistralAI/comments/1se8hlj/rooting_for_mistral_ai/>
- r/kilocode — 429 sur les modèles gratuits OpenRouter, espacer les requêtes et crédits de 10 $ : <https://www.reddit.com/r/kilocode/comments/1mwb80c/newbie_getting_429_rate_limit_exceeded_error_for/>
- Forum Google AI — tool calling multi-tours instable sur la couche compatible OpenAI : <https://discuss.ai.google.dev/t/same-gemini-3-flash-via-openrouter-works-direct-gemini-openai-compat-api-gives-unstable-hallucination-like-behavior-on-multi-turn-tools/142695>
- groq-production-benchmark (calendrier des coupures Llama) : <https://markaicode.com/benchmarks/groq-production-benchmark-latency/>
- Groq free tier 2026 (RPM/RPD/TPM/TPD par modèle) : <https://www.grizzlypeaksoftware.com/articles/p/groq-api-free-tier-limits-in-2026-what-you-actually-get-uwysd6mb>
- OpenRouter 429 : les requêtes refusées comptent dans le quota journalier : <https://markaicode.com/errors/openrouter-rate-limits-fix/>
- Comparatif des API gratuites (le plafond tokens/jour est celui qui mord) : <https://ianlpaterson.com/blog/free-llm-api-2026/>
- Panorama des offres gratuites et de leur volatilité : <https://continuumcode.ai/guides/free-llm-api/>
- Modèles `:free` d'OpenRouter testés un par un + liste de repli : <https://klymentiev.com/blog/openrouter-free-tier>
- NVIDIA NIM (crédit mensuel, base URL) : <https://www.ayautomate.com/free-models/nvidia-nim>
- Cerebras (carte requise pour le crédit, 5 req/min) : <https://itsfree.ai/provider/cerebras/>
- Mistral alias et retraits (table détaillée) : <https://www.promptfoo.dev/docs/providers/mistral/> et <https://mungomash.com/ai/mistral/versions/>

> Re-vérifier ces chiffres avant chaque déploiement : la durée de vie constatée
> d'un ID de modèle gratuit en 2026 est de l'ordre de **3 à 6 mois**.
