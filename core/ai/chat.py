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
    _display_text,
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
#: Garde-fou des appels groupés : les lectures sans effet de bord peuvent être
#: regroupées pour comparer plusieurs résultats. Les actions d'écriture ou de
#: modification restent séquentielles afin d'éviter les rafales coûteuses et
#: les effets de bord. Tout appel refusé reçoit quand même une réponse `tool`
#: (le protocole OpenAI exige une réponse par `tool_call.id`).
MAX_PARALLEL_TOOL_CALLS = 1
#: Les recherches et lectures sont sans effet de bord : plusieurs peuvent être
#: groupées dans une seule réponse pour comparer des formulations. Les outils
#: d'écriture restent soumis à MAX_PARALLEL_TOOL_CALLS.
MAX_PARALLEL_READ_ONLY_CALLS = 3
READ_ONLY_PARALLEL_SKILLS = {"search_knowledge", "list_research_results"}
#: Même en séquentiel, on borne une skill par message utilisateur. Cette limite
#: évite une boucle LLM↔outil sans empêcher quelques recherches complémentaires.
MAX_TOOL_CALLS_PER_SKILL = 3

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


def _announce_excess_iterations(last_user_index: int, iterations: int, max_user: int) -> dict:
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
                f"La boucle LLM↔outils a passé {iterations} tours (limite {max_user}) sur le dernier "
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
        "last_user_index": last_user_index,
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


def _parallel_tool_refusal(tc: dict, position: int, kept: str) -> dict:
    """Refus d'un appel d'outil groupé (au-delà du 1er de la réponse).

    Le protocole OpenAI exige UNE réponse `tool` par `tool_call.id` : on ne peut
    pas ignorer l'appel — on le refuse explicitement, avec le mode d'emploi
    (rejouer SEUL l'outil au prochain tour). La clé `guardrail` permet au front
    d'afficher le refus comme un garde-fou plutôt qu'une erreur de skill.
    """
    name = tc.get("function", {}).get("name", "")
    return {
        "ok": False,
        "error": (
            "Appel d'outil refusé (garde-fou : UN SEUL outil exécuté par réponse, "
            "jamais d'appels groupés). "
            f"Cette réponse a exécuté « {kept} » ; « {name} » arrivait en position {position}. "
            "Si tu en as encore besoin, relance cet outil SEUL dans ta prochaine réponse, "
            "attends son retour, puis enchaîne."
        ),
        "guardrail": "one_tool_per_turn",
    }


def _parallel_read_limit_refusal(tc: dict, position: int) -> dict:
    """Refus lisible au-delà du nombre de lectures regroupables."""
    name = _tool_name(tc)
    return {
        "ok": False,
        "error": (
            f"Lecture « {name} » refusée en position {position} : maximum "
            f"{MAX_PARALLEL_READ_ONLY_CALLS} lectures dans une même réponse. "
            "Synthétise les résultats déjà reçus avant de poursuivre."
        ),
        "guardrail": "parallel_read_limit",
    }


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
    """Retire un outil devenu inutile pour la suite du même message.

    Le provider reçoit réellement la liste réduite : il ne peut donc pas
    reformuler à l'infini une recherche vide. Les autres outils restent
    disponibles (par exemple `add_research_task` pour aller chercher le sujet
    sur le web).
    """
    if not name:
        return
    state.setdefault("disabled_tools", set()).add(name)
    state["tools"] = [
        tool
        for tool in state.get("tools", [])
        if (tool.get("function") or {}).get("name") != name
    ]


def _tool_loop_refusal(name: str, reason: str) -> dict:
    return {
        "ok": False,
        "error": (
            f"Appel de {name or 'cet outil'} interrompu par le garde-fou anti-boucle : {reason} "
            "Réponds avec les informations déjà reçues, ou utilise un autre outil utile."
        ),
        "guardrail": "tool_loop",
    }


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


def _force_final_read_only_answer(state: dict) -> str | None:
    """Demande une synthèse sans outils après trop de lectures successives.

    Ce dernier appel ne peut plus relancer une recherche : même un modèle qui
    ignore la consigne de regroupement doit donc terminer par du texte plutôt
    que tomber sur le message « trop d'outils » affiché à l'utilisateur.
    """
    try:
        outcome = chat_with_failover(state["messages"], [])
    except Exception:  # noqa: BLE001 — le garde-fou final ne doit jamais bloquer
        return None
    _note_outcome(state, outcome)
    result = outcome.result
    state["provider"] = result.provider or outcome.provider.name
    state["model"] = getattr(result, "model", "") or ""
    if result.tool_calls:
        return None
    return result.content or "(réponse vide)"


def _append_refused_tool(state: dict, tool_msgs: list[dict], tc: dict, refusal: dict) -> None:
    name = _tool_name(tc)
    args = _tool_args(tc)
    tool_msgs.append(
        {
            "role": "tool",
            "tool_call_id": tc.get("id", "call-0"),
            "name": name,
            "content": json.dumps(refusal, ensure_ascii=False),
        }
    )
    state["events"].append(
        {
            "type": "tool",
            "skill": name,
            "args": args,
            "result": refusal,
            "guardrail": refusal.get("guardrail"),
        }
    )


