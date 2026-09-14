"""Multi-fournisseurs IA.

Chaîne de providers : Mistral (priorité) → Gemini → Groq → OpenRouter,
puis le provider de démonstration locale (aucune clé requise).
Tous les providers cloud parlent le protocole OpenAI-compatible
(chat/completions + tool calling), ce qui garantit la portabilité.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import env


@dataclass
class ProviderResult:
    content: str
    tool_calls: list[dict] | None = None
    provider: str = ""
    raw: dict = field(default_factory=dict)


class BaseProvider:
    name = "base"

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ProviderResult:
        raise NotImplementedError

    def ping(self) -> None:
        """Test de connexion BON MARCHÉ (appel 1 token, timeout courte).

        Ne pas surcharger pour un provider 100 % local : il est toujours dispo.
        """
        self.chat([{"role": "user", "content": "ping"}])


class OpenAICompatProvider(BaseProvider):
    """Client minimaliste pour toute API compatible OpenAI (Mistral, Groq,
    OpenRouter, Gemini endpoint compatible, ...)."""

    def __init__(self, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _post(self, body: dict[str, Any], timeout: float) -> dict:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ProviderResult:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }
        if tools:
            body["tools"] = tools
        data = self._post(body, timeout=120)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"réponse inattendue de {self.name} : {str(data)[:200]}") from exc
        tool_calls = message.get("tool_calls") or None
        return ProviderResult(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            provider=self.name,
            raw=data,
        )

    def ping(self) -> None:
        """1 token, 20 s max : juste vérifier que la clé + l'endpoint répondent."""
        self._post(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0,
            },
            timeout=20,
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

_DATE_RULE_MARKER = "[REGLE-AJOUTEE-PAR-IA]"


def _tool_call(name: str, arguments: dict) -> dict:
    return {
        "id": f"call-demo-{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


class LocalDemoProvider(BaseProvider):
    name = "demo-local"

    def ping(self) -> None:
        """100 % local : toujours disponible, aucun test réseau à faire."""
        return None

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ProviderResult:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_texts = [m["content"] for m in messages if m["role"] == "user"]
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
                        "je viens de détecter ce défaut et je vais corriger mon prompt)_"
                    )
                    return ProviderResult(
                        content=(
                            f"D'après ma base de connaissances : **{e['title']}** "
                            f"({e.get('date', '?')}) — {e.get('summary', '')}{note}"
                        ),
                        provider=self.name,
                    )
                return ProviderResult(content="Aucun résultat dans ma base pour cette requête.", provider=self.name)
            if skill == "add_research_task":
                return ProviderResult(
                    content=(
                        f"Tâche de recherche ajoutée (id `{data.get('id')}`, statut "
                        f"{data.get('status', 'pending')}). Un service Chromium ou le notebook "
                        "Colab va l'exécuter — tu peux la suivre sur la page **/colab**."
                    ),
                    provider=self.name,
                )
            if skill == "request_to_dev":
                return ProviderResult(
                    content=(
                        f"Requête envoyée au développeur (id `{data.get('id')}`). "
                        "Tu peux la suivre sur la page **/request**."
                    ),
                    provider=self.name,
                )
            if skill == "modify_prompt_system":
                return ProviderResult(
                    content=f"Mon prompt système « {data.get('scope')} » est passé en v{data.get('version')}.",
                    provider=self.name,
                )
            return ProviderResult(content="Outil exécuté : " + json.dumps(data, ensure_ascii=False)[:300], provider=self.name)

        # --- Décision de la première itération ---
        if "zelda" in t:
            use_date = _DATE_RULE_MARKER in system
            return ProviderResult(
                content="",
                tool_calls=[_tool_call("search_knowledge", {"query": "Zelda", "use_date": use_date})],
                provider=self.name,
            )
        if "tes compétences" in t or "tes skills" in t or "ta liste de skills" in t:
            from core.skills import manager as skills_manager
            lines = [f"- **{s['name']}** : {s['description']}" for s in skills_manager.list_skills()]
            return ProviderResult(
                content="Mes compétences actuelles :\n" + "\n".join(lines) + "\n" + "(mode démo local)",
                provider=self.name,
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
                content=f"Mon prompt système « main » est en **v{p['version']}** ({p.get('updated_by', 'seed')}).{extra}",
                provider=self.name,
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
            )
        if re.search(r"(propose|demande|ajoute|crée).*(au dev|à dev|fonctionnalité|fonctionnalité|feature)", t) or "demande au dev" in t:
            return ProviderResult(
                content="",
                tool_calls=[
                    _tool_call(
                        "request_to_dev",
                        {"title": last_user.strip()[:100], "description": last_user.strip(), "type": "feature"},
                    )
                ],
                provider=self.name,
            )
        return ProviderResult(content=_DEMO_EXPLAINED, provider=self.name)


