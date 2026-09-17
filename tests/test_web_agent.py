"""Agent de recherche HTTP (sans navigateur) — tests hors réseau."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core import store as store_module  # noqa: E402
from core.research import agent as research_agent  # noqa: E402
from core.skills import manager as skills  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(label if condition else f"{label} {detail}".strip())
    print(f"  {'✅' if condition else '❌'} {label}{(' ' + detail) if not condition and detail else ''}")


print("[1] compact_hits réduit search/fetch")
search_data = {
    "kind": "search",
    "engine": "ddg-html",
    "results": [
        {"title": "Claude Fable 5.1", "url": "https://anthropic.com/fable", "snippet": "sortie 10 sept 2026", "text": "Fable 5.1 est le dernier modèle."},
        {"title": "Mythos 5", "url": "https://anthropic.com/mythos", "snippet": "juin 2026"},
    ],
}
hits = research_agent.compact_hits(search_data)
check("2 hits", len(hits) == 2)
check("extrait présent", "Fable" in hits[0]["excerpt"])
fetch_data = {"kind": "fetch", "title": "Page", "url": "https://x.test", "text": "hello " * 20, "error": "page vide après extraction (JS lourd ?)"}
fh = research_agent.compact_hits(fetch_data)
check("fetch js_heavy", fh[0]["js_heavy"] is True)

print("[2] web_agent hors-ligne refuse le réseau")
old = os.environ.get("AIIS_AGENT_OFFLINE")
os.environ["AIIS_AGENT_OFFLINE"] = "1"
try:
    res = skills.execute("web_agent", {"kind": "search", "target": "anthropic", "say": "je cherche"})
finally:
    if old is None:
        os.environ.pop("AIIS_AGENT_OFFLINE", None)
    else:
        os.environ["AIIS_AGENT_OFFLINE"] = old
check("refus hors-ligne", res.get("ok") is False and "hors-ligne" in res.get("error", ""))

print("[3] web_agent exécute + persiste (moteur mocké)")
fake = {
    "kind": "search",
    "query": "dernier modèle anthropic",
    "engine": "ddg-html",
    "results": [
        {"title": "Claude Fable 5.1", "url": "https://www.anthropic.com/news/fable-5-1", "snippet": "10 septembre 2026"},
    ],
}
tmp = tempfile.mkdtemp(prefix="web-agent-")
old_dir = store_module.DATA_DIR
store_module.DATA_DIR = tmp
store_module.reset_store_cache()
try:
    with mock.patch.object(research_agent, "network_allowed", return_value=True), mock.patch.object(
        research_agent, "run_step", return_value={"ok": True, **fake, "hits": research_agent.compact_hits(fake), "count": 1, "browser": "http-only", "next_hint": "fetch", "data": fake}
    ):
        out = skills.execute("web_agent", {"kind": "search", "target": "dernier modèle anthropic", "say": "je cherche Fable"})
    check("ok", out.get("ok") is True, json.dumps(out)[:200])
    check("say visible", out.get("say") == "je cherche Fable")
    check("hit Fable", out["hits"][0]["title"] == "Claude Fable 5.1")
    check("skill listée", any(s["id"] == "web_agent" for s in skills.list_skills()))
finally:
    store_module.DATA_DIR = old_dir
    store_module.reset_store_cache()

print(f"RÉSULTAT : {len(PASSED)} OK, {len(FAILED)} en échec")
if FAILED:
    for item in FAILED:
        print("  ✗ " + item)
    raise SystemExit(1)
