"""Multi-fournisseurs IA avec repli en cascade.

Chaîne : Mistral (priorité) → Gemini → Groq → OpenRouter → démo locale.
Tous les providers cloud parlent le protocole OpenAI-compatible
(`chat/completions` + tool calling), ce qui garantit la portabilité.

Ce que ce module a appris des tiers gratuits (voir `limits.py` et
`docs/FREE-TIERS.md` pour les chiffres et les sources) :

1. **Un 429 n'est pas une panne.** C'est une fenêtre de quota (≈1 min) ou un
   plafond journalier/mensuel. Le bon réflexe n'est PAS de réessayer en rafale :
   sur OpenRouter les tentatives refusées comptent dans le quota du jour, et
   chez Mistral la limite est globale à la clé (≈1 req/s). On throttle donc en
   amont, puis on met le provider au repos le temps exact annoncé par l'API
   (`Retry-After`, `x-ratelimit-reset-*`) — et on passe AU SUIVANT plutôt que
   de tomber directement en mode démo.
2. **Un modèle retiré n'est pas un 429.** Groq a coupé `llama-3.3-70b-versatile`
   le 16/08/2026, Mistral a retiré `mistral-medium-2508` le 31/08/2026 et toute
   la ligne Magistral le 31/07/2026. Attendre 1 minute ne changera rien : il
   faut un message qui dit quel modèle mettre à jour (repos long).
3. **Les quotas gratuits sont séparés par modèle.** Chez Mistral,
   `mistral-large-2411` a son propre pool (600 000 tokens / 5 min) alors que
   small/codestral/ministral partagent le pool « standard » (50 000 tokens/min,
   4 M tokens/mois). Changer de modèle dans le MÊME provider suffit souvent à
   repartir → d'où la rotation de modèles avant de changer de provider.
4. **Un 200 peut cacher une erreur.** OpenRouter renvoie des erreurs
   upstream dans un corps 200 (`{"error": {...}}`), et un modèle de raisonnement
   peut vider son budget tokens sans produire de contenu. Les deux sont traités
   comme des échecs à replier.
"""
from __future__ import annotations

import calendar
import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Iterator

import httpx

from .config import env
from .limits import RETIRED_MODELS, SPECS, FreeTierLimits, ProviderSpec, spec_by_name


# ---------------------------------------------------------------------------
# Politiques de retry / de repos (valeurs calées sur les fenêtres réelles)
# ---------------------------------------------------------------------------
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2  # essais supplémentaires après le premier appel
_RETRY_BACKOFF_S = (1.2, 3.0)  # pause avant la 1re puis la 2e relance (sans Retry-After)
_RETRY_MAX_WAIT_S = 12.0  # borne haute d'une pause en ligne (au-delà : on replie)

#: Repos appliqué quand l'API ne dit rien de précis.
COOLDOWN_RATE_LIMIT_S = 65.0  # fenêtre glissante ~1 min (+ marge)
COOLDOWN_5XX_S = 30.0
COOLDOWN_NETWORK_S = 30.0
COOLDOWN_CONFIG_S = 3_600.0  # clé invalide / modèle retiré : 1 h (pas de rafale)
COOLDOWN_UNKNOWN_S = 60.0

#: Au-delà de ce temps d'attente annoncé, on ne bloque pas la requête : on
#: bascule sur le provider suivant (ou la démo) et on réessaiera plus tard.
MAX_INLINE_WAIT_S = 8.0

_PACIFIC_OFFSET_H = -7  # PDT (heure d'été) ; -8 en PST. Approximation assumée :
# elle ne sert qu'à afficher « le quota journalier repart dans ~X h ».


class ProviderError(RuntimeError):
    """Erreur d'appel provider, avec un message lisible pour la bannière ⚠️ du site."""


class ProviderUnavailable(ProviderError):
    """Tous les providers cloud sont au repos : le site bascule en démo locale."""


class StreamInterruptedError(ProviderError):
    """Flux SSE interrompu APRÈS le statut 200 (coupure réseau/fournisseur).

    Le réflexe de l'appelant : abandonner le streaming et relancer la même
    requête en non-streamé via `chat_with_failover`, pour ne jamais rester
    sur une réponse à moitié écrite.
    """


@dataclass
class Failure:
    """Un échec classé : c'est cette classification qui décide du temps de repos."""

    kind: str  # rate_limit | daily_quota | monthly_quota | config | server | network | unknown
    message: str
    status: int | None = None
    retry_after_s: float | None = None  # annoncé par l'API (Retry-After / x-ratelimit-reset-*)
    model: str = ""
    hint: str = ""  # ce que l'utilisateur peut faire (URL, variable .env, modèle à changer)

    @property
    def is_config(self) -> bool:
        return self.kind == "config"


@dataclass
class ProviderResult:
    content: str
    tool_calls: list[dict] | None = None
    provider: str = ""
    model: str = ""
    raw: dict = field(default_factory=dict)

    def with_text(self, text: str) -> "ProviderResult":
        """Copie avec un `content` texte (hors tool_calls)."""
        return ProviderResult(
            content=text,
            tool_calls=self.tool_calls,
            provider=self.provider,
            model=self.model,
            raw=self.raw,
        )


def _display_text(content: str, commentary: str) -> str:
    """Compose le texte affiché quand le tour porte des images.

    Un modèle vision ne renvoie parfois AUCUN `content` texte (il enchaîne sur
    des tokens de « réflexion » ou un tool_call). On reconstitue alors un texte
    neutre accompagné de la consigne utilisateur, au lieu d'une bulle vide ou
    d'un faux « (réponse vide) ». Le contenu texte réel est conservé s'il existe.
    """
    commentary = commentary.strip()
    if content.strip():
        return content
    if commentary:
        return f"Traité — réponds à : {commentary[:300]}"
    return "Traité."



# ---------------------------------------------------------------------------
# Classification des erreurs
# ---------------------------------------------------------------------------
_DAILY_HINTS = (
    "per day",
    "daily",
    "requests per day",
    "free-models-per-day",
    "rate limit exceeded: free-models",
    "quota exceeded for quota group",
    "quota_group",
    "resource exhausted",
    "rpd",
    "journali",
    "par jour",
)
_MONTHLY_HINTS = ("per month", "monthly", "tokens/month", "mensuel")
_CONFIG_HINTS = (
    "model not found",
    "does not exist",
    "unknown model",
    "no such model",
    "not available",
    "deprecated",
    "retired",
    "has been shut down",
    "shut down",
    "unsupported parameter",
    "invalid api key",
    "invalid_api_key",
    "incorrect api key",
    "unauthorized",
    "authentication",
    "billing",
    "insufficient",
    "credit balance",
    "permission",
    "not enabled",
    "access denied",
)