def _run_tool_turn(state: dict, result: ProviderResult) -> bool:
    """Exécute les tool_calls d'un résultat et alimente `messages` + `events`.

    Ordre OpenAI attendu : [assistant(tool_calls), tool(call_1), tool(call_2), …].
    On exécute donc d'abord les outils, puis on insère le message assistant
    avant les retours `tool`. Un outil refusé (`ok=False`) reçoit un retour
    d'échec plutôt que rien, pour que l'IA rebondisse au lieu de réitérer.

    Garde-fou : une réponse composée uniquement de lectures (`search_knowledge`
    ou `list_research_results`) peut contenir jusqu'à
    `MAX_PARALLEL_READ_ONLY_CALLS` appels. Dès qu'une action d'écriture est
    présente, seuls les `MAX_PARALLEL_TOOL_CALLS` premiers appels sont exécutés ;
    chaque appel refusé reçoit tout de même une réponse `tool`, protocole
    OpenAI oblige.
    """
    tool_calls = list(result.tool_calls or [])
    kept_name = _tool_name(tool_calls[0]) if tool_calls else ""
    # Une rafale entièrement composée de lectures est sûre et utile pour
    # comparer plusieurs requêtes. Dès qu'une écriture est mélangée, on revient
    # à la règle stricte : une seule action d'état par réponse.
    read_only_batch = bool(tool_calls) and all(
        _tool_name(tc) in READ_ONLY_PARALLEL_SKILLS for tc in tool_calls
    )
    tool_msgs: list[dict] = []
    for position, tc in enumerate(tool_calls, start=1):
        name = _tool_name(tc)
        args = _tool_args(tc)
        if read_only_batch and position > MAX_PARALLEL_READ_ONLY_CALLS:
            refusal = _parallel_read_limit_refusal(tc, position)
            _append_refused_tool(state, tool_msgs, tc, refusal)
            continue
        if not read_only_batch and position > MAX_PARALLEL_TOOL_CALLS:
            refusal = _parallel_tool_refusal(tc, position, kept_name)
            _append_refused_tool(state, tool_msgs, tc, refusal)
            continue

        signature = _tool_signature(tc)
        signatures = state.setdefault("tool_call_signatures", set())
        counts = state.setdefault("tool_call_counts", {})
        count = int(counts.get(name, 0))
        if signature in signatures:
            refusal = _tool_loop_refusal(name, "cet appel identique a déjà été exécuté")
            _append_refused_tool(state, tool_msgs, tc, refusal)
            _disable_tool(state, name)
            continue
        if count >= MAX_TOOL_CALLS_PER_SKILL:
            refusal = _tool_loop_refusal(name, "cette skill a déjà été appelée trop souvent")
            _append_refused_tool(state, tool_msgs, tc, refusal)
            _disable_tool(state, name)
            continue

        signatures.add(signature)
        counts[name] = count + 1
        tool_state = _tool_message_for(tc)
        if tool_state is None:
            result_ok = {"ok": False, "error": "exécution refusée (skill inconnue ou échec)"}
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
        # Un résultat vide est une réponse définitive pour cette base locale.
        # Retirer seulement la recherche laisse encore `add_research_task`
        # disponible si le modèle comprend qu'il faut consulter le web.
        tool_result = tool_state["_event"].get("result") or {}
        if name == "search_knowledge" and not tool_result.get("entries"):
            _disable_tool(state, name)
    state["messages"].append(
        {
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": result.tool_calls,
        }
    )
    state["messages"].extend(tool_msgs)
    # Les blocs vision (image_url) ne traversent PAS la boucle d'outils : après
    # le 1er appel ils sont remplacés par du texte, pour que l'historique en
    # mémoire reste valide (le provider ne garde pas les images d'un tour à
    # l'autre). Le rendu affiché, lui, conserve les images (le front les garde).
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
                if _read_only_stretch(state, result):
                    forced_reply = _force_final_read_only_answer(state)
                    if forced_reply is not None:
                        extra = _announce_excess_iterations(
                            history_n - 1, last_user_stretch, TOOL_ITERATION_HARD_LIMIT
                        )
                        done = _finalize_done(state, forced_reply, history_n, extra)
                        done.update({"type": "done", "streamed": True})
                        yield done
                        return
                break
            _run_tool_turn(state, result)
            continue

        # --- Tour vision (images dans l'historique) -------------------------
        # Les modèles vision renvoient parfois un `content` vide (pas de texte)
        # même pour une vraie réponse visuelle : on reconstitue un texte
        # affichable, porté par le dernier message utilisateur. Le mode démo ne
        # peut pas décrire les images → il l'explique honnêtement.
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

    # Garde-fou : trop d'outils enchaînés sur le dernier message.
    extra = _announce_excess_iterations(history_n - 1, last_user_stretch, TOOL_ITERATION_HARD_LIMIT)
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
                if _read_only_stretch(state, result):
                    forced_reply = _force_final_read_only_answer(state)
                    if forced_reply is not None:
                        extra = _announce_excess_iterations(
                            history_n - 1, last_user_stretch, TOOL_ITERATION_HARD_LIMIT
                        )
                        return _finalize_done(state, forced_reply, history_n, extra)
                break
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

    extra = _announce_excess_iterations(history_n - 1, last_user_stretch, TOOL_ITERATION_HARD_LIMIT)
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
