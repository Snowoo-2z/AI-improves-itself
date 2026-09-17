"""Agent de recherche HTTP (pas de navigateur).

Colab ne peut pas piloter un « bon » navigateur (pas de JS). Le cœur exécute
donc la même cascade que `colab/main.py` (DDG HTML → DDG lite → Wikipédia,
fetch HTML + robots.txt) **tout de suite** dans le tour de chat.

Boucle agent :
  l'IA dit ce qu'elle fait (`say`) → le script cherche/lit → résultats
  compactés renvoyés → l'IA décide l'étape suivante (autre search, fetch URL,
  add_knowledge). Les pages JS-lourdes restent un cas Colab/`deep` asynchrone.
"""
from __future__ import annotations

import os
import sys
from typing import Any

from core.ai.config import REPO_ROOT

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _colab():
    from colab import main as colab_main

    return colab_main


def compact_hits(data: dict, limit: int = 5) -> list[dict]:
    """Réduit un résultat search/deep/fetch à ce que l'IA peut vraiment lire."""
    kind = str(data.get("kind") or "")
    hits: list[dict] = []
    if kind in ("search", "deep"):
        for it in (data.get("results") or [])[:limit]:
            if not isinstance(it, dict):
                continue
            text = str(it.get("text") or "")
            hits.append(
                {
                    "title": str(it.get("title") or "")[:180],
                    "url": str(it.get("url") or "")[:400],
                    "snippet": str(it.get("snippet") or "")[:280],
                    "excerpt": (" ".join(text.split())[:420] if text else ""),
                    "js_heavy": bool(it.get("fetch_error") or (not text and it.get("url"))),
                }
            )
    elif kind == "fetch":
        text = str(data.get("text") or "")
        hits.append(
            {
                "title": str(data.get("title") or "")[:180],
                "url": str(data.get("url") or data.get("requested_url") or "")[:400],
                "snippet": str(data.get("description") or "")[:280],
                "excerpt": " ".join(text.split())[:900],
                "js_heavy": bool(data.get("error") and "JS" in str(data.get("error"))),
            }
        )
    return hits


def run_step(kind: str, target: str, *, fetch_top: int = 1) -> dict[str, Any]:
    """Exécute UNE étape agent (search | fetch | deep). Sans navigateur."""
    kind = str(kind or "search").strip().lower()
    target = str(target or "").strip()
    if not target:
        return {"ok": False, "error": "target est requis (requête ou URL)."}
    if kind not in ("search", "fetch", "deep"):
        return {"ok": False, "error": f"kind inconnu : {kind} (search|fetch|deep)"}

    m = _colab()
    task = {"target": target, "kind": kind}
    if kind == "search":
        data = m.run_search(task, fetch_top=max(0, min(int(fetch_top or 1), 2)))
    elif kind == "fetch":
        data = m.run_fetch(task)
    else:
        data = m.run_deep(task, fetch_n=2)

    hits = compact_hits(data)
    js_heavy = any(h.get("js_heavy") for h in hits) or bool(data.get("error"))
    engine = data.get("engine") or data.get("http_status") or "http"
    next_hint = (
        "Page trop JS pour HTTP : programme un `add_research_task` kind=deep "
        "(Colab lira plus tard) OU fetch une URL plus simple (Wikipédia, blog)."
        if js_heavy and not any(h.get("excerpt") for h in hits)
        else "Si un titre colle, `web_agent kind=fetch` sur son URL ; sinon reformule la recherche."
    )
    return {
        "ok": True,
        "kind": kind,
        "target": target[:300],
        "engine": engine,
        "hits": hits,
        "count": len(hits),
        "browser": "http-only (pas de JS, comme Colab)",
        "error": data.get("error") or data.get("search_error"),
        "next_hint": next_hint,
        "data": data,
    }


# Désactive le fetch réseau dans les tests (CI / sandbox).
def network_allowed() -> bool:
    return os.environ.get("AIIS_AGENT_OFFLINE", "") not in ("1", "true", "yes")
