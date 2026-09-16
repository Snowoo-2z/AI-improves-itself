"""Orchestration du chat : assemblage du prompt, boucle d'appels d'outils (skills),
mode pensée (thinking) et pas de RÉFLEXION.

Le pas de réflexion est l'essence du projet : après une réponse, l'IA
analyse sa propre sortie ; si un défaut est détecté (en mode démo : règle
déterministe ; en mode live : appelé par le modèle lui-même via sa mission
décrite dans le prompt), elle invoque `modify_prompt_system` → version,
historique, notification /request.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator

from core import store as store_module
from core.prompt_system import registry
from core.skills import manager as skills_manager

from .providers import (
    ProviderResult,
    _display_text,
    chat_with_failover,
    human_delay,
    next_retry_in,
    stream_with_failover,
)

MAX_TOOL_ITERATIONS = 15
READ_ONLY_PARALLEL_SKILLS = {"search_knowledge", "list_research_results"}

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

THINKING_DIRECTIVE = (
    "\n\n---\n\n"
    "## MODE PENSÉE / THINKING (ACTIVÉ)\n"
    "Avant de formuler ta réponse finale, explicite l'intégralité de ta réflexion et de ton raisonnement "
    "pas à pas à l'intérieur d'un bloc balisé <think>...</think>.\n"
    "Dans ce bloc :\n"
    "- Décompose et analyse la demande de l'utilisateur.\n"
    "- Détermine la meilleure stratégie, les outils nécessaires si besoin, et les étapes logiques.\n"
    "- Valide la cohérence et l'exactitude des faits avant de formuler la réponse.\n"
    "Referme impérativement la balise avec </think>, puis formule directement ta réponse finale "
    "à destination de l'utilisateur en dehors de ces balises."
)


def _extract_thinking(raw: str) -> tuple[str, str | None]:
    """Sépare le bloc <think>...</think> de la réponse finale."""
    if not raw:
        return "", None
    match = re.search(r"<think>(.*?)</think>", raw, flags=re.DOTALL | re.IGNORECASE)
    if match:
        thinking = match.group(1).strip()
        reply = (raw[: match.start()] + raw[match.end() :]).strip()
        return reply, thinking if thinking else None
    open_match = re.search(r"<think>(.*)$", raw, flags=re.DOTALL | re.IGNORECASE)
    if open_match:
        thinking = open_match.group(1).strip()
        reply = raw[: open_match.start()].strip()
        return reply, thinking if thinking else None
    return raw.strip(), None


def _textify_content(content) -> str:
    """"Contenu d'un message → texte plat, même s'il est multimédia (vision)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for b in content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text":
                parts.append(str(b.get("text", "")))
            elif t == "image_url":
                img = b.get("image_url") or {}
                url = str(img.get("url", "")) if isinstance(img, dict) else str(img)
                parts.append("[image: " + (url[:60] or "sans URL") + "]")
        text = "\n".join(p for p in parts if p)
        return text or "[image]"
    return str(content or "")


def _textify_user_messages(messages: list[dict]) -> list[dict]:
    """En boucle d'outils, les blocs vision sont consommés après le 1er appel :
    ils sont convertis en texte pour que la suite de l'historique reste valide
    (le provider ne mémorise pas les images d'un tour à l'autre)."""
    out: list[dict] = []
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), list):
            out.append({**{k: v for k, v in m.items() if k != "content"}, "content": _textify_content(m.get("content"))})
        else:
            out.append(m)
    return out


def _last_user_text(history: list[dict]) -> str:
    for m in reversed(history):
        if m.get("role") == "user":
            return _textify_content(m.get("content", ""))
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


def _tool_message_for(tc: dict) -> dict | None:
    """Exécute un tool_call et prépare la réponse `tool` pour le LLM."""
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


