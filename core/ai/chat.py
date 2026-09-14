"""Orchestration du chat : assemblage du prompt (garde-fous mots-clés),
boucle d'appels d'outils (skills), et pas de RÉFLEXION.

Le pas de réflexion est l'essence du projet : après une réponse, l'IA
analyse sa propre sortie ; si un défaut est détecté (en mode démo : règle
déterministe ; en mode live : appelé par le modèle lui-même via sa mission
décrite dans le prompt), elle invoque `modify_prompt_system` → version,
historique, notification /request.
"""
from __future__ import annotations

import json
import re

from core import store as store_module
from core.prompt_system import registry
from core.skills import manager as skills_manager

from .providers import build_chain, get_active_provider, invalidate_provider_cache

MAX_TOOL_ITERATIONS = 6

_DATE_RULE_MARKER = "[REGLE-AJOUTEE-PAR-IA]"
_DATE_RULE = (
    "\n\n"
    "[REGLE-AJOUTEE-PAR-IA] AUTO-CORRECTION (v ajoutée par l'IA après défaut détecté) : "
    "quand l'utilisateur demande le PLUS RÉCENT / DERNIER élément d'une catégorie "
    "(ex. « le dernier jeu Zelda »), IL FAUT utiliser search_knowledge avec "
    "use_date=true (tri date décroissante). Ne JAMAIS renvoyer la première ligne de "
    "la base de connaissances sans vérifier la date demandée — c'est exactement le "
    "défaut que j'ai commis (question « dernier Zelda » → réponse avec le Zelda de 1986)."
)


def _last_user_text(history: list[dict]) -> str:
    for m in reversed(history):
        if m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def _demo_needs_reflection(user_text: str, system_prompt: str, reply: str) -> bool:
    """Règle déterministe (mode démo) : reproduction fidèle de l'exemple du README.

    L'utilisateur demande le DERNIER Zelda ; la base est rangée de l'ancien au
    récent ; sans la règle date dans le prompt, l'IA a répondu avec 1986.
    """
    t = user_text.lower()
    if "zelda" not in t:
        return False
    asked_date = any(w in t for w in ("dernier", "dernière", "latest", "plus récent", "plus recente", "recent"))
    if not asked_date:
        return False
    if _DATE_RULE_MARKER in system_prompt:
        return False  # la règle est déjà là : la réponse devrait être bonne
    if "1986" in reply and "Tears of the Kingdom" not in reply:
        return True
    return False


def _demo_apply_self_correction(scope: str, reason: str) -> dict | None:
    prompt = registry.get_current(scope)
    new_content = prompt["content"] + _DATE_RULE
    return skills_manager.execute(
        "modify_prompt_system",
        {"scope": scope, "reason": reason, "new_content": new_content},
    )


def handle_chat(history: list[dict]) -> dict:
    """Traiter une conversation (l'ensemble du historique est envoyé par le site).

    Retourne : { reply, provider, events: [{type: tool|prompt_update, ...}], system_assembled: bool }
    """
    store_module.get_store().seed_if_empty("dev_requests", [])
    store_module.get_store().seed_if_empty("research_tasks", [])
    store_module.get_store().seed_if_empty("research_results", [])

    user_text = _last_user_text(history)
    chosen = registry.select_for_user_input(user_text)
    system = registry.assemble_system_prompt(chosen)

    messages: list[dict] = [{"role": "system", "content": system}, *history]
    tools = skills_manager.to_openai_tools()

    events: list[dict] = []
    reply = ""

    # --- Choix du provider (sélection testée UNE fois par process, puis en cache) ---
    provider, errors = get_active_provider()
    provider_name = provider.name

    # --- Boucle principale : LLM ↔ outils ---
    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            result = provider.chat(messages, tools)
        except Exception as exc:  # noqa: BLE001
            if provider.name != "demo-local":
                errors.append(f"{provider.name}: {exc}")
                # Le provider en panne est écarté du cache : le prochain message
                # re-testera la chaîne complète (il peut être rétabli d'ici là).
                invalidate_provider_cache()
                fallback = next((p for p in build_chain() if p.name == "demo-local"), provider)
                provider = fallback
                provider_name = provider.name
                result = provider.chat(messages, tools)
            else:
                raise
        provider_name = result.provider or provider_name

        if result.tool_calls:
            messages.append(
                {"role": "assistant", "content": result.content or "", "tool_calls": result.tool_calls}
            )
            for tc in result.tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {}
                tool_result = skills_manager.execute(name, args)
                events.append({"type": "tool", "skill": name, "args": args, "result": tool_result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", "call-0"),
                        "name": name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
            continue

        reply = result.content or "(réponse vide)"
        break

    if not reply:
        # La boucle d'outils est épuisée sans réponse finale (trop d'appels d'outils).
        reply = "(réponse interrompue : trop d'appels d'outils enchaînés — réessaie)."

    # --- Pas de réflexion : l'IA analyse sa propre réponse ---
    if provider_name == "demo-local" and _demo_needs_reflection(user_text, system, reply):
        result = _demo_apply_self_correction(
            "main",
            "Défaut détecté en auto-analyse : question « dernier jeu Zelda » → j'ai renvoyé la "
            "première ligne de la base (1986) en ignorant la date demandée. J'ajoute une règle "
            "pour trier par date décroissante quand l'utilisateur demande le plus récent.",
        )
        if result and result.get("ok"):
            events.append(
                {
                    "type": "prompt_update",
                    "scope": "main",
                    "version": result.get("version"),
                    "reason": "Défaut détecté en auto-analyse : « dernier Zelda » → réponse 1986 (date ignorée).",
                    "trigger": "réflexion post-réponse (démo déterministe)",
                    "author": "ai",
                }
            )

    out = {
        "reply": reply,
        "provider": provider_name,
        "events": events,
        "prompt_ids": [p["id"] for p in chosen],
    }
    if errors:
        out["warnings"] = errors
    return out
