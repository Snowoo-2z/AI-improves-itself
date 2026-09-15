"""Script Colab — le « cerveau de recherche » que l'IA met à jour via ses tâches.

Mécanique :
1. L'IA ajoute des tâches (via la skill add_research_task / l'API du site) :
   kind = search (requête) | fetch (URL) | note (texte brut).
2. Vous ouvrez ce script dans Google Colab (ou le lancez en local) → `run_all()`.
   Si MAIN_SITE_URL est défini, les tâches sont AUSSI rapatriées depuis l'API
   du site (indispensable quand le backend est distant — GitHub sur Render :
   les tâches du chat ne sont plus dans le fichier local) puis fusionnées
   avec `tasks.json` (par id).
3. Chaque tâche `pending` est exécutée, marquée `done`/`failed` (localement +
   repoussé au site), et un résultat est écrit dans `results.json`.
4. Les nouveaux résultats sont poussés vers le site : POST /api/research/results —
   l'IA pourra ensuite les étudier (skill list_research_results).

Exécution en local (hors Colab) :
    pip install requests beautifulsoup4
    python colab/main.py
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "tasks.json")
RESULTS_PATH = os.path.join(HERE, "results.json")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MAIN_SITE_URL = os.environ.get("MAIN_SITE_URL", "")


# ------------------------------------------------------------ utilitaires ----
def _read(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return default


def _write(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _http_get(url: str, timeout: int = 30) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def _strip_html(html: str, max_chars: int = 8000) -> str:
    """Extraction de texte honnête (pas de dépendance lourde)."""
    text = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;|&apos;", "'", text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))) if 32 <= int(m.group(1)) < 0x10000 else " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()[:max_chars]


def _search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """Recherche DuckDuckGo (endpoint HTML, sans clé API)."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    status, html = _http_get(url)
    if status != 200:
        raise RuntimeError(f"HTTP {status} sur DuckDuckGo")
    out = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        link, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if "uddg=" in link:
            try:
                link = urllib.parse.unquote(re.search(r"uddg=([^&]+)", link).group(1))
            except (AttributeError, TypeError):
                pass
        out.append({"title": title, "url": link})
        if len(out) >= max_results:
            break
    return out


# ------------------------------------------------------------ tâches ----
def _run_search(task: dict) -> dict:
    results = _search_duckduckgo(task["target"])
    return {"kind": "search", "query": task["target"], "results": results, "error": None if results else "aucun résultat"}


def _run_fetch(task: dict) -> dict:
    status, html = _http_get(task["target"])
    text = _strip_html(html)
    return {"kind": "fetch", "url": task["target"], "http_status": status, "text": text}


def _run_note(task: dict) -> dict:
    return {"kind": "note", "content": task["target"]}


RUNNERS = {"search": _run_search, "fetch": _run_fetch, "note": _run_note}


# ------------------------------------------------------------ site (API) ----
def _pull_from_site() -> list[dict]:
    """Rapatrie les tâches depuis l'API (source de vérité à distance)."""
    if not MAIN_SITE_URL:
        return []
    try:
        status, body = _http_get(MAIN_SITE_URL.rstrip("/") + "/api/research/tasks", timeout=20)
        if status != 200:
            print(f"! tâches API inaccessibles (HTTP {status}) — fichier local seul.")
            return []
        items = json.loads(body).get("tasks", [])
        return items if isinstance(items, list) else []
    except Exception as exc:  # noqa: BLE001
        print(f"! tâches API inaccessibles ({exc}) — fichier local seul.")
        return []


def _push_status_to_site(task_id: str | None, status: str) -> None:
    """Repousse le statut d'une tâche (PATCH, best-effort)."""
    if not MAIN_SITE_URL or not task_id:
        return
    try:
        body = json.dumps({"status": status}).encode("utf-8")
        req = urllib.request.Request(
            MAIN_SITE_URL.rstrip("/") + f"/api/research/tasks/{task_id}",
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": UA},
            method="PATCH",
        )
        urllib.request.urlopen(req, timeout=20)
    except Exception as exc:  # noqa: BLE001
        print(f"! statut {status} non poussé (tâche {task_id}) : {exc}")


def _push_to_site(new_entries: list[dict]) -> None:
    if not MAIN_SITE_URL or not new_entries:
        return
    for res in new_entries:
        try:
            body = json.dumps(
                {"kind": res.get("kind", "note"), "data": res.get("data", {}), "task_id": res.get("task_id")}
            ).encode("utf-8")
            req = urllib.request.Request(
                MAIN_SITE_URL.rstrip("/") + "/api/research/results",
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": UA},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=20)
            print(f"→ résultat poussé au site (tâche {res.get('task_id')})")
        except Exception as exc:  # noqa: BLE001
            print(f"! impossible de pousser au site : {exc}")


# ------------------------------------------------------------ orquestration ----
def run_all(max_tasks: int | None = None) -> list[dict]:
    tasks = _read(TASKS_PATH, [])
    # Fusion avec les tâches distantes (par id) : sans ça, les tâches créées
    # via le chat sur Render (backend GitHub) seraient invisibles ici.
    for remote in _pull_from_site():
        if remote.get("id") and not any(t.get("id") == remote["id"] for t in tasks):
            tasks.append(remote)
    results = _read(RESULTS_PATH, [])
    done: list[dict] = []
    pending = [t for t in tasks if t.get("status") in ("pending", "processing")]
    if max_tasks:
        pending = pending[:max_tasks]
    for task in pending:
        task["status"] = "processing"
        runner = RUNNERS.get(task.get("kind"))
        if runner is None:
            task.update(status="failed", error=f"kind inconnu : {task.get('kind')}")
            _push_status_to_site(task.get("id"), "failed")
            _write(TASKS_PATH, tasks)
            continue
        try:
            data = runner(task)
            task.update(status="done", error=None)
            entry = {"task_id": task.get("id"), "kind": task.get("kind"), "data": data,
                     "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            results.append(entry)
            done.append(entry)
            _push_status_to_site(task.get("id"), "done")
        except Exception as exc:  # noqa: BLE001
            task.update(status="failed", error=str(exc))
            _push_status_to_site(task.get("id"), "failed")
        _write(TASKS_PATH, tasks)  # sauvegarde incrementale : pas de perte en cas de coupure
    _write(RESULTS_PATH, results)
    _push_to_site(done)
    return done


if __name__ == "__main__":
    n = run_all()
    print(f"\n{len(n)} tâche(s) exécutée(s). Résultats : {RESULTS_PATH}")