def _build_state(history: list[dict], thinking: bool = False) -> dict:
    """Prépare le tour : prompt choisi, messages système, outils, compteurs."""
    _seed_stores()
    user_text = _last_user_text(history)
    chosen = registry.select_for_user_input(user_text)
    system = registry.assemble_system_prompt(chosen)
    if thinking:
        system += THINKING_DIRECTIVE
    return {
        "user_text": user_text,
        "thinking": thinking,
        "chosen": chosen,
        "system": system,
        "messages": [{"role": "system", "content": system}, *history],
        "tools": skills_manager.to_openai_tools(),
        "disabled_tools": set(),
        "tool_call_signatures": set(),
        "tool_call_counts": {},
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


def _tool_name(tc: dict) -> str:
    function = tc.get("function") or {}
    return str(function.get("name") or "")


def _tool_args(tc: dict) -> dict:
    function = tc.get("function") or {}
    try:
        args = json.loads(function.get("arguments") or "{}")
    except (TypeError, ValueError):
        args = {}
    return args if isinstance(args, dict) else {}


def _tool_signature(tc: dict) -> str:
    """Signature stable d'un appel pour détecter les rejoués du modèle."""
    return json.dumps(
        {"name": _tool_name(tc), "args": _tool_args(tc)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _disable_tool(state: dict, name: str) -> None:
    """Retire un outil devenu inutile pour la suite du même message."""
    if not name:
        return
    state.setdefault("disabled_tools", set()).add(name)
    state["tools"] = [
        tool
        for tool in state.get("tools", [])
        if (tool.get("function") or {}).get("name") != name
    ]


def _read_only_result(result: ProviderResult) -> bool:
    return bool(result.tool_calls) and all(
        _tool_name(tc) in READ_ONLY_PARALLEL_SKILLS for tc in result.tool_calls
    )


def _read_only_stretch(state: dict, result: ProviderResult) -> bool:
    return _read_only_result(result) and all(
        event.get("skill") in READ_ONLY_PARALLEL_SKILLS
        for event in state.get("events", [])
        if event.get("type") == "tool"
    )


def _force_final_answer(state: dict) -> str | None:
    """Demande une synthèse finale sans outils.

    Ce dernier appel ne peut plus relancer d'outil (tools=[]) : le modèle termine
    par du texte plutôt que de bloquer la réponse.
    """
    try:
        outcome = chat_with_failover(state["messages"], [])
    except Exception:  # noqa: BLE001
        return None
    _note_outcome(state, outcome)
    result = outcome.result
    state["provider"] = result.provider or outcome.provider.name
    state["model"] = getattr(result, "model", "") or ""
    if result.tool_calls:
        return None
    return result.content or "(réponse vide)"


_force_final_read_only_answer = _force_final_answer


def _run_tool_turn(state: dict, result: ProviderResult) -> bool:
    """Exécute les tool_calls d'un résultat et alimente `messages` + `events`.

    Tous les tool_calls demandés par le modèle sont exécutés et insérés
    selon le protocole OpenAI : [assistant(tool_calls), tool(call_1), tool(call_2), …].
    """
    tool_calls = list(result.tool_calls or [])
    tool_msgs: list[dict] = []
    signatures = state.setdefault("tool_call_signatures", set())
    counts = state.setdefault("tool_call_counts", {})

    for tc in tool_calls:
        name = _tool_name(tc)
        args = _tool_args(tc)
        signature = _tool_signature(tc)
        count = int(counts.get(name, 0))

        signatures.add(signature)
        counts[name] = count + 1
        tool_state = _tool_message_for(tc)
        if tool_state is None:
            result_ok = {"ok": False, "error": f"exécution impossible pour {name}"}
            tool_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", "call-0"),
                    "name": name,
                    "content": json.dumps(result_ok, ensure_ascii=False),
                }
            )
            state["events"].append(
                {
                    "type": "tool",
                    "skill": name,
                    "args": args,
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

        tool_result = tool_state["_event"].get("result") or {}
        if name == "search_knowledge" and not tool_result.get("entries"):
            _disable_tool(state, name)
        elif name == "list_research_results" and not tool_result.get("results"):
            _disable_tool(state, name)

    state["messages"].append(
        {
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": result.tool_calls,
        }
    )
    state["messages"].extend(tool_msgs)
    if any(
        m.get("role") == "user" and isinstance(m.get("content"), list)
        for m in state["messages"]
    ):
        state["messages"] = _textify_user_messages(state["messages"])
    return True


def _next_retry_fields() -> dict:
    retry_in = next_retry_in()
    return {
        "provider_retry_in_s": round(retry_in, 1),
        "provider_retry_in_human": human_delay(retry_in) if retry_in else "",
    }


def _live_turn(history: list[dict], thinking: bool = False) -> Iterator[dict]:
    """Un tour de chat en streaming, identique sur le plan logique à `handle_chat`.

    Produit des événements `{type: "token", content, provider, model, first}`
    puis UN événement final `{type: "done", reply, thinking, provider, model, events, ...}`.
    """
    state = _build_state(history, thinking=thinking)
    history_n = len(history)
    first_token = True

    for iteration in range(MAX_TOOL_ITERATIONS):
        result: ProviderResult | None = None
        provider_name = ""
        model = ""
        for ev in stream_with_failover(state["messages"], state["tools"]):
            if ev.get("type") == "token" and isinstance(ev.get("content"), str):
                yield {
                    "type": "token",
                    "content": ev["content"],
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
            reply = "(réponse vide)"
            done = _finalize_done(state, reply, history_n)
            done.update({"type": "done", "streamed": True})
            yield done
            return

        state["provider"] = provider_name
        state["model"] = model

        if result.tool_calls:
            _run_tool_turn(state, result)
            continue

        # --- Tour vision (images dans l'historique) -------------------------
        if any(
            m.get("role") == "user" and isinstance(m.get("content"), list)
            for m in history
        ):
            commentary = _last_user_text(history).strip()
            if state["provider"] == "demo-local":
                reply = (
                    "Je suis en mode démo local (aucun moteur configuré) : je ne peux pas "
                    "voir les images. Renseigne `MISTRAL_API_KEY` dans `.env` pour activer "
                    "la vision — `ministral-8b-latest` est multimodal."
                )
            else:
                reply = _display_text(result.content, commentary)
            done = _finalize_done(state, reply, history_n)
            done.update({"type": "done", "streamed": True})
            yield done
            return

        # --- Réponse finale -------------------------------------------------
        reply = result.content or "(réponse vide)"
        done = _finalize_done(state, reply, history_n)
        done.update({"type": "done", "streamed": True})
        yield done
        return

    # Synthèse finale sans outils si fin d'itérations
    forced_result: ProviderResult | None = None
    for ev in stream_with_failover(state["messages"], []):
        if ev.get("type") == "token" and isinstance(ev.get("content"), str):
            yield {
                "type": "token",
                "content": ev["content"],
                "provider": ev.get("provider", ""),
                "model": ev.get("model", ""),
                "first": first_token,
            }
            first_token = False
            continue
        if ev.get("type") == "result":
            forced_result = ev.get("result")
            _note_outcome(state, ev)

    forced_reply = (
        forced_result.content
        if forced_result and forced_result.content
        else _force_final_answer(state)
    )
    reply = forced_reply if forced_reply is not None else "(réponse vide)"
    done = _finalize_done(state, reply, history_n)
    done.update({"type": "done", "streamed": True})
    yield done


def _finalize_done(state: dict, reply: str, history_n: int, extra: dict | None = None) -> dict:
    """Construit l'événement final `done` (réflexion démo comprise)."""
    events = list(state["events"])
    clean_reply, extracted_thinking = _extract_thinking(reply)
    final_reply = clean_reply if clean_reply else reply

    if state["provider"] == "demo-local" and _demo_needs_reflection(
        state["user_text"], state["system"], final_reply
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
        "reply": final_reply,
        "thinking": extracted_thinking,
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


def handle_chat(history: list[dict], thinking: bool = False) -> dict:
    """Traiter une conversation (l'ensemble du historique est envoyé par le site).

    Retourne : { reply, thinking, provider, events: [{type: tool|prompt_update, ...}], system_assembled: bool }
    """
    state = _build_state(history, thinking=thinking)
    history_n = len(history)

    for iteration in range(MAX_TOOL_ITERATIONS):
        outcome = chat_with_failover(state["messages"], state["tools"])
        _note_outcome(state, outcome)
        result = outcome.result
        state["provider"] = result.provider or outcome.provider.name
        state["model"] = getattr(result, "model", "") or ""

        if result.tool_calls:
            _run_tool_turn(state, result)
            continue

        if any(
            m.get("role") == "user" and isinstance(m.get("content"), list)
            for m in history
        ):
            commentary = _last_user_text(history).strip()
            if state["provider"] == "demo-local":
                reply = (
                    "Je suis en mode démo local (aucun moteur configuré) : je ne peux pas "
                    "voir les images. Renseigne `MISTRAL_API_KEY` dans `.env` pour activer "
                    "la vision — `ministral-8b-latest` est multimodal."
                )
            else:
                reply = _display_text(result.content, commentary)
            return _finalize_done(state, reply, history_n)

        reply = result.content or "(réponse vide)"
        return _finalize_done(state, reply, history_n)

    forced_reply = _force_final_answer(state)
    reply = forced_reply if forced_reply is not None else "(réponse vide)"
    return _finalize_done(state, reply, history_n)


def handle_chat_stream(history: list[dict], thinking: bool = False) -> Iterator[dict]:
    """Comme `handle_chat`, mais la réponse finale est diffusée en streaming (SSE)."""
    yield from _live_turn(history, thinking=thinking)
