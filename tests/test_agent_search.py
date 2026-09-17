"""Recherche agentique Colab — hors réseau."""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from colab import agent_search as ag  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(label if condition else f"{label} {detail}".strip())
    print(f"  {'✅' if condition else '❌'} {label}{(' ' + detail) if not condition and detail else ''}")


print("[1] parse_next_action")
stop = ag.parse_next_action('{"done": true, "kind": "search", "target": "", "say": "assez"}')
check("stop", stop["done"] is True)
nxt = ag.parse_next_action('{"done": false, "kind": "fetch", "target": "https://x.test", "say": "je lis"}')
check("fetch", nxt["kind"] == "fetch" and nxt["target"].startswith("https://") and not nxt["done"])
check("json noyé", ag.parse_next_action("voici {\"done\": true, \"target\": \"\"}")["done"] is True)

print("[2] run_agent avec runner mocké")
calls = []


def runner(kind, target):
    calls.append((kind, target))
    return {
        "kind": kind,
        "engine": "fake",
        "results": [{"title": "Claude Fable 5.1", "url": "https://anthropic.com/fable", "snippet": "2026-09-10"}],
    }


def llm(_sys, _user):
    if len(calls) == 1:
        return '{"done": false, "kind": "fetch", "target": "https://anthropic.com/fable", "say": "je lis Fable"}'
    return '{"done": true, "kind": "", "target": "", "say": "terminé"}'


rep = ag.run_agent("dernier modèle Anthropic", max_steps=4, llm=llm, runner=runner, log=lambda *_a, **_k: None)
check("2 étapes", len(rep["steps"]) == 2, str(len(rep["steps"])))
check("1er search", calls[0][0] == "search")
check("2e fetch Fable", calls[1] == ("fetch", "https://anthropic.com/fable"))
check("hit daté dans l'étape 1", "Fable" in rep["steps"][0]["hits"][0]["title"])

print(f"RÉSULTAT : {len(PASSED)} OK, {len(FAILED)} en échec")
if FAILED:
    raise SystemExit(1)
