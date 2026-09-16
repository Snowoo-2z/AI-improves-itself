"""Tests de l'exécution complète des outils (core/ai/chat.py).

Vérifie que les appels d'outils (simples, multiples ou groupés) sont tous exécutés
proprement sans refus artificiel de limite, dans le respect du protocole OpenAI.

Aucun appel réseau : les providers sont remplacés par des résultats scriptés,
et le store est isolé dans un dossier temporaire.

Lancer :  python tests/test_tool_guardrail.py     (aucune dépendance de test)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from types import SimpleNamespace

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("STORE_BACKEND", "local")

from core import store as store_module  # noqa: E402
from core.ai import chat as chat_module  # noqa: E402
from core.ai.providers import FailoverOutcome, ProviderResult  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


# ---------------------------------------------------------------------------
# Outillage : store temporaire + providers scriptés
# ---------------------------------------------------------------------------
_TMP = tempfile.mkdtemp(prefix="toolguard-")


def reset_store() -> None:
    """Store local dans un dossier temporaire (rien n'écrit dans core/data)."""
    store_module.DATA_DIR = _TMP  # noqa: SLF001 — test
    store_module.reset_store_cache()
    for name in ("knowledge", "dev_requests", "research_tasks", "research_results"):
        path = os.path.join(_TMP, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)


def tc(name: str, call_id: str, args: dict | None = None) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args or {}, ensure_ascii=False)},
    }


def scripted_failover(results: list[ProviderResult]):
    """Faussaire de `chat_with_failover` : rend les résultats dans l'ordre."""
    queue = list(results)
    provider_ns = SimpleNamespace(name="fake-provider")

    def fake(messages, tools, **kwargs):  # noqa: ANN001, ANN003
        assert queue, "le provider scripté a été appelé plus que prévu"
        result = queue.pop(0)
        return FailoverOutcome(result=result, provider=provider_ns, errors=[], attempts=[])

    return fake


def scripted_stream(results: list[ProviderResult]):
    """Faussaire de `stream_with_failover` : événements `result` scriptés."""
    queue = list(results)
    provider_ns = SimpleNamespace(name="fake-provider")

    def fake(messages, tools, **kwargs):  # noqa: ANN001, ANN003
        assert queue, "le provider scripté a été appelé plus que prévu"
        result = queue.pop(0)
        if not result.tool_calls and result.content:
            yield {"type": "token", "content": result.content, "provider": result.provider, "model": result.model}
        yield {"type": "result", "result": result, "provider": provider_ns, "errors": [], "attempts": []}

    return fake


def swap(name: str, replacement):
    original = getattr(chat_module, name)
    setattr(chat_module, name, replacement)
    return original


class restore:
    def __init__(self, pairs: list[tuple[str, object]]):
        self.pairs = pairs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for name, original in self.pairs:
            setattr(chat_module, name, original)
        return False


HISTORY = [{"role": "user", "content": "Fais la recherche puis mémorise le résultat."}]

# ---------------------------------------------------------------------------
print("\n[1] Réponse à 3 appels groupés : tous les 3 sont exécutés sans blocage")
reset_store()
r1 = ProviderResult(
    content="",
    tool_calls=[
        tc("search_knowledge", "c1", {"query": "Zelda"}),
        tc("add_knowledge", "c2", {"title": "X", "summary": "Y"}),
        tc("request_to_dev", "c3", {"title": "t", "description": "d"}),
    ],
    provider="fake-provider",
    model="fake-1",
)
r2 = ProviderResult(content="Réponse finale.", provider="fake-provider", model="fake-1")
with restore([("chat_with_failover", swap("chat_with_failover", scripted_failover([r1, r2])))]):
    out = chat_module.handle_chat(HISTORY)

check("réponse finale délivrée", out.get("reply") == "Réponse finale.", str(out.get("reply"))[:80])
tool_events = [e for e in out.get("events", []) if e.get("type") == "tool"]
check("3 événements outil tracés", len(tool_events) == 3, str([e.get("skill") for e in tool_events]))
execd = [e for e in tool_events if not e.get("guardrail")]
check("les 3 outils ont été exécutés", len(execd) == 3)
check("search_knowledge exécuté", any(e.get("skill") == "search_knowledge" for e in execd))
check("add_knowledge exécuté", any(e.get("skill") == "add_knowledge" for e in execd))
check("request_to_dev exécuté", any(e.get("skill") == "request_to_dev" for e in execd))

