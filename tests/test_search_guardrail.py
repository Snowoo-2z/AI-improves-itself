"""Régressions de la recherche pertinente et de la boucle d'outils.

Lancer : python tests/test_search_guardrail.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core import store as store_module  # noqa: E402
from core.ai import chat as chat_module  # noqa: E402
from core.ai.providers import FailoverOutcome, ProviderResult  # noqa: E402
from core.skills import manager as skills_manager  # noqa: E402


PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(label if condition else f"{label} {detail}".strip())
    print(f"  {'✅' if condition else '❌'} {label}{(' ' + detail) if not condition and detail else ''}")


print("[1] La recherche ne confond plus « modèle OpenAI » et Mistral")
fixture = [
    {
        "title": "Mistral AI",
        "category": "ia",
        "date": "2023-09-01",
        "summary": "Modèles Mistral Small et Medium.",
    },
    {
        "title": "OpenAI GPT",
        "category": "ia",
        "date": "2025-01-01",
        "summary": "Modèle OpenAI de test.",
    },
]
with mock.patch.object(skills_manager, "_load_knowledge", return_value=fixture):
    miss = skills_manager.execute("search_knowledge", {"query": "modèle OpenAI", "use_date": True})
    hit = skills_manager.execute("search_knowledge", {"query": "modèle Mistral", "use_date": True})
with mock.patch.object(skills_manager, "_load_knowledge", return_value=fixture[:1]):
    no_openai = skills_manager.execute("search_knowledge", {"query": "modèle OpenAI", "use_date": True})

check("une requête OpenAI ne renvoie pas Mistral", miss["entries"][0]["title"] == "OpenAI GPT")
check("la pertinence exige le sujet explicite", all("Mistral" not in e["title"] for e in miss["entries"]))
check("sans entrée OpenAI, le résultat est vide", no_openai["entries"] == [])
check("une requête Mistral reste trouvable", hit["entries"][0]["title"] == "Mistral AI")


print("[2] Une recherche locale vide ne redémarre pas une rafale infinie")

def tool_call(query: str, call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "arguments": json.dumps({"query": query, "use_date": True}),
        },
    }


queue = [
    ProviderResult(content="", tool_calls=[tool_call("modèle OpenAI", "s1")], provider="fake"),
    ProviderResult(content="", tool_calls=[tool_call("modèle OpenAI le plus récent", "s2")], provider="fake"),
    ProviderResult(content="Je ne peux pas confirmer ce modèle sans source web.", provider="fake"),
]
calls: list[list[dict]] = []


def fake_failover(messages, tools, **kwargs):  # noqa: ANN001, ANN003
    calls.append(tools)
    return FailoverOutcome(queue.pop(0), SimpleNamespace(name="fake"), [], [])

old_data_dir = store_module.DATA_DIR
old_chat = chat_module.chat_with_failover
try:
    store_module.DATA_DIR = tempfile.mkdtemp(prefix="search-guardrail-")
    store_module.reset_store_cache()
    state = chat_module._build_state([{"role": "user", "content": "Compare ces recherches."}])
    parallel = ProviderResult(
        content="",
        tool_calls=[
            tool_call("modèle OpenAI", "p1"),
            tool_call("modèle GPT", "p2"),
        ],
        provider="fake",
    )
    chat_module._run_tool_turn(state, parallel)
    parallel_events = [e for e in state["events"] if e.get("type") == "tool"]
    check(
        "deux recherches de lecture seule sont exécutées dans la même réponse",
        len(parallel_events) == 2 and not any(e.get("guardrail") for e in parallel_events),
    )
    with mock.patch.object(chat_module, "chat_with_failover", side_effect=fake_failover):
        out = chat_module.handle_chat([{"role": "user", "content": "Quel est le dernier modèle OpenAI ?"}])
finally:
    chat_module.chat_with_failover = old_chat
    store_module.DATA_DIR = old_data_dir
    store_module.reset_store_cache()

check("la réponse finale est délivrée", out["reply"] == "Je ne peux pas confirmer ce modèle sans source web.")
check("deux recherches maximum puis réponse", len(calls) == 3, f"{len(calls)} appels")
check("le garde-fou de boucle dure n'est pas déclenché", "announce_slack" not in out)
check(
    "la skill de recherche est retirée après résultat vide",
    len(calls) >= 2
    and not any((t.get("function") or {}).get("name") == "search_knowledge" for t in (calls[-1] or [])),
)

print("[3] Trop de tours de lecture force une synthèse sans nouvel outil")
force_queue = [
    ProviderResult(content="", tool_calls=[tool_call(f"f{i}", f"requête {i}")], provider="fake")
    for i in range(4)
]
force_queue.append(ProviderResult(content="Synthèse forcée.", provider="fake"))
old_data_dir = store_module.DATA_DIR
old_chat = chat_module.chat_with_failover
try:
    store_module.DATA_DIR = tempfile.mkdtemp(prefix="search-force-")
    store_module.reset_store_cache()

    def force_failover(messages, tools, **kwargs):  # noqa: ANN001, ANN003
        return FailoverOutcome(force_queue.pop(0), SimpleNamespace(name="fake"), [], [])

    with mock.patch.object(chat_module, "chat_with_failover", side_effect=force_failover):
        forced = chat_module.handle_chat([{"role": "user", "content": "Compare les sources."}])
finally:
    chat_module.chat_with_failover = old_chat
    store_module.DATA_DIR = old_data_dir
    store_module.reset_store_cache()

check("une synthèse finale est délivrée après plusieurs recherches", forced["reply"] == "Synthèse forcée.")
check("la synthèse forcée ne relance aucun outil", not forced["reply"].startswith("J'ai enchaîné trop"))

print(f"RÉSULTAT : {len(PASSED)} OK, {len(FAILED)} en échec")
if FAILED:
    for item in FAILED:
        print("  ✗ " + item)
    raise SystemExit(1)