def build_chain() -> list[BaseProvider]:
    """Construire la chaîne de providers (premier configuré = principal)."""
    chain: list[BaseProvider] = []
    mistral_key = env("MISTRAL_API_KEY")
    if mistral_key:
        chain.append(
            OpenAICompatProvider(
                "mistral", "https://api.mistral.ai/v1", mistral_key, env("MISTRAL_MODEL", "mistral-small-latest")
            )
        )
    gemini_key = env("GEMINI_API_KEY")
    if gemini_key:
        chain.append(
            OpenAICompatProvider(
                "gemini",
                "https://generativelanguage.googleapis.com/v1beta/openai",
                gemini_key,
                env("GEMINI_MODEL", "gemini-2.5-flash"),
            )
        )
    groq_key = env("GROQ_API_KEY")
    if groq_key:
        chain.append(
            OpenAICompatProvider(
                "groq", "https://api.groq.com/openai/v1", groq_key, env("GROQ_MODEL", "llama-3.3-70b-versatile")
            )
        )
    openrouter_key = env("OPENROUTER_API_KEY")
    if openrouter_key:
        chain.append(
            OpenAICompatProvider(
                "openrouter",
                "https://openrouter.ai/api/v1",
                openrouter_key,
                env("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
            )
        )
    chain.append(LocalDemoProvider())  # toujours disponible en dernier recours
    return chain


# ---------------------------------------------------------------------------
# Sélection du provider ACTIF (mise en cache).
#
# Avant la correction : CHAQUE message du chat déclenchait un « ping » complet
# (vrai appel API avec le prompt système en entier) pour tester le provider →
# coût/latence doublés à chaque message. Maintenant : la sélection se fait UNE
# fois (au premier besoin) avec un ping de 1 token, le résultat est mis en
# cache, et le cache est invalidé si le provider échoue en cours de route
# (retour automatique sur demo-local pour le message en cours).
# ---------------------------------------------------------------------------
_selection_lock = threading.Lock()
_active_provider: BaseProvider | None = None
_active_provider_errors: list[str] = []


def get_active_provider() -> tuple[BaseProvider, list[str]]:
    """Renvoyer le premier provider disponible (testé UNE fois, puis mis en cache).

    Retourne (provider, erreurs_des_providers_sautés).
    """
    global _active_provider, _active_provider_errors
    with _selection_lock:
        if _active_provider is not None:
            return _active_provider, list(_active_provider_errors)
        chain = build_chain()
        errors: list[str] = []
        for candidate in chain:
            try:
                candidate.ping()
            except Exception as exc:  # noqa: BLE001 — on saute ce provider
                errors.append(f"{candidate.name}: {exc}")
                continue
            _active_provider = candidate
            _active_provider_errors = errors
            return candidate, list(errors)
        # Tous les providers cloud sont en échec : on s'accroche au mode démo
        # (il ne lève jamais d'exception) pour ne jamais bloquer le site.
        _active_provider = chain[-1]
        _active_provider_errors = errors
        return _active_provider, list(errors)


def invalidate_provider_cache() -> None:
    """Le provider actif vient d'échouer : on re-testera la chaîne au prochain message."""
    global _active_provider
    with _selection_lock:
        _active_provider = None


def active_provider_errors() -> list[str]:
    """Erreurs constatées lors de la sélection (vide tant que rien n'a été testé)."""
    return list(_active_provider_errors) if _active_provider is not None else []


def primary_provider_name() -> str:
    """Nom du provider à afficher : celui réellement actif (une fois sélectionné),
    sinon le premier configuré (sans appel réseau → fast, utilisable par /api/status)."""
    if _active_provider is not None:
        return _active_provider.name
    return build_chain()[0].name
