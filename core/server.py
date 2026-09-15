"""Serveur du projet AI-improves-itself.

Sert :
- le site statique (site/) à la racine,
- l'API du cœur IA (/api/*) : chat, prompt système, skills, /request,
  /colab (recherche), /data (base de connaissances).

Démarrage (depuis la racine du repo) :
    python core/server.py            # ou : uvicorn core.server:app --port 8000
"""
from __future__ import annotations

import os
import sys
from typing import Any

# Permet `python core/server.py` (commande documentée dans le README) : la racine
# du repo doit être importable pour charger le paquet `core.*`.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from core import store as store_module  # noqa: E402
from core.ai.chat import handle_chat  # noqa: E402
from core.ai.config import env  # noqa: E402
from core.ai import providers  # noqa: E402
from core.prompt_system import registry  # noqa: E402
from core.research import service as research  # noqa: E402
from core.skills import manager as skills_manager  # noqa: E402

SITE_DIR = os.path.join(REPO_ROOT, "site")
COLAB_DIR = os.path.join(REPO_ROOT, "colab")

app = FastAPI(
    title="AI-improves-itself",
    description="Un projet de recherche : une IA qui s'améliore d'elle-même (prompt versionné, skills, recherche web).",
    version="0.1.0",
)

# ------------------------------------------------------------------ API ----
class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., description="Historique complet [{role, content}]")


class PromptEditRequest(BaseModel):
    new_content: str
    reason: str = "édition manuelle"
    scope: str = "main"


class RequestItem(BaseModel):
    title: str
    description: str = ""
    type: str = "other"
    from_role: str = "human"  # 'ai' | 'human'


class ResearchTask(BaseModel):
    kind: str = "search"  # search | fetch | note
    target: str
    reason: str = ""
    by: str = "human"


class ResearchResult(BaseModel):
    kind: str = "note"
    data: dict[str, Any]
    task_id: str | None = None


@app.get("/api/status")
def status() -> dict:
    s = store_module.get_store()
    main = registry.get_current("main")
    # `health_report()` ne fait AUCUN appel réseau : il lit l'état des moteurs
    # (qui est au repos, pourquoi, dans combien de temps il est re-testé).
    health = providers.health_report()
    provider_name = providers.primary_provider_name()
    return {
        "primary_provider": provider_name,
        "model": health["limits"].get(provider_name, {}).get("model", ""),
        "demo_mode": provider_name == "demo-local",
        "provider_errors": health["errors"],
        "provider_retry_in_s": health["retry_in_s"],
        "provider_retry_in_human": health["retry_in_human"],
        "provider": health,
        "prompt_main_version": main.get("version"),
        "prompt_updated_by": main.get("updated_by"),
        "prompts": [
            {"id": p["id"], "scope": p.get("scope"), "version": p.get("version")}
            for p in registry.load_all().values()
        ],
        "counts": {
            "dev_requests": len(s.list("dev_requests")),
            "research_tasks": len(s.list("research_tasks")),
            "research_results": len(s.list("research_results")),
            "knowledge": len(s.list("knowledge", default=_knowledge_seed())),
        },
    }


@app.post("/api/providers/retest")
def retest_providers(payload: dict | None = None) -> dict:
    """Re-tester la chaîne de providers à la demande (bouton « retester » du site).

    `force=true` réveille aussi les moteurs au repos : utile après avoir changé
    une clé dans `.env`, mais ça consomme un appel par provider — sur un tier
    gratuit à 50 requêtes/jour (OpenRouter), à ne pas spammer.
    """
    force = bool((payload or {}).get("force"))
    report = providers.ping_chain(force=force)
    providers.invalidate_provider_cache()
    health = providers.health_report()
    return {
        "ok": True,
        "ping": report,
        "active": health["active"],
        "errors": health["errors"],
        "retry_in_human": health["retry_in_human"],
    }


def _knowledge_seed() -> list[dict]:
    import json

    path = os.path.join(REPO_ROOT, "core", "data", "knowledge.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    if not req.messages:
        raise HTTPException(400, "messages vide")
    return handle_chat(req.messages)


@app.get("/api/prompt-system")
def prompt_system() -> dict:
    return {"prompts": list(registry.load_all().values())}


@app.post("/api/prompt-system/{scope}")
def edit_prompt(scope: str, req: PromptEditRequest) -> dict:
    """Édition humaine du prompt système (même versionnage que l'IA)."""
    try:
        prompt = registry.apply_modification(
            scope, req.new_content, req.reason or "édition manuelle", author="human", trigger="manuel"
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "scope": scope, "version": prompt["version"]}


@app.get("/api/skills")
def skills() -> dict:
    return {"skills": skills_manager.list_skills()}


@app.get("/api/requests")
def requests_list() -> dict:
    items = store_module.get_store().list("dev_requests")
    return {"requests": sorted(items, key=lambda r: str(r.get("created_at", "")), reverse=True)}


@app.post("/api/requests")
def requests_add(req: RequestItem) -> dict:
    item = store_module.get_store().add(
        "dev_requests",
        {
            "title": req.title[:140],
            "description": req.description,
            "type": req.type,
            "from_role": req.from_role,
            "status": "open",
        },
    )
    return {"ok": True, "id": item.get("id")}


@app.get("/api/research/tasks")
def research_tasks() -> dict:
    items = store_module.get_store().list("research_tasks")
    return {"tasks": sorted(items, key=lambda r: str(r.get("created_at", "")), reverse=True)}


@app.post("/api/research/tasks")
def research_task_add(req: ResearchTask) -> dict:
    try:
        item = research.create_task(req.kind, req.target, req.reason, by=req.by)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "id": item.get("id")}


@app.get("/api/research/results")
def research_results() -> dict:
    items = store_module.get_store().list("research_results")
    return {"results": sorted(items, key=lambda r: str(r.get("created_at", "")), reverse=True)}


@app.post("/api/research/results")
def research_result_add(req: ResearchResult) -> dict:
    """Point d'entrée utilisé par le notebook Colab (et par le service Chromium)."""
    item = research.add_result(req.kind, req.data, task_id=req.task_id)
    return {"ok": True, "id": item.get("id")}


def _safe_int(value: Any, default: int, lo: int, hi: int) -> int:
    """Interprète une valeur int tolérante (JSON), bornée à [lo, hi]."""
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


@app.post("/api/research/scrape")
def research_scrape(payload: dict) -> dict:
    """Scraper une URL via le service Chromium (déployé sur Render)."""
    url = str(payload.get("url", "")).strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "url invalide")
    wait_ms = _safe_int(payload.get("wait_ms", 2000), 2000, 0, 15000)
    max_chars = _safe_int(payload.get("max_chars", 12000), 12000, 200, 60000)
    return research.scrape_via_service(url, wait_ms, max_chars)


@app.get("/api/data/entries")
def data_entries() -> dict:
    s = store_module.get_store()
    items = s.list("knowledge", default=_knowledge_seed())
    return {"entries": items, "count": len(items)}


# ------------------------------------------------------------- Static ----
app.mount("/colab-notebook", StaticFiles(directory=COLAB_DIR, html=True), name="colab-notebook")
app.mount("/", StaticFiles(directory=SITE_DIR, html=True), name="site")


if __name__ == "__main__":
    import uvicorn

    # `app` directement (aucun re-import par chemin de module → robuste quelle
    # que soit la façon dont le script est lancé).
    uvicorn.run(app, host="0.0.0.0", port=int(env("PORT", "8000") or 8000), reload=False)
