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
from collections.abc import Iterator

from core import store as store_module
from core.prompt_system import registry
from core.skills import manager as skills_manager

from .providers import (
    ProviderResult,
    chat_with_failover,
    human_delay,
    next_retry_in,
    stream_with_failover,
)

MAX_TOOL_ITERATIONS = 6
#: Garde-fou de l'ORCHESTRATEUR : dans une boucle d'outils, le modèle est interdit
#: de rester plus de quelques tours sur le dernier message. Au-delà, le message est
#: coupé et l'excédent signalé au dev — l'IA ne peut plus saturer son propre
#: historique et franchir la fenêtre de contexte (faille de debut).
TOOL_ITERATION_HARD_LIMIT = 3

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


def _seed_stores() -> None:
    """Collections vides prêtes pour le mode local (gitignore'd, non versionnées)."""
    store_module.get_store().seed_if_empty("dev_requests", [])
    store_module.get_store().seed_if_empty("research_tasks", [])
    store_module.get_store().seed_if_empty("research_results", [])


def _announce_excess_iterations(last_n: int, max_user: int) -> dict:
    """Garde-fou : le dernier message utilisateur est saturé d'appels d'outils.

    On note un `last_user_index` convenu entre le front et le back (le front
    saura quels messages purger de l'historique avant de re-causer), puis on
    ouvre une requête au dev — non seulement pour auditer, mais parce que le
    champ `last_user_index` ne traverse pas les conversations relues plus tard.
    """
    store_module.get_store().add(
        "dev_requests",
        {
            "title": "[Garde-fou] Boucle d'outils saturée sur le dernier message",
            "description": (
                f"La boucle LLM↔outils a passé {last_n} tours (limite {max_user}) sur le dernier "
                "message utilisateur, sans réponse finale. Le message a été coupé et l'historique "
                "en excès signalé au front (champ `last_user_index` réinjecté dans `messages`). "
                "À surveiller : une IA qui enchaîne les auto-modifications pourrait masquer un défaut."
            ),
            "type": "other",
            "from_role": "ai",
            "status": "info",
        },
    )
    return {
        "announce_slack": "garde-fou boucle d'outils",
        "last_user_index": last_n,
    }


def _tool_message_for(tc: dict) -> dict | None:
    """Exécute un tool_call et prépare la réponse `tool` pour le LLM.

    Retourne None si le skills manager a renvoyé `ok=False` (l'IA est alors
    privée du retour ET du droit de réessayer le même outil — anti-boucle).
    """
    fn = tc.get("function", {})
    name = fn.get("name", "")
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except ValueError:
        args = {}
    result = skills_manager.execute(name, args)
    if result.get("ok") is False:
        return None
    return {
        "role": "tool",
        "tool_call_id": tc.get("id", "call-0"),
        "name": name,
        "content": json.dumps(result, ensure_ascii=False),
        "_event": {"type": "tool", "skill": name, "args": args, "result": result},
    }


def _build_state(history: list[dict]) -> dict:
    """Prépare le tour : prompt choisi, messages système, outils, compteurs."""
    _seed_stores()
    user_text = _last_user_text(history)
    chosen = registry.select_for_user_input(user_text)
    system = registry.assemble_system_prompt(chosen)
    return {
        "user_text": user_text,
        "chosen": chosen,
        "system": system,
        "messages": [{"role": "system", "content": system}, *history],
        "tools": skills_manager.to_openai_tools(),
        "events": [],
        "errors": [],
        "error_providers": set(),
        "attempts": [],
        "provider": "",
        "model": "",
    }


def _note_outcome(state: dict, outcome) -> None:
    # `outcome` peut être un FailoverOutcome (attributs) ou un dict (clés).
    attempts = getattr(outcome, "attempts", None)
    if attempts is None and isinstance(outcome, dict):
        attempts = outcome.get("attempts")
    errors = getattr(outcome, "errors", None)
    if errors is None and isinstance(outcome, dict):
        errors = outcome.get("errors")
    for a in attempts or []:
        state["attempts"].append(a)
    for message in errors or []:
        name = message.split(":", 1)[0]
        if name in state["error_providers"]:
            continue
        state["error_providers"].add(name)
        state["errors"].append(message)