def _body_snippet(response: httpx.Response, limit: int = 220) -> str:
    try:
        text = response.text or ""
    except Exception:  # noqa: BLE001
        return ""
    text = " ".join(text.split())
    return text[:limit]


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Pause annoncée par l'API : `Retry-After` puis en-têtes x-ratelimit-reset-*.

    Groq renvoie `x-ratelimit-reset-tokens: 7.66s`, d'autres `ratelimit-reset`
    (secondes ou horodatage). On prend la valeur la plus petite non nulle :
    c'est le temps à attendre pour la fenêtre qui bloque le plus tôt.
    """
    candidates: list[float] = []
    raw = response.headers.get("retry-after")
    if raw:
        raw = raw.strip()
        try:
            candidates.append(float(raw))
        except ValueError:
            try:  # Retry-After peut être une date HTTP
                dt = datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %Z")
                candidates.append(max(0.0, (dt.replace(tzinfo=timezone.utc) - _utcnow()).total_seconds()))
            except ValueError:
                pass
    for header in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests", "ratelimit-reset"):
        value = response.headers.get(header)
        if not value:
            continue
        value = value.strip().rstrip("s")
        try:
            number = float(value)
        except ValueError:
            continue
        # Un horodatage (> 1e9) plutôt qu'une durée ?
        candidates.append(number - time.time() if number > 1e9 else number)
    positive = [c for c in candidates if c > 0]
    return min(positive) if positive else None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def daily_reset_seconds(tz: str = "utc") -> float:
    """Secondes avant la remise à zéro du quota journalier du fournisseur.

    Google réinitialise à minuit heure du Pacifique ; Groq et OpenRouter à
    minuit UTC. Utile pour annoncer un repos réaliste au lieu de « ~1 min ».
    """
    now = _utcnow()
    if tz == "us_pacific":
        local = now + timedelta(hours=_PACIFIC_OFFSET_H)
        midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        target = midnight - timedelta(hours=_PACIFIC_OFFSET_H)
    else:
        target = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1.0, (target - now).total_seconds())


def monthly_reset_seconds() -> float:
    """Secondes avant le 1er du mois prochain (quota mensuel Mistral)."""
    now = _utcnow()
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    target = datetime(year, month, 1, tzinfo=timezone.utc)
    return max(1.0, (target - now).total_seconds())


def classify_failure(
    exc: Exception,
    *,
    provider_name: str,
    model: str = "",
    limits: FreeTierLimits | None = None,
    daily_tz: str = "utc",
    spec: ProviderSpec | None = None,
) -> Failure:
    """Transformer une exception en échec classé (le temps de repos en découle)."""
    spec = spec or spec_by_name(provider_name)
    limits_url = spec.limits_url if spec else ""
    label = spec.label if spec else provider_name
    if spec is not None and (limits is None or limits == FreeTierLimits()):
        # Provider construit sans son catalogue (script, test) : on retrouve les
        # vraies limites pour que le message d'erreur reste informatif.
        limits = spec.limits
    status: int | None = None
    body = ""
    retry_after: float | None = None

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = _body_snippet(exc.response)
        retry_after = _retry_after_seconds(exc.response)
        text = f"{body} {exc.response.reason_phrase}".lower()
    else:
        text = str(exc).lower()
        body = text

    retired = RETIRED_MODELS.get(model)
    hint_model = f" (modèle `{model}`)" if model else ""

    # 1) Erreurs de CONFIGURATION : rien d'attendre, il faut changer .env.
    if status in (401, 403):
        return Failure(
            "config",
            f"{provider_name}: clé API refusée ({status}){hint_model} — {body[:160]}",
            status=status,
            hint="Vérifier la clé dans .env (pas d'espace, bonne variable).",
        )
    if status == 404 or retired or any(h in text for h in ("model not found", "does not exist", "unknown model", "no such model")):
        detail = retired or "modèle inconnu ou retiré de l'API"
        return Failure(
            "config",
            f"{provider_name}: {detail}{hint_model} — {body[:160]}",
            status=status,
            hint="Mettre à jour le modèle dans .env (voir docs/FREE-TIERS.md) — un repos ne changera rien.",
        )
    if status == 402 or any(h in text for h in ("insufficient", "credit balance", "billing")):
        return Failure(
            "config",
            f"{provider_name}: solde/facturation ({status or 'n/a'}){hint_model} — {body[:160]}",
            status=status,
            hint="Compte sans crédit : utiliser un modèle `:free` ou un autre fournisseur.",
        )
    if status == 400 and "unsupported parameter" in text:
        return Failure(
            "config",
            f"{provider_name}: paramètre non supporté{hint_model} — {body[:160]}",
            status=400,
            hint="Le modèle exige d'autres paramètres (ex. max_completion_tokens) : changer de modèle.",
        )

    # 2) Quota 429 : fenêtre glissante, jour ou mois ?
    if status == 429:
        if any(h in text for h in _MONTHLY_HINTS):
            wait = retry_after or monthly_reset_seconds()
            return Failure(
                "monthly_quota",
                f"{provider_name}: quota MENSUEL du tier gratuit épuisé{hint_model} — {body[:160]}",
                status=429,
                retry_after_s=wait,
                hint=f"Réinitialisation au 1er du mois. {limits_url}".strip(),
            )
        if any(h in text for h in _DAILY_HINTS):
            wait = retry_after or daily_reset_seconds(daily_tz)
            return Failure(
                "daily_quota",
                f"{provider_name}: quota JOURNALIER du tier gratuit atteint{hint_model} — {body[:160]}",
                status=429,
                retry_after_s=wait,
                hint=(
                    "Réinitialisation à minuit (heure du Pacifique pour Google, UTC sinon). "
                    f"{limits_url}"
                ).strip(),
            )
        return Failure(
            "rate_limit",
            f"{provider_name}: 429 Too Many Requests — limite du tier gratuit atteinte{hint_model}. "
            f"{label} : {limits.summary() if limits else 'limites non publiées'}. {body[:160]}".strip(),
            status=429,
            retry_after_s=retry_after,
            hint=f"Repos automatique puis nouvel essai ; limites exactes : {limits_url}".strip(),
        )

    # 3) Le reste : serveur, réseau, réponse inexploitable.
    # 2b) OpenRouter renvoie parfois l'échec upstream DANS un corps 200 :
    # aucun statut exploitable, mais le texte dit « rate limit » / « no endpoints ».
    if status in (None, 200) and any(
        h in text for h in ("no endpoints found", "rate limit", "temporarily rate-limited", "overloaded", "capacity")
    ):
        return Failure(
            "rate_limit",
            f"{provider_name}: capacité gratuite indisponible (erreur upstream){hint_model} — {body[:160]}",
            status=status or 200,
            retry_after_s=retry_after,
            hint=(
                "Pool gratuit partagé saturé (heures de pointe) : le moteur est mis au repos "
                "et un autre prend le relais. " + limits_url
            ).strip(),
        )

    if status is not None and status in _RETRYABLE_STATUS:
        return Failure(
            "server",
            f"{provider_name}: erreur {status}{hint_model} — {body[:160]}",
            status=status,
            retry_after_s=retry_after,
            hint="Erreur passagère du fournisseur : repos court puis nouvel essai.",
        )
    if status is not None:
        return Failure(
            "config" if status in (400, 405, 422) else "unknown",
            f"{provider_name}: HTTP {status}{hint_model} — {body[:160]}",
            status=status,
            hint="Réponse inattendue : vérifier le modèle et l'endpoint dans .env.",
        )
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return Failure(
            "network",
            f"{provider_name}: réseau/timeout{hint_model} — {type(exc).__name__}: {str(exc)[:120]}",
            hint="Sortie réseau bloquée ou fournisseur injoignable : repos court puis nouvel essai.",
        )
    return Failure(
        "unknown",
        f"{provider_name}: {type(exc).__name__}{hint_model} — {str(exc)[:180]}",
        hint="Erreur inclassée : voir les journaux du serveur.",
    )


def cooldown_for(failure: Failure, daily_tz: str = "utc") -> float:
    """Temps de repos (secondes) à imposer au provider après cet échec."""
    if failure.kind == "rate_limit":
        if failure.retry_after_s and failure.retry_after_s <= COOLDOWN_RATE_LIMIT_S * 2:
            return max(2.0, failure.retry_after_s + 1.0)
        return COOLDOWN_RATE_LIMIT_S
    if failure.kind == "daily_quota":
        return failure.retry_after_s or daily_reset_seconds(daily_tz)
    if failure.kind == "monthly_quota":
        return failure.retry_after_s or monthly_reset_seconds()
    if failure.kind == "config":
        return COOLDOWN_CONFIG_S
    if failure.kind == "server":
        return failure.retry_after_s or COOLDOWN_5XX_S
    if failure.kind == "network":
        return COOLDOWN_NETWORK_S
    return COOLDOWN_UNKNOWN_S


# ---------------------------------------------------------------------------
# Provider OpenAI-compatible multi-modèles
# ---------------------------------------------------------------------------
def _flag_enabled(key: str) -> bool:
    """Variable d'env « drapeau » : `1`, `true`, `yes`, `on`, `oui` (insensible à la casse)."""
    if not key:
        return False
    return (env(key) or "").strip().lower() in {"1", "true", "yes", "y", "on", "oui"}


