"""Pipeline de recherche : tâches → exécution (Chromium/Colab) → résultats.

- `create_task` / `add_result` : utilisés par le serveur API (et le notebook Colab).
- `scrape_via_service` : client vers le service Chromium déployé (Render).
- `study_result` (phase 2) : l'IA étudie le résultat et décide si la base de
  connaissances doit être mise à jour (aujourd'hui : stockage + exposition).
"""
from __future__ import annotations

from core import store as store_module
from core.ai.config import env


def create_task(kind: str, target: str, reason: str = "", by: str = "human") -> dict:
    if kind not in ("search", "fetch", "note"):
        raise ValueError("kind doit être 'search', 'fetch' ou 'note'")
    if not target:
        raise ValueError("target est requis")
    s = store_module.get_store()
    return s.add(
        "research_tasks",
        {"kind": kind, "target": target[:500], "reason": reason[:500], "by": by, "status": "pending"},
    )


def add_result(kind: str, data: dict, task_id: str | None = None) -> dict:
    s = store_module.get_store()
    # task_id est persisté DANS le résultat : la page /colab l'affiche pour
    # rattacher le résultat à sa tâche, et Supabase utilise la FK research_results.task_id.
    item = s.add(
        "research_results",
        {"kind": kind, "data": data, "task_id": task_id, "status": "done"},
    )
    if task_id:
        s.update("research_tasks", task_id, {"status": "done", "updated_at": _now_iso()})
    return item


def mark_task(task_id: str, status: str) -> dict | None:
    s = store_module.get_store()
    return s.update("research_tasks", task_id, {"status": status, "updated_at": _now_iso()})


def _now_iso() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def scrape_via_service(url: str, wait_ms: int = 2000, max_chars: int = 12000) -> dict:
    """Appeler le service Chromium (web service Render) pour scraper une URL."""
    import httpx

    base = (env("SCRAPER_SERVICE_URL") or "").rstrip("/")
    if not base:
        return {
            "ok": False,
            "error": "SCRAPER_SERVICE_URL non configuré dans .env (déployer services/scraper sur Render).",
        }
    try:
        r = httpx.post(
            f"{base}/scrape",
            json={"url": url, "wait_ms": wait_ms, "max_chars": max_chars},
            timeout=90,
        )
        r.raise_for_status()
        return {"ok": True, **r.json()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Erreur service de scraping : {exc}"}