def _run_tool_turn(state: dict, result: ProviderResult) -> bool:
    """Exécute les tool_calls d'un résultat et alimente `messages` + `events`.

    Ordre OpenAI attendu : [assistant(tool_calls), tool(call_1), tool(call_2), …].
    On exécute donc d'abord tous les outils, puis on insère le message assistant
    avant les retours `tool`. Un outil refusé (`ok=False`) reçoit un retour
    d'échec plutôt que rien, pour que l'IA rebondisse au lieu de réitérer.
    """
    tool_msgs: list[dict] = []
    for tc in result.tool_calls or []:
        tool_state = _tool_message_for(tc)
        if tool_state is None:
            result_ok = {"ok": False, "error": "exécution refusée (skill inconnue ou échec)"}
            tool_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", "call-0"),
                    "name": tc.get("function", {}).get("name", ""),
                    "content": json.dumps(result_ok, ensure_ascii=False),
                }
            )
            state["events"].append(
                {
                    "type": "tool",
                    "skill": tc.get("function", {}).get("name", ""),
                    "args": {},
                    "result": result_ok,
                }
            )
            continue
        tool_msgs.append(
            {
                "role": "tool",
                "tool_call_id": tool_state["tool_call_id"],
                "name": tool_state["name"],
                "content": tool_state["content"],
            }
        )
        state["events"].append(tool_state["_event"])
    state["messages"].append(
        {
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": result.tool_calls,
        }
    )
    state["messages"].extend(tool_msgs)
    return True


def _next_retry_fields() -> dict:
    retry_in = next_retry_in()
    return {
        "provider_retry_in_s": round(retry_in, 1),
        "provider_retry_in_human": human_delay(retry_in) if retry_in else "",
    }


def _live_turn(history: list[dict]) -> Iterator[dict]:
    """Un tour de chat en streaming, identique sur le plan logique à `handle_chat`.

    Produit des événements `{type: "token", content, provider, model, first}`
    (chaque `token` est un delta réel, diffusé EN DIRECT) puis UN événement
    final `{type: "done", reply, provider, model, events, warnings?, attempts?,
    ...}`.

    Les tours d'outils (skills) sont exécutés côté serveur : quand le premier
    appel est un pur appel d'outil, aucun token n'est émis ; la diffusion ne
    commence que sur la réponse finale (via le provider qui y répond).
    """
    state = _build_state(history)
    history_n = len(history)

    last_user_stretch = 0
    first_token = True
    for iteration in range(MAX_TOOL_ITERATIONS):
        # --- Un appel (potentiellement streamé) ---------------------------
        result: ProviderResult | None = None
        provider_name = ""
        model = ""
        for ev in stream_with_failover(state["messages"], state["tools"]):
            if ev.get("type") == "token":
                yield {
                    "type": "token",
                    "content": ev.get("content", ""),
                    "provider": ev.get("provider", ""),
                    "model": ev.get("model", ""),
                    "first": first_token,
                }
                first_token = False
                continue
            if ev.get("type") == "result":
                result = ev.get("result")
                provider = ev.get("provider")
                provider_name = getattr(result, "provider", "") or getattr(provider, "name", "")
                model = getattr(result, "model", "") or ""
                _note_outcome(state, ev)
                continue
        if result is None:
            # Garde-fou ultime : aucun moteur n'a produit de résultat exploitable.
            reply = "(réponse vide)"
            done = _finalize_done(state, reply, history_n)
            done.update({"type": "done", "streamed": True})
            yield done
            return

        state["provider"] = provider_name
        state["model"] = model

        if result.tool_calls:
            last_user_stretch += 1
            if last_user_stretch > TOOL_ITERATION_HARD_LIMIT:
                break
            _run_tool_turn(state, result)
            continue

        # --- Réponse finale -------------------------------------------------
        reply = result.content or "(réponse vide)"
        done = _finalize_done(state, reply, history_n)
        done.update({"type": "done", "streamed": True})
        yield done
        return

    # Garde-fou : trop d'outils enchaînés sur le dernier message.
    extra = _announce_excess_iterations(history_n - 1, TOOL_ITERATION_HARD_LIMIT)
    reply = (
        "J'ai enchaîné trop d'outils (auto-analyse) sans parvenir à une réponse finale : "
        "j'ai signalé cet excès au développeur. Repose ta question, je serai plus concis."
    )
    if last_user_stretch > TOOL_ITERATION_HARD_LIMIT:
        _trim_excess_turns(state, history_n)
    done = _finalize_done(state, reply, history_n, extra)
    done.update({"type": "done", "streamed": True})
    yield done