s = store_module.get_store()
check("add_knowledge persisté", len(s.list("knowledge")) == 1)
check("request_to_dev persisté", len(s.list("dev_requests")) == 1)

# ---------------------------------------------------------------------------
print("\n[2] Protocole OpenAI : chaque tool_call.id a sa réponse `tool`")
reset_store()
state = chat_module._build_state(HISTORY)  # noqa: SLF001
chat_module._run_tool_turn(state, r1)  # noqa: SLF001
messages = state["messages"]
assistant_msgs = [m for m in messages if m.get("role") == "assistant" and m.get("tool_calls")]
tool_msgs = [m for m in messages if m.get("role") == "tool"]
check("1 message assistant avec ses 3 tool_calls", len(assistant_msgs) == 1 and len(assistant_msgs[0]["tool_calls"]) == 3)
check(
    "3 messages `tool` en réponse, ids dans l'ordre [c1, c2, c3]",
    [m.get("tool_call_id") for m in tool_msgs] == ["c1", "c2", "c3"],
    str([m.get("tool_call_id") for m in tool_msgs]),
)
check(
    "les 3 réponses tool sont valides",
    all(json.loads(m["content"]).get("error") is None for m in tool_msgs),
)

# ---------------------------------------------------------------------------
print("\n[3] Chemin streamé (SSE) : exécution sans blocage")
reset_store()
s1 = ProviderResult(
    content="",
    tool_calls=[tc("list_research_results", "s1", {}), tc("add_knowledge", "s2", {"title": "X", "summary": "Y"})],
    provider="fake-provider",
    model="fake-1",
)
s2 = ProviderResult(content="Réponse streamée.", provider="fake-provider", model="fake-1")
with restore([("stream_with_failover", swap("stream_with_failover", scripted_stream([s1, s2])))]):
    events = list(chat_module.handle_chat_stream(HISTORY))

dones = [ev for ev in events if ev.get("type") == "done"]
check("un événement final `done` produit", len(dones) == 1)
done = dones[0] if dones else {}
check("réponse streamée délivrée", done.get("reply") == "Réponse streamée.", str(done.get("reply"))[:80])
stool = [e for e in done.get("events", []) if e.get("type") == "tool"]
check(
    "stream : les 2 outils exécutés sans blocage",
    len(stool) == 2
    and stool[0].get("skill") == "list_research_results"
    and stool[1].get("skill") == "add_knowledge",
    str([(e.get("skill"), e.get("guardrail")) for e in stool]),
)
check("add_knowledge exécuté en mode stream", len(store_module.get_store().list("knowledge")) == 1)

# ---------------------------------------------------------------------------
print("\n[4] Non-régression : un appel d'outil seul passe sans refus")
reset_store()
single = ProviderResult(content="", tool_calls=[tc("search_knowledge", "alone", {"query": "Zelda"})], provider="fake-provider")
final = ProviderResult(content="OK seul.", provider="fake-provider")
with restore([("chat_with_failover", swap("chat_with_failover", scripted_failover([single, final])))]):
    out = chat_module.handle_chat(HISTORY)
tool_events = [e for e in out.get("events", []) if e.get("type") == "tool"]
check(
    "appel unique exécuté, aucun refus",
    len(tool_events) == 1 and tool_events[0].get("skill") == "search_knowledge",
)
check("réponse finale OK", out.get("reply") == "OK seul.")

# ---------------------------------------------------------------------------
print("\n[5] Prompt système : outils documentés et disponibles")
reset_store()
state = chat_module._build_state([{"role": "user", "content": "Bonjour"}])  # noqa: SLF001
check(
    "le prompt assemblé présente les outils",
    "search_knowledge" in state["system"] and "modify_prompt_system" in state["system"],
    "outils absents du prompt",
)

print("\n" + "=" * 68)
print(f"RÉSULTAT : {len(PASSED)} vérifications OK, {len(FAILED)} en échec")
if FAILED:
    for item in FAILED:
        print("  ✗ " + item)
    sys.exit(1)
print("Tout est vert ✅")
