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

print("[4] Enchaînement mixte search_knowledge -> add_research_task -> réponse finale")
mixed_queue = [
    ProviderResult(content="", tool_calls=[tool_call("dernier modèle OpenAI", "m1")], provider="fake"),
    ProviderResult(
        content="",
        tool_calls=[
            {
                "id": "m2",
                "type": "function",
                "function": {
                    "name": "add_research_task",
                    "arguments": json.dumps({"kind": "deep", "target": "dernier modèle OpenAI 2026", "reason": "non trouvé"}),
                },
            }
        ],
        provider="fake",
    ),
    ProviderResult(content="Selon mes connaissances, le modèle le plus récent est GPT-4o / Astra GPT 6. Une recherche Colab a été programmée.", provider="fake"),
]
mixed_calls: list[list[dict]] = []

def mixed_failover(messages, tools, **kwargs):  # noqa: ANN001, ANN003
    mixed_calls.append(tools or [])
    return FailoverOutcome(mixed_queue.pop(0), SimpleNamespace(name="fake"), [], [])

old_data_dir = store_module.DATA_DIR
old_chat = chat_module.chat_with_failover
try:
    store_module.DATA_DIR = tempfile.mkdtemp(prefix="search-mixed-")
    store_module.reset_store_cache()
    with mock.patch.object(chat_module, "chat_with_failover", side_effect=mixed_failover):
        mixed_out = chat_module.handle_chat([{"role": "user", "content": "Quel est le dernier modèle d'OpenAI ?"}])
finally:
    chat_module.chat_with_failover = old_chat
    store_module.DATA_DIR = old_data_dir
    store_module.reset_store_cache()

check("la réponse finale de l'enchaînement mixte est délivrée", "Astra GPT 6" in mixed_out["reply"] or "GPT-4o" in mixed_out["reply"])
check("l'enchaînement mixte ne déclenche pas d'erreur", not mixed_out["reply"].startswith("J'ai enchaîné trop"))
check("la conversation a mené à son terme en 3 appels", len(mixed_calls) == 3)

print("[5] Boucle mixte saturée force la synthèse finale sans message d'interruption")
saturate_queue = [
    ProviderResult(content="", tool_calls=[tool_call("q1", "c1")], provider="fake"),
    ProviderResult(
        content="",
        tool_calls=[
            {
                "id": "c2",
                "type": "function",
                "function": {
                    "name": "add_research_task",
                    "arguments": json.dumps({"kind": "search", "target": "cible", "reason": "besoin"}),
                },
            }
        ],
        provider="fake",
    ),
    ProviderResult(
        content="",
        tool_calls=[
            {
                "id": "c3",
                "type": "function",
                "function": {
                    "name": "list_research_results",
                    "arguments": json.dumps({"limit": 1}),
                },
            }
        ],
        provider="fake",
    ),
    ProviderResult(content="", tool_calls=[tool_call("q4", "c4")], provider="fake"),
    ProviderResult(content="Synthèse finale après boucle mixte saturée.", provider="fake"),
]

old_data_dir = store_module.DATA_DIR
old_chat = chat_module.chat_with_failover
try:
    store_module.DATA_DIR = tempfile.mkdtemp(prefix="search-saturate-")
    store_module.reset_store_cache()

    def saturate_failover(messages, tools, **kwargs):  # noqa: ANN001, ANN003
        return FailoverOutcome(saturate_queue.pop(0), SimpleNamespace(name="fake"), [], [])

    with mock.patch.object(chat_module, "chat_with_failover", side_effect=saturate_failover):
        sat_out = chat_module.handle_chat([{"role": "user", "content": "Question complexe"}])
finally:
    chat_module.chat_with_failover = old_chat
    store_module.DATA_DIR = old_data_dir
    store_module.reset_store_cache()

check("la synthèse finale est délivrée sur boucle mixte", sat_out["reply"] == "Synthèse finale après boucle mixte saturée.")
check("la boucle mixte ne termine pas par l'erreur enchaîné trop d'outils", not sat_out["reply"].startswith("J'ai enchaîné trop"))

print("[6] La source (URL) compte dans la recherche + correspondance partielle signalée")
fixture_source = [
    {
        "title": "Claude Opus 4.5",
        "category": "ia",
        "date": "2026-09-10",
        "summary": "Nouveau modèle de raisonnement, plus rapide.",
        "source": "https://www.anthropic.com/news/claude-opus-4-5",
    },
    {
        "title": "Mistral AI",
        "category": "ia",
        "date": "2023-09-01",
        "summary": "Modèles Mistral Small et Medium.",
        "source": "https://mistral.ai",
    },
]
with mock.patch.object(skills_manager, "_load_knowledge", return_value=fixture_source):
    by_source = skills_manager.execute("search_knowledge", {"query": "dernier modèle anthropic"})
