"""Catalogue des offres gratuites des fournisseurs IA — vérifié le 2026-09-15.

Ce module centralise TOUT ce que le projet sait des tiers gratuits : limites
réelles, IDs de modèles vivants, IDs **retirés** (qui renvoient une erreur de
configuration, pas un 429), et la stratégie de repli associée. `providers.py`
l'utilise pour construire la chaîne ; `docs/FREE-TIERS.md` en est la version
lisible (avec les sources).

Pourquoi un catalogue plutôt que des valeurs en dur dans `.env` :
les offres gratuites changent vite. Rien qu'en 2026 :

- **Groq** a coupé `llama-3.3-70b-versatile` et `llama-3.1-8b-instant` le
  16/08/2026 (remplacements conseillés : `openai/gpt-oss-120b`,
  `qwen/qwen3.6-27b`, `openai/gpt-oss-20b`), après `qwen/qwen3-32b` et
  `meta-llama/llama-4-scout-17b-16e-instruct` le 17/07/2026.
- **Mistral** a retiré `mistral-medium-2505` / `mistral-medium-2508` le
  31/08/2026, `devstral-2512` et toute la ligne Magistral le 31/07/2026
  (`magistral-small-latest` pointe désormais sur Mistral Small 4), et
  `mistral-small-2506` le 31/07/2026.
- **Google** a réduit le tier gratuit (coupe de décembre 2025, Pro passé
  derrière la facturation en mai 2026) : le gratuit est maintenant une
  famille Flash (`gemini-3-flash-preview`, `gemini-3.1-flash-lite`,
  `gemini-2.5-flash`, `gemini-2.5-flash-lite`).
- **OpenRouter** fait tourner sa liste de modèles `:free` en permanence ;
  l'auto-routeur `openrouter/free` (février 2026) filtre tout seul les modèles
  gratuits compatibles avec ce que demande l'appel (outils, images, JSON).

Conséquence pour le code : un ID de modèle mort ne doit PAS être traité comme
un 429 (repos 1 min puis on recommence) mais comme une **erreur de
configuration** (repos long + message qui dit quel modèle mettre à jour).
C'est exactement ce que fait `classify_failure()` dans `providers.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Limites réelles du tier gratuit, par fournisseur (état 2026-09-15).
# `rpm` sert à calculer l'intervalle minimal entre deux appels (throttle) :
# mieux vaut prévenir le 429 que le subir — sur OpenRouter, les tentatives
# échouées en 429 CONSOMMENT quand même le quota journalier.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FreeTierLimits:
    """Ce que le fournisseur annonce (ou ce que la communauté a mesuré)."""

    rpm: float | None = None  # requêtes/minute
    rpd: int | None = None  # requêtes/jour
    tpm: int | None = None  # tokens/minute
    tpd: int | None = None  # tokens/jour
    monthly_tokens: int | None = None  # tokens/mois
    rps: float | None = None  # requêtes/seconde (Mistral : limite globale par clé)
    note: str = ""

    def min_interval(self) -> float:
        """Intervalle minimal entre deux appels pour rester sous la limite RPM/RPS."""
        if self.rps:
            return round(1.0 / self.rps + 0.05, 3)
        if self.rpm:
            return round(60.0 / self.rpm + 0.25, 3)
        return 0.0

    def summary(self) -> str:
        bits: list[str] = []
        if self.rps:
            bits.append(f"{self.rps:g} req/s")
        if self.rpm:
            bits.append(f"{self.rpm:g} req/min")
        if self.rpd:
            bits.append(f"{self.rpd:,} req/jour".replace(",", " "))
        if self.tpm:
            bits.append(f"{self.tpm:,} tokens/min".replace(",", " "))
        if self.tpd:
            bits.append(f"{self.tpd:,} tokens/jour".replace(",", " "))
        if self.monthly_tokens:
            bits.append(f"{self.monthly_tokens:,} tokens/mois".replace(",", " "))
        out = " · ".join(bits) or "limites non publiées"
        return f"{out} — {self.note}" if self.note else out


@dataclass(frozen=True)
class ProviderSpec:
    """Un fournisseur gratuit : endpoint, modèles vivants, limites, repli."""

    name: str
    label: str
    base_url: str
    key_env: str
    model_env: str
    #: Modèles essayés dans l'ordre. Le premier qui répond est utilisé ; en cas
    #: de 429 on passe au suivant (chez Mistral les pools de quota sont séparés
    #: par modèle → changer de modèle peut suffire à repartir).
    models: tuple[str, ...]
    limits: FreeTierLimits
    #: Fenêtre du quota journalier : "utc" (Groq, OpenRouter) ou "us_pacific"
    #: (Google réinitialise à minuit heure du Pacifique).
    daily_quota_tz: str = "utc"
    #: Certains modèles n'acceptent que `max_completion_tokens` (gpt-oss…).
    completion_tokens_models: tuple[str, ...] = ()
    #: En-têtes supplémentaires (OpenRouter demande une attribution pour les
    #: modèles gratuits, sinon ils peuvent être exclus du routage).
    extra_headers: dict[str, str] = field(default_factory=dict)
    #: Paramètres hors standard OpenAI à injecter dans le corps de la requête
    #: (ex. `reasoning_effort` chez Mistral). Clé = motif d'ID de modèle
    #: (préfixe), valeur = champ à ajouter. Envoyer un paramètre non supporté
    #: vaut une 422 : on ne l'envoie QUE sur les modèles qui l'acceptent.
    #: Par défaut ces champs ne sont PAS envoyés (voir `enable_extra_body`) :
    #: le raisonnement consomme des tokens invisibles, donc du quota gratuit.
    extra_body: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Active `extra_body` (variables d'env dédiées, ex. `MISTRAL_REASONING=1`).
    enable_extra_body_env: str = ""
    #: Le ping ne consomme pas de quota s'il est minuscule, mais il en consomme
    #: QUAND MÊME un appel : sur les tiers gratuits à 50 req/jour, on ne ping
    #: que si le provider n'a pas répondu récemment.
    ping_is_cheap: bool = True
    signup_url: str = ""
    limits_url: str = ""
    deprecations_url: str = ""


# --- Mistral « La Plateforme », mode gratuit (Experiment) -------------------
# Mesures communautaires (r/MistralAI, 20-23/02/2026) + doc officielle :
#   • limite GLOBALE par clé : ~1 requête/seconde, quel que soit le modèle ;
#   • pool « standard » PARTAGÉ (small/large-2512/codestral/nemo/ministral/
#     pixtral) : 50 000 tokens/min + 4 000 000 tokens/mois ;
#   • pool isolé `mistral-large-2411` : 600 000 tokens / 5 min, 60 req/min
#     (le seul modèle gratuit avec une fenêtre de 5 minutes) ;
#   • le 429 arrive donc sur trois axes : RPS, TPM, quota mensuel.
MISTRAL = ProviderSpec(
    name="mistral",
    label="Mistral (La Plateforme, mode gratuit)",
    base_url="https://api.mistral.ai/v1",
    key_env="MISTRAL_API_KEY",
    model_env="MISTRAL_MODEL",
    models=(
        # Ordre VOLONTAIRE : le plus petit d'abord. Retour d'usage réel du
        # projet : `mistral-small-latest` (Small 4, 119B MoE) sort en erreur/429
        # sur le mode gratuit alors que le Ministral 8B passe. Explication :
        # ils partagent le même pool (50 000 tokens/min + 4 M tokens/mois), mais
        # un 8B répond en quelques centaines de tokens là où Small 4 en produit
        # des milliers → le petit modèle tient ~10× plus longtemps dans le pool.
        "ministral-8b-latest",  # 8B, 256K de contexte : le plus fiable en gratuit
        "mistral-small-latest",  # Small 4 (alias vivant), meilleur en raisonnement
        "mistral-large-2411",  # pool de quota ISOLÉ, fenêtre 5 min : bon 3e choix
        "ministral-3b-latest",  # dernier recours, minuscule mais quasi jamais en 429
    ),
    limits=FreeTierLimits(
        rps=1.0,
        tpm=50_000,
        monthly_tokens=4_000_000,
        note=(
            "limite globale ~1 req/s par clé + pool « standard » partagé "
            "(small/large-2512/codestral/ministral) : 50 000 tokens/min et 4 M tokens/mois ; "
            "mistral-large-2411 a son propre pool (600 000 tokens / 5 min). "
            "Un petit modèle (ministral-8b) tient beaucoup plus longtemps dans ce pool "
            "qu'un Small 4 → c'est le premier essayé. "
            "Limites exactes : admin.mistral.ai/plateforme/limits"
        ),
    ),
    # La ligne Magistral (raisononnement natif) est retirée depuis le
    # 31/07/2026 : le raisonnement s'active maintenant avec `reasoning_effort`
    # sur Small 4 et Medium 3.5 uniquement. Les autres modèles renvoient 422 si
    # on le leur envoie → d'où le filtre par préfixe d'ID.
    extra_body={
        "mistral-small": {"reasoning_effort": "high"},
        "mistral-medium": {"reasoning_effort": "high"},
    },
    # Opt-in : `MISTRAL_REASONING=1` dans .env. En « high », la réponse arrive
    # avec des blocs de réflexion qui comptent dans les 50 000 tokens/min et
    # les 4 M tokens/mois du pool gratuit → à réserver aux questions dures.
    enable_extra_body_env="MISTRAL_REASONING",
    signup_url="https://console.mistral.ai/cle",
    limits_url="https://admin.mistral.ai/plateforme/limits",
    deprecations_url="https://docs.mistral.ai/models",
)

# Modèles Mistral RETIRÉS de l'API (appel = erreur, pas de 429). Utilisé pour
# expliquer clairement un échec au lieu d'attendre un repos qui ne changera rien.
MISTRAL_RETIRED: dict[str, str] = {
    "mistral-medium-2505": "retiré le 31/08/2026 → mistral-medium-latest (Medium 3.5)",
    "mistral-medium-2508": "retiré le 31/08/2026 → mistral-medium-latest (Medium 3.5)",
    "mistral-medium-2508-latest": "retiré → mistral-medium-latest",
    "magistral-small-2506": "retiré le 30/11/2025 → mistral-small-latest (Small 4)",
    "magistral-small-2507": "retiré le 30/11/2025 → mistral-small-latest (Small 4)",
    "magistral-small-2509": "retiré le 31/07/2026 → mistral-small-latest (Small 4)",
    # Piège : l'ALIAS survit parfois au modèle. `magistral-small-latest` a pointé
    # un temps sur Mistral Small 4, puis la ligne Magistral a été retirée
    # (31/07/2026) — le réglage « raisonnement gratuit » des vieux .env casse.
    # Le raisonnement s'active maintenant via reasoning_effort sur Small 4 /
    # Medium 3.5 (docs.mistral.ai → capabilities/reasoning).
    "magistral-small-latest": "ligne Magistral retirée le 31/07/2026 → mistral-small-latest "
    "(raisonnement via reasoning_effort)",
    "magistral-medium-latest": "ligne Magistral retirée le 31/07/2026 → mistral-medium-latest",
    "mistral-tiny-latest": "alias de Mistral NeMo, retiré le 31/07/2026 → ministral-8b-latest",
    "open-mistral-nemo": "Mistral NeMo retiré le 31/07/2026 → ministral-8b-latest",
    "mistral-small-3.1-24b-instruct": "retiré → mistral-small-latest",
    "pixtral-12b-2409": "retiré → ministral-14b-latest",
    "magistral-medium-2506": "retiré le 30/11/2025 → mistral-medium-latest",
    "magistral-medium-2509": "retiré le 31/07/2026 → mistral-medium-latest",
    "devstral-2512": "retiré le 31/07/2026 → mistral-medium-latest",
    "devstral-small-latest": "labs-devstral-small-2512 retiré le 31/03/2026",
    "mistral-small-2501": "retiré le 30/11/2025 → mistral-small-latest",
    "mistral-small-2503": "retiré le 30/11/2025 → mistral-small-latest",
    "mistral-small-2506": "retiré le 31/07/2026 → mistral-small-latest (Small 4)",
    "open-mixtral-8x7b": "retiré le 30/03/2025 → mistral-small-latest",
    "open-mixtral-8x22b": "retiré → mistral-small-latest",
    "open-mistral-7b": "retiré → ministral-3b-latest",
    "pixtral-large-2411": "déprécié le 27/02/2026 → mistral-medium-latest",
}

# --- Google AI Studio (Gemini API, tier gratuit) ----------------------------
# Depuis mai 2026 les modèles Pro ne sont plus sur le tier gratuit : le gratuit
# est une famille Flash. Le quota journalier se réinitialise à MINUIT HEURE DU
# PACIFIQUE (pas UTC) — détail qui change le temps de repos à annoncer.
GEMINI = ProviderSpec(
    name="gemini",
    label="Google AI Studio (Gemini, tier gratuit)",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    key_env="GEMINI_API_KEY",
    model_env="GEMINI_MODEL",
    models=(
        "gemini-2.5-flash",  # stable, outil de calling fiable, 1M de contexte
        "gemini-3-flash-preview",  # recommandé par Google sur le tier gratuit
        "gemini-2.5-flash-lite",  # plus de req/min, pour les tâches légères
        "gemini-3.1-flash-lite",
    ),
    limits=FreeTierLimits(
        rpm=10,
        rpd=1_500,
        tpm=250_000,
        note=(
            "10-15 req/min selon le modèle, quota journalier remis à minuit heure du "
            "Pacifique ; coupes de quota déjà observées (déc. 2025) : vérifier dans AI Studio. "
            "Les prompts du tier gratuit peuvent servir à améliorer les produits Google."
        ),
    ),
    daily_quota_tz="us_pacific",
    signup_url="https://aistudio.google.com/apikey",
    limits_url="https://ai.google.dev/gemini-api/docs/rate-limits",
    deprecations_url="https://ai.google.dev/gemini-api/docs/models",
)

# --- Groq (GroqCloud, tier gratuit) -----------------------------------------
# Le catalogue bouge vite : deux familles Llama coupées le 16/08/2026.
# Les plafonds JOURNALIERS de tokens sont la vraie limite (pas les RPM).
GROQ = ProviderSpec(
    name="groq",
    label="Groq (GroqCloud, tier gratuit)",
    base_url="https://api.groq.com/openai/v1",
    key_env="GROQ_API_KEY",
    model_env="GROQ_MODEL",
    models=(
        "openai/gpt-oss-120b",  # remplaçant officiel de llama-3.3-70b-versatile
        "qwen/qwen3.6-27b",  # autre remplacement conseillé, 60 RPM
        "openai/gpt-oss-20b",  # remplaçant de llama-3.1-8b-instant, très rapide
    ),
    limits=FreeTierLimits(
        rpm=30,
        rpd=1_000,
        tpm=8_000,
        tpd=200_000,
        note=(
            "30 RPM / 1 000 RPD / 8K TPM / 200K TPD sur gpt-oss-120b (qwen3.6-27b : 60 RPM). "
            "Le plafond de tokens PAR JOUR est la limite qui tombe en premier. "
            "Les modèles de raisonnement consomment des tokens de réflexion invisibles."
        ),
    ),
    completion_tokens_models=("openai/gpt-oss-120b", "openai/gpt-oss-20b", "openai/gpt-oss-safeguard-20b"),
    signup_url="https://console.groq.com/keys",
    limits_url="https://console.groq.com/docs/rate-limits",
    deprecations_url="https://console.groq.com/docs/deprecations",
)

GROQ_RETIRED: dict[str, str] = {
    "llama-3.3-70b-versatile": "coupé le 16/08/2026 → openai/gpt-oss-120b ou qwen/qwen3.6-27b",
    "llama-3.1-8b-instant": "coupé le 16/08/2026 → openai/gpt-oss-20b",
    "qwen/qwen3-32b": "coupé le 17/07/2026 → openai/gpt-oss-120b",
    "meta-llama/llama-4-scout-17b-16e-instruct": "coupé le 17/07/2026 → openai/gpt-oss-120b",
    "llama3-70b-8192": "coupé le 30/08/2025 → openai/gpt-oss-120b",
    "llama3-8b-8192": "coupé le 30/08/2025 → openai/gpt-oss-20b",
    "deepseek-r1-distill-llama-70b": "coupé le 02/10/2025 → openai/gpt-oss-120b",
    "mixtral-8x7b-32768": "retiré → openai/gpt-oss-120b",
    "gemma2-9b-it": "retiré → openai/gpt-oss-20b",
    "qwen-qwq-32b": "retiré → qwen/qwen3.6-27b",
    "llama-3.3-70b-specdec": "coupé le 14/04/2025 → openai/gpt-oss-120b",
    "deepseek-r1-distill-qwen-32b": "coupé le 14/04/2025 → openai/gpt-oss-120b",
}

# --- OpenRouter (modèles :free) ---------------------------------------------
# Deux plafonds distincts : 20 req/min sur les variantes `:free` (inchangé par
# un achat de crédits) et 50 req/JOUR tant qu'on n'a jamais acheté 10 $ de
# crédits (1 000/jour ensuite, définitivement). Piège documenté : les requêtes
# refusées en 429 comptent DANS le quota journalier → ne jamais faire de
# retry en rafale ; on throttle à 3 s et on met un disjoncteur.
OPENROUTER = ProviderSpec(
    name="openrouter",
    label="OpenRouter (modèles :free)",
    base_url="https://openrouter.ai/api/v1",
    key_env="OPENROUTER_API_KEY",
    model_env="OPENROUTER_MODEL",
    models=(
        "openrouter/free",  # auto-routeur officiel : choisit un :free compatible outils
        "nvidia/nemotron-3-super-120b-a12b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ),
    limits=FreeTierLimits(
        rpm=20,
        rpd=50,
        note=(
            "20 req/min sur les variantes :free + 50 req/jour (1 000/jour après un achat "
            "unique de 10 $ de crédits). Les tentatives refusées en 429 comptent dans le "
            "quota journalier ; la capacité gratuite est un pool partagé, saturé aux heures "
            "de pointe. La liste des :free tourne : ne jamais coder UN seul ID en dur."
        ),
    ),
    extra_headers={
        # Attribution demandée par OpenRouter ; sans elle les modèles gratuits
        # peuvent être exclus du routage. Aucun secret ici (valeur publique).
        "HTTP-Referer": "https://github.com/Snowoo-2z/AI-improves-itself",
        "X-Title": "AI-improves-itself",
    },
    signup_url="https://openrouter.ai/keys",
    limits_url="https://openrouter.ai/docs/api-reference/limits",
    deprecations_url="https://openrouter.ai/models?max_price=0",
)

# --- NVIDIA NIM (Build) — moteur gratuit OPTIONNEL --------------------------
# OpenAI-compatible, sans carte bancaire, crédit mensuel offert. Utile comme
# 5e secours quand les quatre premiers sont au repos. Le catalogue NIM bouge
# (les modèles et leurs limites changent sans préavis) : vérifier sur
# build.nvidia.com, et ajuster `NVIDIA_MODEL` (liste séparée par des virgules).
NVIDIA = ProviderSpec(
    name="nvidia",
    label="NVIDIA NIM (Build, crédit mensuel offert)",
    base_url="https://integrate.api.nvidia.com/v1",
    key_env="NVIDIA_API_KEY",
    model_env="NVIDIA_MODEL",
    models=(
        "openai/gpt-oss-120b",
        "meta/llama-3.3-70b-instruct",
        "mistralai/mistral-large-2411",
    ),
    limits=FreeTierLimits(
        rpm=40,
        note=(
            "crédit mensuel offert (souvent ~1 000 crédits/mois), débit limité en requêtes/min ; "
            "les modèles et plafonds changent sans préavis : vérifier sur build.nvidia.com"
        ),
    ),
    signup_url="https://build.nvidia.com/",
    limits_url="https://build.nvidia.com/",
    deprecations_url="https://docs.api.nvidia.com/nim/reference/llm-apis",
)

# Chaîne dans l'ordre de priorité (le premier avec une clé est le moteur
# principal ; les suivants sont des secours). `demo-local` ferme la marche.
SPECS: tuple[ProviderSpec, ...] = (MISTRAL, GEMINI, GROQ, OPENROUTER, NVIDIA)

#: IDs retirés, tous fournisseurs confondus → message d'erreur explicite.
RETIRED_MODELS: dict[str, str] = {
    **{k: f"mistral — {v}" for k, v in MISTRAL_RETIRED.items()},
    **{k: f"groq — {v}" for k, v in GROQ_RETIRED.items()},
    "gemini-1.5-pro": "google — tier gratuit supprimé, utiliser gemini-2.5-flash",
    "gemini-1.5-flash": "google — retiré, utiliser gemini-2.5-flash",
    "gemini-2.0-flash": "google — en fin de vie, utiliser gemini-2.5-flash",
    "gemini-3.1-pro-preview": "google — pas de tier gratuit (API payante)",
}


def spec_by_name(name: str) -> ProviderSpec | None:
    for spec in SPECS:
        if spec.name == name:
            return spec
    return None


def limits_table() -> list[dict]:
    """Tableau lisible (utilisé par /api/status et par docs/FREE-TIERS.md)."""
    return [
        {
            "provider": spec.name,
            "label": spec.label,
            "models": list(spec.models),
            "limits": spec.limits.summary(),
            "min_interval_s": spec.limits.min_interval(),
            "signup_url": spec.signup_url,
            "limits_url": spec.limits_url,
        }
        for spec in SPECS
    ]