def _trim_excess_turns(state: dict, history_n: int) -> None:
    """Retire les derniers tours assistant/tool d'une boucle en excès.

    On garde le début strict de la conversation (system + historique d'origine)
    ainsi que le dernier tour assistant/tool, pour que l'utilisateur conserver
    son contexte sans que la fenêtre de tokens ne déborde.
    """
    messages = state["messages"]
    base = messages[: history_n + 1]  # system + historique réel de la conversation
    tail = messages[history_n + 1 :]  # tours assistant/tool accumulés par la boucle
    # On ne garde que le dernier tour assistant→outils (contexte immédiat).
    cut = 0
    for i in range(len(tail) - 1, -1, -1):
        if tail[i].get("role") == "tool":
            cut = i
            break
    state["messages"] = base + tail[cut:]


def _finalize_done(state: dict, reply: str, history_n: int, extra: dict | None = None) -> dict:
    """Construit l'événement final `done` (réflexion démo comprise)."""
    events = list(state["events"])
    # --- Pas de réflexion : l'IA analyse sa propre réponse ---
    if state["provider"] == "demo-local" and _demo_needs_reflection(
        state["user_text"], state["system"], reply
    ):
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

    out: dict = {
        "reply": reply,
        "provider": state["provider"],
        "model": state["model"],
        "events": events,
        "prompt_ids": [p["id"] for p in state["chosen"]],
    }
    if extra:
        out.update(extra)
    if state["errors"]:
        out["warnings"] = state["errors"]
        out["fallback_to_demo"] = state["provider"] == "demo-local"
        out.update(_next_retry_fields())
        out["attempts"] = state["attempts"]
    return out


def handle_chat(history: list[dict]) -> dict:
    """Traiter une conversation (l'ensemble du historique est envoyé par le site).

    Retourne : { reply, provider, events: [{type: tool|prompt_update, ...}], system_assembled: bool }
    """
    state = _build_state(history)
    history_n = len(history)

    last_user_stretch = 0
    for iteration in range(MAX_TOOL_ITERATIONS):
        outcome = chat_with_failover(state["messages"], state["tools"])
        _note_outcome(state, outcome)
        result = outcome.result
        state["provider"] = result.provider or outcome.provider.name
        state["model"] = getattr(result, "model", "") or ""

        if result.tool_calls:
            last_user_stretch += 1
            if last_user_stretch > TOOL_ITERATION_HARD_LIMIT:
                break
            _run_tool_turn(state, result)
            continue

        reply = result.content or "(réponse vide)"
        return _finalize_done(state, reply, history_n)

    extra = _announce_excess_iterations(history_n - 1, TOOL_ITERATION_HARD_LIMIT)
    reply = (
        "J'ai enchaîné trop d'outils (auto-analyse) sans parvenir à une réponse finale : "
        "j'ai signalé cet excès au développeur. Repose ta question, je serai plus concis."
    )
    if last_user_stretch > TOOL_ITERATION_HARD_LIMIT:
        _trim_excess_turns(state, history_n)
    return _finalize_done(state, reply, history_n, extra)


def handle_chat_stream(history: list[dict]) -> Iterator[dict]:
    """Comme `handle_chat`, mais la réponse finale est diffusée en streaming (SSE).

    Produit une séquence d'événements dict :
    - fragments texte : { type: "token", content, provider, model, first }
    - message final   : { type: "done", reply, provider, model, streamed,
      events, prompt_ids, warnings?, fallback_to_demo?, attempts? }

    Le premier fragment `done` porte le flag `streamed=true`. Les tours d'outils
    (skills) sont exécutés côté serveur en non-streamé : le front ne reçoit des
    tokens que pour la réponse finale, jamais pour les appels intermédiaires.
    """
    yield from _live_turn(history)