check(
    "une entrée est trouvée via le domaine de sa source (anthropic.com)",
    by_source["entries"][0]["title"] == "Claude Opus 4.5",
    json.dumps(by_source),
)
check("pas de flag partial quand la correspondance est complète", by_source.get("partial") is False)
check("l'entrée Mistral n'est pas confondue", all("Mistral" not in e["title"] for e in by_source["entries"]))

fixture_partial = [
    {"title": "Google Gemini 2", "category": "ia", "date": "2026-08-01",
     "summary": "Nouveau modèle de Google.", "source": "https://blog.google"},
    {"title": "Vision API", "category": "web", "date": "2026-07-01",
     "summary": "API d'analyse d'images.", "source": "https://example.com"},
]
with mock.patch.object(skills_manager, "_load_knowledge", return_value=fixture_partial):
    partial = skills_manager.execute("search_knowledge", {"query": "modèle vision google"})
check(
    "correspondance partielle renvoyée avec le flag partial",
    partial.get("partial") is True and len(partial["entries"]) >= 1,
    json.dumps(partial),
)
check("l'entrée la plus couverte arrive d'abord", partial["entries"][0]["title"] == "Google Gemini 2")
check("la note avertit que la correspondance est partielle", "PARTIELLE" in partial.get("note", ""))

with mock.patch.object(skills_manager, "_load_knowledge", return_value=[fixture_partial[1]]):
    still_empty = skills_manager.execute("search_knowledge", {"query": "modèle OpenAI"})
check("un seul terme absent → toujours vide (garde-fou historique inchangé)", still_empty["entries"] == [])

print("[7] « dernier modèle Anthropic » : date exacte, Mythos 5 n'est pas le dernier")
fixture_anth = [
    {
        "title": "Anthropic Mythos 5",
        "category": "ia",
        "date": "2026-06-23",
        "summary": "Mythos 5 existe, accès partiellement réautorisé.",
        "source": "seed",
    },
    {
        "title": "Anthropic Claude Fable 5.1",
        "category": "ia",
        "date": "2026-09-10",
        "summary": "Claude Fable 5.1 : dernier modèle Anthropic.",
        "source": "seed",
    },
]
with mock.patch.object(skills_manager, "_load_knowledge", return_value=fixture_anth):
    latest = skills_manager.execute(
        "search_knowledge", {"query": "modèle Anthropic", "use_date": True}
    )
    oldest_first = skills_manager.execute(
        "search_knowledge", {"query": "modèle Anthropic", "use_date": False}
    )
check(
    "use_date=true → Claude Fable 5.1 en premier (date 2026-09-10)",
    latest["entries"][0]["title"] == "Anthropic Claude Fable 5.1",
    json.dumps(latest),
)
check(
    "Mythos 5 reste listé mais plus ancien",
    any(e["title"] == "Anthropic Mythos 5" for e in latest["entries"])
    and latest["entries"][0]["date"] == "2026-09-10",
)
check("la source est renvoyée", "source" in latest["entries"][0])
check(
    "sans use_date les deux modèles restent trouvables",
    {e["title"] for e in oldest_first["entries"]}
    >= {"Anthropic Mythos 5", "Anthropic Claude Fable 5.1"},
)
check(
    "chronologie datée : Fable puis Mythos",
    [t["title"] for t in latest.get("timeline") or []][:2]
    == ["Anthropic Claude Fable 5.1", "Anthropic Mythos 5"],
    json.dumps(latest.get("timeline")),
)
check("chaque entrée datée a dated=true", all(e.get("dated") for e in latest["entries"]))

print("[8] Filtre date/année sur la recherche")
with mock.patch.object(skills_manager, "_load_knowledge", return_value=fixture_anth):
    june = skills_manager.execute(
        "search_knowledge", {"query": "Anthropic", "date": "2026-06-23"}
    )
    year = skills_manager.execute(
        "search_knowledge", {"query": "Anthropic", "date": "2026"}
    )
check("jour exact → uniquement Mythos 5", [e["title"] for e in june["entries"]] == ["Anthropic Mythos 5"], json.dumps(june))
check("année 2026 → les deux, Fable d'abord", year["entries"][0]["title"] == "Anthropic Claude Fable 5.1" and len(year["timeline"]) == 2)

print(f"RÉSULTAT : {len(PASSED)} OK, {len(FAILED)} en échec")
if FAILED:
    for item in FAILED:
        print("  ✗ " + item)
    raise SystemExit(1)