class OpenAICompatProvider:
    """Client minimaliste pour toute API compatible OpenAI.

    Un provider peut porter PLUSIEURS modèles (`models`) : en cas de 429 sur le
    premier, on essaie le suivant avant de déclarer le provider indisponible.
    C'est décisif chez Mistral, où les pools de quota sont séparés par modèle.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        models: Iterable[str],
        min_interval: float = 0.0,
        extra_headers: dict[str, str] | None = None,
        extra_body: dict[str, dict[str, Any]] | None = None,
        enable_extra_body_env: str = "",
        completion_tokens_models: Iterable[str] = (),
        limits: FreeTierLimits | None = None,
        daily_tz: str = "utc",
        label: str = "",
    ):
        self.name = name
        self.label = label or name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.models: list[str] = [m for m in models if m] or [""]
        self.min_interval = max(0.0, float(min_interval))
        self.extra_headers = dict(extra_headers or {})
        self.extra_body_env = enable_extra_body_env
        # Opt-in : le raisonnement (« reasoning_effort ») consomme des tokens
        # invisibles donc du quota gratuit → désactivé sauf variable d'env.
        self.extra_body = dict(extra_body or {}) if _flag_enabled(enable_extra_body_env) else {}
        self._completion_key_models = set(completion_tokens_models)
        self.limits = limits or FreeTierLimits()
        self.daily_tz = daily_tz

        self.model = self.models[0]  # modèle courant (celui qui a répondu en dernier)
        self._model_index = 0
        self._throttle_lock = threading.Lock()
        self._next_allowed_at = 0.0
        self.last_used_at = 0.0
        self.last_quota: dict[str, Any] = {}

    # -- throttle ----------------------------------------------------------
    def _throttle(self) -> None:
        """Sérialiser les appels : sur un tier gratuit, la rafale crée le 429."""
        if self.min_interval <= 0.0:
            return
        with self._throttle_lock:
            wait = self._next_allowed_at - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._next_allowed_at = time.monotonic() + self.min_interval

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.extra_headers)
        return headers

    def _token_key(self, model: str) -> str:
        return "max_completion_tokens" if model in self._completion_key_models else "max_tokens"

    def _rotate_model(self, failed_model: str) -> str | None:
        """Passer au modèle suivant du provider (quota séparé). None si épuisés."""
        if len(self.models) < 2:
            return None
        for _ in range(len(self.models)):
            self._model_index = (self._model_index + 1) % len(self.models)
            candidate = self.models[self._model_index]
            if candidate != failed_model:
                self.model = candidate
                return candidate
        return None

    def _record_quota(self, response: httpx.Response) -> None:
        """Mémoriser les en-têtes de quota (affichés par /api/status)."""
        quota: dict[str, Any] = {}
        for header in (
            "x-ratelimit-limit-requests",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-limit-tokens",
            "x-ratelimit-remaining-tokens",
            "x-ratelimit-reset-tokens",
        ):
            value = response.headers.get(header)
            if value:
                quota[header.replace("x-ratelimit-", "")] = value
        if quota:
            self.last_quota = quota

    @staticmethod
    def _body_error(data: Any) -> str | None:
        """OpenRouter (et d'autres) renvoient une erreur dans un corps HTTP 200."""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                message = str(err.get("message") or err.get("code") or "erreur upstream")
                metadata = err.get("metadata")
                if isinstance(metadata, dict) and metadata.get("provider_name"):
                    message = f"{metadata['provider_name']}: {message}"
                return message
            if isinstance(err, str) and err:
                return err
        return None

    def _post(self, body: dict[str, Any], timeout: float, model: str, retry_on_429: bool = True) -> dict:
        """Un appel, avec retry borné. Lève une exception classable en Failure.

        `retry_on_429=False` (utilisé par `chat` quand le provider a plusieurs
        modèles) : on ne mitraille PAS un modèle en 429 — chaque requête refusée
        compte dans le quota sur plusieurs tiers gratuits (OpenRouter : les 429
        sont décomptés des 50 req/jour ; Mistral : limite globale ~1 req/s).
        On sort tout de suite et on tourne vers le modèle suivant.
        """
        url = f"{self.base_url}/chat/completions"
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            self._throttle()
            try:
                resp = httpx.post(url, headers=self._headers(), json=body, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                self._record_quota(resp)
                upstream_error = self._body_error(data)
                if upstream_error:
                    # 200 + corps d'erreur : reproduire une HTTPStatusError pour
                    # que la classification (429 upstream, modèle saturé…) fonctionne.
                    raise httpx.HTTPStatusError(
                        upstream_error, request=resp.request, response=resp
                    )
                return data
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                if status not in _RETRYABLE_STATUS or attempt >= _MAX_RETRIES:
                    break
                if status == 429 and not retry_on_429:
                    break  # → rotation immédiate vers un autre modèle du provider
                pause = _retry_after_seconds(exc.response) or _RETRY_BACKOFF_S[attempt]
                if pause > MAX_INLINE_WAIT_S:
                    break  # trop long : on replie vers un autre moteur au lieu de bloquer
                time.sleep(pause)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= _MAX_RETRIES:
                    break
                time.sleep(_RETRY_BACKOFF_S[attempt])
            except ValueError as exc:  # JSON invalide
                last_exc = exc
                break
        assert last_exc is not None
        raise last_exc

    def _extra_body_for(self, model: str) -> dict[str, Any]:
        """Paramètres hors standard acceptés par CE modèle (filtrés par préfixe).

        Exemple réel : `reasoning_effort` n'est accepté que par `mistral-small-*`
        et `mistral-medium-*` ; l'envoyer à `codestral-latest` vaut une 422.
        """
        for prefix, fields in self.extra_body.items():
            if model.startswith(prefix):
                return dict(fields)
        return {}

    # -- vision (images) ---------------------------------------------------
    def _build_messages(self, messages: list[dict]) -> list[dict]:
        """Normalise les messages avant l'appel : texte OU contenu multimédia.

        Le front peut envoyer des blocs vision* dans `content` :

        - `{role: "user", content: [{type:"text", text}, {type:"image_url",
           image_url: {url}}]}` → transmis tel quel (les listes de blocs
           conformes à « OpenAI vision » sont des `text` + 1..N images).
        - `{role: "user", content: [{type:"image_url", image_url:{url}}]}` →
          on ajoute un bloc `text` vide, pour que la structure reste valide
          même sur les modèles qui exigent un bloc texte.

        Tout le reste (texte simple, messages non « user ») passe inchangé.
        """
        out: list[dict] = []
        for m in messages:
            content = m.get("content")
            if isinstance(content, list):
                blocks = [
                    b for b in content
                    if isinstance(b, dict) and b.get("type") in ("text", "image_url")
                ]
                has_image = any(b.get("type") == "image_url" for b in blocks)
                has_text = any(b.get("type") == "text" for b in blocks)
                if has_image:
                    if not has_text:
                        # Les modèles vision exigent un bloc texte : on le met en
                        # TÊTE, en CONSERVANT les images derrière.
                        blocks = [{"type": "text", "text": "[image]"}, *blocks]
                    out.append({**{k: v for k, v in m.items() if k != "content"}, "content": blocks})
                    continue
                # liste sans image → revenir au texte si possible (défensive).
                texts = [str(b.get("text", "")) for b in content if b.get("type") == "text"]
                m = {**{k: v for k, v in m.items() if k != "content"}, "content": "\n".join(texts)}
            out.append(m)
        return out

    def _payload(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model: str,
        max_tokens: int | None,
        *,
        stream: bool = False,
    ) -> dict:
        body: dict[str, Any] = {"model": model, "messages": self._build_messages(messages), "temperature": 0.7}
        if tools:
            body["tools"] = tools
        if max_tokens:
            body[self._token_key(model)] = max_tokens
        if stream:
            body["stream"] = True
        body.update(self._extra_body_for(model))
        return body

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ProviderResult:
        """Appel complet, avec rotation de modèles du provider avant d'abandonner."""
        tried: list[str] = []
        last_exc: Exception | None = None
        model = self.model
        while True:
            tried.append(model)
            try:
                data = self._post(
                    self._payload(messages, tools, model, None),
                    timeout=120,
                    model=model,
                    # Plusieurs modèles configurés → inutile d'insister sur un 429.
                    retry_on_429=len(self.models) < 2,
                )
                self.model = model
                self._model_index = self.models.index(model) if model in self.models else self._model_index
                self.last_used_at = time.time()
                return self._parse(data, model)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                failure = classify_failure(
                    exc, provider_name=self.name, model=model, limits=self.limits, daily_tz=self.daily_tz
                )
                # Un 429 « fenêtre glissante » peut être contourné par un AUTRE
                # modèle du même provider (pools de quota séparés). Pas une erreur
                # de config ni un quota journalier/mensuel : là, tout le provider
                # est concerné.
                if failure.kind != "rate_limit":
                    break
                nxt = self._rotate_model(model)
                if not nxt or nxt in tried:
                    break
                model = nxt
        assert last_exc is not None
        raise last_exc

    def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Iterator[ProviderResult]:
        """Streaming SSE OpenAI-compatible (Mistral/Gemini/Groq/OpenRouter/NVIDIA).

        Yields un `ProviderResult` par fragment : `content` = le delta d'un jeton
        (peut être vide), `tool_calls` = le delta de tool_calls si le modèle
        commence un appel d'outil. Les fragments « usage */role/finish_reason »
        sont ignorés.

        En cas de 429 « fenêtre glissante », le modèle suivant du provider est
        essayé (pools de quota séparés) puis l'exception est relancée. Si le flux
        se coupe APRÈS le statut 200 (coupure réseau/fournisseur), on lève
        `StreamInterruptedError` : l'appelant sait qu'une partie des jetons est
        déjà partie et décide quoi faire (reprendre en non-streamé, ou garder la
        réponse partielle).
        """
        last_exc: Exception | None = None
        tried: list[str] = []
        model = self.model
        while True:
            if model in tried:
                break
            tried.append(model)
            try:
                yield from self._post_stream(
                    self._payload(messages, tools, model, None, stream=True),
                    model=model,
                )
                return
            except StreamInterruptedError:
                raise
            except Exception as exc:  # noqa: BLE001 — on replie comme en non-streamé
                last_exc = exc
                failure = classify_failure(
                    exc, provider_name=self.name, model=model, limits=self.limits, daily_tz=self.daily_tz
                )
                if failure.kind != "rate_limit":
                    break
                nxt = self._rotate_model(model)
                if not nxt:
                    break
                model = nxt
        assert last_exc is not None
        raise last_exc

    def _post_stream(
        self,
        body: dict[str, Any],
        *,
        model: str,
    ) -> Iterator[ProviderResult]:
        """Un appel streamé unique : produit les fragments SSE d'un modèle."""
        url = f"{self.base_url}/chat/completions"
        self._throttle()
        started = False
        try:
            with httpx.stream(
                "POST",
                url,
                headers=self._headers(),
                json=body,
                timeout=httpx.Timeout(connect=30.0, read=240.0, write=60.0, pool=10.0),
            ) as resp:
                resp.raise_for_status()
                self._record_quota(resp)
                started = True
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.strip()
                    # `data: [DONE]` marque la fin propre du flux.
                    if line.startswith("data:"):
                        payload = line[len("data:"):].strip()
                        if payload == "[DONE]":
                            return
                        try:
                            data = json.loads(payload)
                        except ValueError:
                            continue
                        chunk = self._parse_chunk(data, model)
                        if chunk is not None:
                            yield chunk
        except httpx.HTTPStatusError:
            # Un flux peut s'ouvrir (200) puis être coupé en cours de route : le
            # client doit pouvoir réessayer en non-streamé.
            raise StreamInterruptedError("flux interrompu par le fournisseur")
        except (httpx.TimeoutException, httpx.TransportError):
            if started:
                raise StreamInterruptedError("flux interrompu (timeout/réseau)")
            raise

    def _parse_chunk(self, data: Any, model: str) -> ProviderResult | None:
        """Fragment SSE → ProviderResult (content = delta de token, tool_calls = delta)."""
        if not isinstance(data, dict):
            return None
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError, TypeError):
            return None
        delta = choice.get("delta") or choice.get("message") or {}
        if not isinstance(delta, dict):
            return None
        content = delta.get("content")
        if not isinstance(content, str):
            content = ""
        tool_calls = None
        raw_tool_calls = delta.get("tool_calls")
        if isinstance(raw_tool_calls, list) and raw_tool_calls:
            tool_calls = [tc for tc in raw_tool_calls if isinstance(tc, dict)]
        mdl = data.get("model") or model
        if not content and not tool_calls:
            return None
        return ProviderResult(
            content=content,
            tool_calls=tool_calls or None,
            provider=self.name,
            model=mdl,
            raw=data,
        )

    def ping(self) -> None:
        """1 token, timeout courte : vérifier que la clé + l'endpoint répondent."""
        self._post(
            self._payload(
                [{"role": "user", "content": "ping"}],
                None,
                self.model,
                max_tokens=1,
            )
            | {"temperature": 0},
            timeout=20,
            model=self.model,
        )

    def _parse(self, data: dict, model: str) -> ProviderResult:
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"réponse inattendue de {self.name} : {str(data)[:200]}") from exc
        return ProviderResult(
            content=message.get("content") or "",
            tool_calls=message.get("tool_calls") or None,
            provider=self.name,
            model=data.get("model") or model,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Provider de démonstration — 100 % local, aucune clé API.
#
# Reproduit fidèlement le scénario du README : la base de connaissances est
# rangée du plus ancien au plus récent. SANS la règle "date" dans le prompt
# système, l'IA renvoie la PREMIÈRE ligne de la base (le Zelda de 1986) alors
# qu'on lui demandait le DERNIER. Le module de réflexion (core/ai/chat.py)
# détecte l'erreur et déclenche modify_prompt_system : la version du prompt
# passe à v2, et la question suivante est correctement réponse.
# ---------------------------------------------------------------------------
_DEMO_EXPLAINED = (
    "Je tourne actuellement en **mode démo local** (aucune clé API configurée) : "
    "je n'ai donc pas de vraie compréhension du langage, juste un petit "
    "comportement déterministe pour te montrer la mécanique du projet. "
    "Essaie : **« Quel est le dernier jeu Zelda ? »** — ma 1ère réponse montrera "
    "mon défaut, puis je modifierai mon propre prompt système pour me corriger. "
    "Pose la question deux fois pour voir la différence. "
    "Pour m'activer réellement : renseigne `MISTRAL_API_KEY` (ou Gemini/Groq/OpenRouter) dans `.env`."
)

# Variante quand des clés EXISTENT mais que les providers cloud sont au repos
# (429 quota/limite de débit du tier gratuit, modèle retiré, réseau…) : ne pas
# prétendre qu'aucune clé n'est configurée, et dire QUAND ça revient.
_DEMO_EXPLAINED_CLOUD_DOWN = (
    "⚠️ Mes moteurs cloud sont momentanément au repos (limites du tier gratuit "
    "atteintes — 429 —, modèle retiré ou erreur réseau) : je réponds en **mode "
    "démo local** en attendant. Chaque moteur est re-testé automatiquement dès "
    "la fin de son repos, tu peux aussi renvoyer ton message. "
    "Essaie : **« Quel est le dernier jeu Zelda ? »** pour voir la mécanique "
    "d'auto-amélioration pendant ce temps."
)

_DATE_RULE_MARKER = "[REGLE-AJOUTEE-PAR-IA]"


def _tool_call(name: str, arguments: dict) -> dict:
    return {
        "id": f"call-demo-{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


def _wrap_demo_thinking(system: str, content: str) -> str:
    if "MODE PENSÉE / THINKING (ACTIVÉ)" in system and content and not content.startswith("<think>"):
        think_text = (
            "<think>\n"
            "1. Analyse de la demande de l'utilisateur et du contexte.\n"
            "2. Évaluation des connaissances locales et des règles de prompt actives.\n"
            "3. Structuration et validation de la réponse.\n"
            "</think>\n"
        )
        return think_text + content
    return content


class LocalDemoProvider:
    name = "demo-local"
    label = "Mode démo local (aucune clé, déterministe)"

    def __init__(self) -> None:
        self.model = "demo-local"
        self.limits = FreeTierLimits(note="100 % local, aucune limite")
        self.daily_tz = "utc"
        self.last_used_at = 0.0
        self.last_quota: dict[str, Any] = {}

    def ping(self) -> None:
        """100 % local : toujours disponible, aucun test réseau à faire."""
        return None

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ProviderResult:
        def _txt(c) -> str:
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
            return str(c or "")

        system = next((_txt(m["content"]) for m in messages if m["role"] == "system"), "")
        user_texts = [_txt(m["content"]) for m in messages if m["role"] == "user"]
        last_user = user_texts[-1] if user_texts else ""
        t = last_user.lower()
        tool_msgs = [m for m in messages if m["role"] == "tool"]

        # --- Retour d'appel d'outil : composer la réponse finale ---
        if tool_msgs:
            last = tool_msgs[-1]
            try:
                data = json.loads(last.get("content", "{}"))
            except (ValueError, TypeError):
                data = {}
            skill = last.get("name", "")
            if skill == "search_knowledge":
                entries = data.get("entries", [])
                if entries:
                    e = entries[0]
                    note = (
                        " _(tri par date décroissante appliqué grâce à la règle que je viens "
                        "d'ajouter à mon prompt)_."
                        if data.get("used_date_sort")
                        else " _(piqué dans la première entrée de la base, sans tri par date — "
                        "je viens de détecter ce défaut et je vais corriger mon prompt)_."
                    )
                    return ProviderResult(
                        content=_wrap_demo_thinking(
                            system,
                            f"D'après ma base de connaissances : **{e['title']}** "
                            f"({e.get('date', '?')}) — {e.get('summary', '')}{note}",
                        ),
                        provider=self.name,
                        model=self.model,
                    )
                if "openai" in t:
                    content = (
                        "Je n'ai aucune entrée vérifiée sur OpenAI dans ma base de connaissances. "
                        "Je préfère ne pas inventer le modèle le plus récent : une recherche web "
                        "est nécessaire pour répondre à cette question."
                    )
                else:
                    content = "Aucun résultat dans ma base pour cette requête."
                return ProviderResult(
                    content=_wrap_demo_thinking(system, content),
                    provider=self.name,
                    model=self.model,
                )
            if skill == "add_research_task":
                return ProviderResult(
                    content=_wrap_demo_thinking(
                        system,
                        f"Tâche de recherche ajoutée (id `{data.get('id')}`, statut "
                        f"{data.get('status', 'pending')}). Le notebook Colab va l'exécuter "
                        "— tu peux la suivre sur la page **/colab**.",
                    ),
                    provider=self.name,
                    model=self.model,
                )
            if skill == "request_to_dev":
                return ProviderResult(
                    content=_wrap_demo_thinking(
                        system,
                        f"Requête envoyée au développeur (id `{data.get('id')}). "
                        "Tu peux la suivre sur la page **/request**.",
                    ),
                    provider=self.name,
                    model=self.model,
                )
            if skill == "modify_prompt_system":
                return ProviderResult(
                    content=_wrap_demo_thinking(
                        system,
                        f"Mon prompt système « {data.get('scope')} » est passé en v{data.get('version')}.",
                    ),
                    provider=self.name,
                    model=self.model,
                )
            return ProviderResult(
                content=_wrap_demo_thinking(
                    system,
                    "Outil exécuté : " + json.dumps(data, ensure_ascii=False)[:300],
                ),
                provider=self.name,
                model=self.model,
            )

        # --- Décision de la première itération ---
        if "zelda" in t:
            use_date = _DATE_RULE_MARKER in system
            return ProviderResult(
                content="",
                tool_calls=[_tool_call("search_knowledge", {"query": "Zelda", "use_date": use_date})],
                provider=self.name,
                model=self.model,
            )
        if "tes compétences" in t or "tes skills" in t or "ta liste de skills" in t:
            from core.skills import manager as skills_manager

            lines = [f"- **{s['name']}** : {s['description']}" for s in skills_manager.list_skills()]
            return ProviderResult(
                content=_wrap_demo_thinking(
                    system,
                    "Mes compétences actuelles :\n" + "\n".join(lines) + "\n\n(mode démo local)",
                ),
                provider=self.name,
                model=self.model,
            )
        if "prompt" in t:
            from core.prompt_system import registry

            p = registry.get_current("main")
            hist = p.get("history", [])[-1]
            extra = (
                f"\nDernière modification (v{p['version']}) : {hist.get('reason')}"
                if hist
                else "\nAucune auto-modification pour l'instant — essaie la question Zelda !"
            )
            return ProviderResult(
                content=_wrap_demo_thinking(
                    system,
                    f"Mon prompt système « main » est en **v{p['version']}** ({p.get('updated_by', 'seed')}).{extra}",
                ),
                provider=self.name,
                model=self.model,
            )
        if re.search(r"(cherche sur le web|scrape|scrap|crawl|fetch)", t):
            m = re.search(r"https?://\S+", last_user)
            kind = "fetch" if m else "search"
            target = m.group(0).rstrip(".,) ") if m else t.strip()[:120]
            return ProviderResult(
                content="",
                tool_calls=[
                    _tool_call(
                        "add_research_task",
                        {"kind": kind, "target": target, "reason": f"Demandé par l'utilisateur : {last_user[:120]}"},
                    )
                ],
                provider=self.name,
                model=self.model,
            )
        if re.search(r"(propose|demande|ajoute|crée).*(au dev|à dev|fonctionnalité|feature)", t) or "demande au dev" in t:
            return ProviderResult(
                content="",
                tool_calls=[
                    _tool_call(
                        "request_to_dev",
                        {"title": last_user.strip()[:100], "description": last_user.strip(), "type": "feature"},
                    )
                ],
                provider=self.name,
                model=self.model,
            )
        # Moteurs cloud au repos ≠ aucune clé configurée : adapter le message.
        errors = provider_errors()
        if not errors:
            return ProviderResult(
                content=_wrap_demo_thinking(system, _DEMO_EXPLAINED),
                provider=self.name,
                model=self.model,
            )
        retry_in = next_retry_in()
        details = "\n".join(f"- {message.split(' — ')[0]}" for message in errors[:4])
        when = f" Prochain test automatique dans **{human_delay(retry_in)}**." if retry_in else ""
        return ProviderResult(
            content=_wrap_demo_thinking(
                system,
                f"{_DEMO_EXPLAINED_CLOUD_DOWN}{when}\n\nMoteurs au repos :\n{details}",
            ),
            provider=self.name,
            model=self.model,
        )


def human_delay(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 90:
        return f"~{max(1, seconds // 5 * 5)} s"
    if seconds < 3600:
        return f"~{seconds // 60} min"
    if seconds < 86400:
        hours, minutes = divmod(seconds // 60, 60)
        return f"~{hours} h{f'{minutes:02d}' if minutes else ''}"
    return f"~{seconds // 86400} j"


# ---------------------------------------------------------------------------
# Construction de la chaîne
# ---------------------------------------------------------------------------
def _models_from_env(spec: ProviderSpec) -> list[str]:
    """Modèles du provider : `MISTRAL_MODEL=a,b` (liste) ou défaut du catalogue.

    Un ID retiré est conservé s'il est demandé explicitement (l'utilisateur le
    verra échouer avec un message qui dit quoi mettre à la place) — mais il ne
    sera JAMAIS choisi par défaut.
    """
    raw = (env(spec.model_env) or "").strip()
    if not raw:
        return list(spec.models)
    wanted = [part.strip() for part in re.split(r"[,;]", raw) if part.strip()]
    models: list[str] = []
    for model in wanted:
        if model not in models:
            models.append(model)
    # Les modèles du catalogue restants servent de secours automatique.
    for model in spec.models:
        if model not in models:
            models.append(model)
    return models


def build_provider(spec: ProviderSpec, api_key: str) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        spec.name,
        spec.base_url,
        api_key,
        _models_from_env(spec),
        min_interval=spec.limits.min_interval(),
        extra_headers=spec.extra_headers,
        extra_body=spec.extra_body,
        enable_extra_body_env=spec.enable_extra_body_env,
        completion_tokens_models=spec.completion_tokens_models,
        limits=spec.limits,
        daily_tz=spec.daily_quota_tz,
        label=spec.label,
    )


def _chain_signature() -> tuple:
    """Empreinte de la configuration : si elle change, on reconstruit la chaîne."""
    return tuple((spec.name, (env(spec.key_env) or "").strip(), env(spec.model_env)) for spec in SPECS)


_chain_lock = threading.Lock()
_cached_chain: list[Any] | None = None
_cached_chain_signature: tuple | None = None


def build_chain() -> list[Any]:
    """Construire la chaîne de providers (premier configuré = principal).

    La chaîne est mise en cache tant que `.env` ne change pas : les instances
    conservent leur throttle et leur modèle courant entre deux messages, et le
    « provider préféré » reste identifiable d'un appel à l'autre.
    """
    global _cached_chain, _cached_chain_signature
    signature = _chain_signature()
    with _chain_lock:
        if _cached_chain is not None and _cached_chain_signature == signature:
            return _cached_chain
        chain: list[Any] = []
        for spec in SPECS:
            api_key = (env(spec.key_env) or "").strip()
            if api_key:
                chain.append(build_provider(spec, api_key))
        chain.append(LocalDemoProvider())  # toujours disponible en dernier recours
        _cached_chain = chain
        _cached_chain_signature = signature
        return chain


def configured_providers() -> list[str]:
    """Providers avec une clé dans .env (sans appel réseau)."""
    return [spec.name for spec in SPECS if (env(spec.key_env) or "").strip()]


# ---------------------------------------------------------------------------
# Santé des providers (disjoncteur) : qui est au repos, jusqu'à quand, pourquoi
# ---------------------------------------------------------------------------
@dataclass
class ProviderHealth:
    failure: Failure | None = None
    ready_at: float = 0.0  # time.monotonic() ; 0 = prêt
    consecutive: int = 0
    total_failures: int = 0
    last_ok_at: float = 0.0  # time.time()

    def ready_in(self) -> float:
        if self.ready_at <= 0.0:
            return 0.0
        return max(0.0, self.ready_at - time.monotonic())

    def to_dict(self, name: str) -> dict:
        out = {
            "provider": name,
            "ready": self.ready_in() <= 0.0,
            "retry_in_s": round(self.ready_in(), 1),
            "consecutive_failures": self.consecutive,
            "total_failures": self.total_failures,
            "last_ok_at": self.last_ok_at or None,
        }
        if self.failure:
            out["failure"] = {
                "kind": self.failure.kind,
                "status": self.failure.status,
                "model": self.failure.model,
                "message": self.failure.message,
                "hint": self.failure.hint,
                "retry_after_s": self.failure.retry_after_s,
            }
        return out


class HealthRegistry:
    """Disjoncteur par provider : on ne rappelle PAS un moteur au repos.

    Avant cette refonte, un échec cloud renvoyait directement en mode démo et la
    chaîne n'était re-testée qu'après un repos global de 60 s. Résultat : un
    seul 429 Mistral masquait une clé Groq/Gemini parfaitement valide.
    Maintenant chaque provider a son propre repos, calculé d'après ce que l'API
    annonce (Retry-After, x-ratelimit-reset-*, fenêtre journalière/mensuelle).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._health: dict[str, ProviderHealth] = {}

    def _entry(self, name: str) -> ProviderHealth:
        entry = self._health.get(name)
        if entry is None:
            entry = ProviderHealth()
            self._health[name] = entry
        return entry

    def ready_in(self, name: str) -> float:
        with self._lock:
            return self._entry(name).ready_in()

    def is_ready(self, name: str) -> bool:
        return self.ready_in(name) <= 0.0

    def force_ready(self, name: str | None = None) -> None:
        """Remettre un provider (ou tous) en service — utilisé par les tests."""
        with self._lock:
            names = list(self._health) if name is None else [name]
            for key in names:
                entry = self._health.get(key)
                if entry:
                    entry.ready_at = 0.0
                    entry.consecutive = 0

    def note_failure(self, name: str, failure: Failure, cooldown: float | None = None) -> ProviderHealth:
        with self._lock:
            entry = self._entry(name)
            entry.failure = failure
            entry.consecutive += 1
            entry.total_failures += 1
            entry.ready_at = time.monotonic() + (cooldown if cooldown is not None else COOLDOWN_UNKNOWN_S)
            return entry

    def note_success(self, name: str) -> ProviderHealth:
        with self._lock:
            entry = self._entry(name)
            entry.failure = None
            entry.consecutive = 0
            entry.ready_at = 0.0
            entry.last_ok_at = time.time()
            return entry

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {name: entry.to_dict(name) for name, entry in self._health.items()}


HEALTH = HealthRegistry()

# Provider « préféré » (celui qui a répondu en dernier) : sert de point d'entrée
# rapide, sans re-tester toute la chaîne à chaque message.
_state_lock = threading.Lock()
_preferred: Any | None = None


def _demo_provider() -> LocalDemoProvider:
    return LocalDemoProvider()


def provider_errors() -> list[str]:
    """Messages des providers actuellement au repos (vide si tout va bien)."""
    out: list[str] = []
    for name, entry in HEALTH.snapshot().items():
        if entry.get("ready") or not entry.get("failure"):
            continue
        out.append(entry["failure"]["message"])
    return out


def next_retry_in() -> float:
    """Secondes avant le prochain re-test automatique (0 si aucun au repos)."""
    waits = [e["retry_in_s"] for e in HEALTH.snapshot().values() if not e.get("ready")]
    return min(waits) if waits else 0.0


def health_report() -> dict:
    """État complet, servi par /api/status (et par la bannière du site)."""
    snapshot = HEALTH.snapshot()
    resting = [e for e in snapshot.values() if not e.get("ready")]
    return {
        "configured": configured_providers(),
        "active": _preferred.name if _preferred is not None else None,
        "chain": [p.name for p in build_chain()],
        "health": snapshot,
        "errors": [e["failure"]["message"] for e in resting if e.get("failure")],
        "hints": [e["failure"]["hint"] for e in resting if e.get("failure", {}).get("hint")],
        "retry_in_s": round(next_retry_in(), 1),
        "retry_in_human": human_delay(next_retry_in()) if resting else "",
        "limits": {
            p.name: {
                "label": p.label,
                "model": p.model,
                "models": list(getattr(p, "models", [p.model])),
                "limits": p.limits.summary(),
                "min_interval_s": p.min_interval,
                "quota_headers": getattr(p, "last_quota", {}),
            }
            for p in build_chain()
            if p.name != "demo-local"
        },
    }


def get_active_provider() -> tuple[Any, list[str]]:
    """Premier provider utilisable SANS appel réseau (respecte les repos en cours).

    Conservé pour compatibilité : le chat passe par `chat_with_failover`, qui
    teste réellement les providers au besoin.
    """
    chain = build_chain()
    errors: list[str] = []
    for provider in chain:
        if provider.name == "demo-local":
            break
        wait = HEALTH.ready_in(provider.name)
        if wait > 0.0:
            entry = HEALTH.snapshot().get(provider.name, {}).get("failure", {})
            errors.append(entry.get("message") or f"{provider.name}: au repos encore {human_delay(wait)}")
            continue
        return provider, errors
    return chain[-1], errors or provider_errors()


def invalidate_provider_cache() -> None:
    """Compatibilité : remet le provider préféré à None (le prochain message reteste)."""
    global _preferred
    with _state_lock:
        _preferred = None


def active_provider_errors() -> list[str]:
    """Alias de compatibilité (utilisé par le mode démo et /api/status)."""
    return provider_errors()


def primary_provider_name() -> str:
    """Nom à afficher : le provider préféré s'il est connu, sinon le premier configuré."""
    if _preferred is not None:
        return _preferred.name
    chain = build_chain()
    return chain[0].name


@dataclass
class FailoverOutcome:
    result: ProviderResult
    provider: Any
    errors: list[str]
    attempts: list[dict] = field(default_factory=list)
    fell_back_to_demo: bool = False


def chat_with_failover(
    messages: list[dict],
    tools: list[dict] | None = None,
    *,
    chain: list[Any] | None = None,
    on_attempt: Callable[[Any], None] | None = None,
) -> FailoverOutcome:
    """Appeler le premier moteur disponible ; en cas d'échec, PASSER AU SUIVANT.

    Ordre réel : provider préféré → reste de la chaîne (ceux qui ne sont pas au
    repos) → démo locale. Chaque échec est classé (`classify_failure`) et met le
    provider au repos pour la durée appropriée, donc un moteur en 429 n'est plus
    rappelé pendant sa fenêtre de quota et les suivants prennent le relais au
    lieu de basculer tout le site en mode démo.
    """
    global _preferred
    chain = chain if chain is not None else build_chain()
    cloud = [p for p in chain if p.name != "demo-local"]
    demo = next((p for p in chain if p.name == "demo-local"), _demo_provider())

    with _state_lock:
        preferred = _preferred
    preferred_name = getattr(preferred, "name", None)
    ordered: list[Any] = [p for p in cloud if p.name == preferred_name] if preferred_name else []
    ordered.extend(p for p in cloud if not any(p.name == o.name for o in ordered))

    errors: list[str] = []
    attempts: list[dict] = []

    for provider in ordered:
        wait = HEALTH.ready_in(provider.name)
        if wait > 0.0:
            snapshot = HEALTH.snapshot().get(provider.name, {})
            failure = snapshot.get("failure") or {}
            reason = failure.get("message") or f"{provider.name}: au repos"
            errors.append(f"{reason} (repos encore {human_delay(wait)})")
            attempts.append(
                {
                    "provider": provider.name,
                    "model": getattr(provider, "model", ""),
                    "status": "skipped",
                    "reason": f"cooling_down:{int(wait)}s",
                }
            )
            continue
        try:
            if on_attempt:
                on_attempt(provider)
            result = provider.chat(messages, tools)
            HEALTH.note_success(provider.name)
            with _state_lock:
                _preferred = provider
            attempts.append(
                {
                    "provider": provider.name,
                    "model": result.model or getattr(provider, "model", ""),
                    "status": "ok",
                }
            )
            return FailoverOutcome(result=result, provider=provider, errors=errors, attempts=attempts)
        except Exception as exc:  # noqa: BLE001 — on replie vers le moteur suivant
            current_model = getattr(provider, "model", "")
            failure = classify_failure(
                exc,
                provider_name=provider.name,
                model=current_model,
                limits=getattr(provider, "limits", None),
                daily_tz=getattr(provider, "daily_tz", "utc"),
            )
            wait_s = cooldown_for(failure, getattr(provider, "daily_tz", "utc"))
            HEALTH.note_failure(provider.name, failure, wait_s)
            message = failure.message
            if failure.hint:
                message = f"{message} → {failure.hint}"
            errors.append(f"{message} (repos {human_delay(wait_s)}, essai du moteur suivant)")
            attempts.append(
                {
                    "provider": provider.name,
                    "model": failure.model or getattr(provider, "model", ""),
                    "status": "failed",
                    "kind": failure.kind,
                    "reason": message[:200],
                }
            )

    # Tous les moteurs cloud sont au repos ou en échec : démo locale (jamais
    # d'exception → le site ne se bloque pas), sans appel réseau supplémentaire.
    with _state_lock:
        _preferred = demo
    result = demo.chat(messages, tools)
    attempts.append({"provider": demo.name, "model": demo.model, "status": "ok"})
    if not errors:
        errors = provider_errors()
    return FailoverOutcome(
        result=result,
        provider=demo,
        errors=errors,
        attempts=attempts,
        fell_back_to_demo=True,
    )


class StreamAccumulator:
    """Recompose le flux d'un provider en réponse texte + d'éventuels tool_calls.

    - `text`      : les deltas de contenu concaténés (vide si tool_call pur).
    - `tool_calls()` : les tool_calls finaux une fois le flux terminé ([] sinon).
      Lève `StreamInterruptedError` si un appel d'outil est incomplet.
    """

    def __init__(self, provider_name: str = "", model: str = "") -> None:
        self.text = ""
        self.provider = provider_name
        self.model = model
        self._call_parts: list[ProviderResult] = []

    def add(self, frag: ProviderResult) -> None:
        self.provider = frag.provider or self.provider
        self.model = frag.model or self.model
        self.text += frag.content or ""
        if frag.tool_calls:
            self._call_parts.append(frag)

    def tool_calls(self) -> list[dict]:
        if not self._call_parts:
            return []
        picks: dict[int, dict] = {}
        for frag in self._call_parts:
            for tc in frag.tool_calls or []:
                idx = tc.get("index")
                if not isinstance(idx, int):
                    idx = 0
                slot = picks.setdefault(
                    idx,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                fn = tc.get("function") or {}
                if tc.get("id"):
                    slot["id"] = tc["id"]
                if tc.get("type"):
                    slot["type"] = tc["type"]
                if fn.get("name"):
                    slot["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    slot["function"]["arguments"] += fn["arguments"]
        picked = [picks[i] for i in sorted(picks)]
        # Un tool_call dont les arguments ne sont pas terminés (flux coupé) est
        # invalide : on le signale pour forcer un re-routage non-streamé.
        for c in picked:
            try:
                json.loads(c["function"]["arguments"] or "{}")
            except ValueError as exc:
                raise StreamInterruptedError("appel d'outil incomplet dans le flux") from exc
        return picked


def stream_with_failover(
    messages: list[dict],
    tools: list[dict] | None = None,
    *,
    chain: list[Any] | None = None,
) -> Iterator[dict]:
    """Variante streamée de `chat_with_failover` : un générateur qui diffuse EN DIRECT.

    Événements produits (à destination de l'orchestrateur de `core/ai/chat.py`) :
    - `{"type": "token", "content", "provider", "model"}` : un delta de la réponse
      finale (le front l'affiche tel quel, en direct).
    - `{"type": "result", "result": ProviderResult, "provider": Provider,
       "errors": [...], "attempts": [...]}` : le résultat complet (contenu final
      ET tool_calls éventuels), quand le flux est proprement terminé.

    Règles :
    - On ne diffuse des `token` que pour une vraie réponse texte. Un pur appel
      d'outil (aucun texte) ne produit AUCUN token : les deltas de tool_call sont
      accumulés en interne (`StreamAccumulator`) puis rendus dans `result`.
    - Flux coupé après 200 → `StreamInterruptedError` → bascule NON-streamée via
      `chat_with_failover` (la réponse complète arrive d'un bloc).
    - 429 / moteur au repos → même cascade que le non-streamé (provider suivant,
      puis démo locale).
    """
    global _preferred
    chain = chain if chain is not None else build_chain()
    cloud = [p for p in chain if p.name != "demo-local"]
    demo = next((p for p in chain if p.name == "demo-local"), _demo_provider())

    with _state_lock:
        preferred = _preferred
    preferred_name = getattr(preferred, "name", None)
    ordered: list[Any] = [p for p in cloud if p.name == preferred_name] if preferred_name else []
    ordered.extend(p for p in cloud if not any(p.name == o.name for o in ordered))

    errors: list[str] = []
    attempts: list[dict] = []

    for provider in ordered:
        wait = HEALTH.ready_in(provider.name)
        if wait > 0.0:
            snapshot = HEALTH.snapshot().get(provider.name, {})
            failure = snapshot.get("failure") or {}
            reason = failure.get("message") or f"{provider.name}: au repos"
            errors.append(f"{reason} (repos encore {human_delay(wait)})")
            attempts.append(
                {
                    "provider": provider.name,
                    "model": getattr(provider, "model", ""),
                    "status": "skipped",
                    "reason": f"cooling_down:{int(wait)}s",
                }
            )
            continue
        streamer = getattr(provider, "stream_chat", None)
        if not callable(streamer):
            # Provider sans méthode stream (ne devrait pas arriver) : non-streamé.
            outcome = chat_with_failover(messages, tools)
            if outcome.result.content:
                yield {
                    "type": "token",
                    "content": outcome.result.content,
                    "provider": outcome.provider.name,
                    "model": outcome.result.model or getattr(outcome.provider, "model", ""),
                }
            yield {
                "type": "result",
                "result": outcome.result,
                "provider": outcome.provider,
                "errors": errors + outcome.errors,
                "attempts": attempts + outcome.attempts,
            }
            return
        try:
            acc = StreamAccumulator(provider.name, getattr(provider, "model", ""))
            opened = False
            for frag in streamer(messages, tools):
                opened = True
                acc.add(frag)
                if frag.content:
                    yield {
                        "type": "token",
                        "content": frag.content,
                        "provider": provider.name,
                        "model": frag.model or getattr(provider, "model", ""),
                    }
            if not opened:
                continue  # flux vide : passe au provider suivant (rare)
            tool_calls = acc.tool_calls()
            HEALTH.note_success(provider.name)
            with _state_lock:
                _preferred = provider
            result = ProviderResult(
                content=acc.text,
                tool_calls=tool_calls or None,
                provider=provider.name,
                model=acc.model or getattr(provider, "model", ""),
            )
            attempts.append(
                {"provider": provider.name, "model": result.model, "status": "ok", "streamed": True}
            )
            yield {"type": "result", "result": result, "provider": provider, "errors": errors, "attempts": attempts}
            return
        except StreamInterruptedError as exc:
            # Flux ouvert puis coupé : impossible de le reprendre là où il s'est
            # arrêté → on redemande la réponse complète en non-streamé. Le front
            # remplacera le texte partiel par `done.reply` de toute façon.
            errors.append(f"{provider.name}: {exc}")
            attempts.append(
                {
                    "provider": provider.name,
                    "model": getattr(provider, "model", ""),
                    "status": "failed",
                    "kind": "stream_interrupted",
                    "reason": str(exc),
                }
            )
            outcome = chat_with_failover(messages, tools)
            yield {
                "type": "result",
                "result": outcome.result,
                "provider": outcome.provider,
                "errors": errors + outcome.errors,
                "attempts": attempts + outcome.attempts,
            }
            return
        except Exception as exc:  # noqa: BLE001 — on replie vers le moteur suivant
            current_model = getattr(provider, "model", "")
            failure = classify_failure(
                exc,
                provider_name=provider.name,
                model=current_model,
                limits=getattr(provider, "limits", None),
                daily_tz=getattr(provider, "daily_tz", "utc"),
            )
            wait_s = cooldown_for(failure, getattr(provider, "daily_tz", "utc"))
            HEALTH.note_failure(provider.name, failure, wait_s)
            message = failure.message
            if failure.hint:
                message = f"{message} → {failure.hint}"
            errors.append(f"{message} (repos {human_delay(wait_s)}, essai du moteur suivant)")
            attempts.append(
                {
                    "provider": provider.name,
                    "model": failure.model or getattr(provider, "model", ""),
                    "status": "failed",
                    "kind": failure.kind,
                    "reason": message[:200],
                }
            )

    # Tous les moteurs cloud sont au repos ou en échec : démo locale.
    with _state_lock:
        _preferred = demo
    result = demo.chat(messages, tools)
    attempts.append({"provider": demo.name, "model": demo.model, "status": "ok"})
    if not errors:
        errors = provider_errors()
    if not result.tool_calls and result.content:
        yield {
            "type": "token",
            "content": result.content,
            "provider": demo.name,
            "model": result.model or demo.model,
        }
    yield {
        "type": "result",
        "result": result,
        "provider": demo,
        "errors": errors,
        "attempts": attempts,
        "fell_back_to_demo": True,
    }


def ping_chain(force: bool = False) -> dict:
    """Tester la chaîne (utilisé par /api/status quand on veut forcer un re-test).

    Coûte un appel par provider : à éviter sur les tiers gratuits à 50 req/jour.
    Par défaut on ne teste que les providers déjà prêts (pas de réveil forcé).
    """
    report: dict[str, Any] = {}
    for provider in build_chain():
        if provider.name == "demo-local":
            report[provider.name] = "ok (local)"
            continue
        wait = HEALTH.ready_in(provider.name)
        if wait > 0.0 and not force:
            report[provider.name] = f"au repos ({human_delay(wait)})"
            continue
        try:
            provider.ping()
            HEALTH.note_success(provider.name)
            report[provider.name] = f"ok ({provider.model})"
        except Exception as exc:  # noqa: BLE001
            failure = classify_failure(exc, provider_name=provider.name, model=provider.model)
            HEALTH.note_failure(provider.name, failure, cooldown_for(failure, provider.daily_tz))
            report[provider.name] = failure.message
    return report
