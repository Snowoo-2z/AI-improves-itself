"""Recherche agentique — 1 cellule Colab (copier-coller).

Pas de navigateur JS (Colab n'en a pas). Le script :

  1. demande une QUESTION (ou tire les tâches pending du site) ;
  2. dit ce qu'il fait (« je cherche … ») ;
  3. exécute HTTP (DDG → Wikipédia → fetch HTML, robots.txt) ;
  4. affiche les hits ; éventuellement Mistral choisit l'étape suivante
     (fetch une URL, autre search, stop) — max MAX_STEPS ;
  5. pousse les résultats au site (POST /api/research/results).

Colle ce fichier entier dans UNE cellule Colab → Run.
En local :  python colab/agent_search.py

Dépendances : stdlib. Si `colab/main.py` est importable, on réutilise sa
cascade ; sinon repli Wikipédia + fetch urllib.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCRIPT_VERSION = 1
MAIN_SITE_URL = os.environ.get("MAIN_SITE_URL", "https://aiis-core.onrender.com").rstrip("/")
MAX_STEPS = 4
PUSH_TO_SITE = True
MISTRAL_MODEL = "ministral-8b-latest"
MISTRAL_API_BASE = "https://api.mistral.ai/v1"
UA = "Mozilla/5.0 (compatible; AIIS-agent/1.0; +https://github.com/Snowoo-2z/AI-improves-itself)"
IS_COLAB = os.path.isdir("/content") and os.access("/content", os.W_OK)

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
if os.path.dirname(HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _http_get(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_json(method: str, url: str, payload: dict | None = None, timeout: int = 30) -> tuple[int, dict | None]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    heads = {"User-Agent": UA, "Accept": "application/json"}
    if payload is not None:
        heads["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=heads, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw.strip() else None
            return resp.status, data if isinstance(data, dict) else None
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8", errors="replace") or "null")
        except Exception:
            data = None
        return exc.code, data if isinstance(data, dict) else None


def wikipedia_search(query: str, lang: str = "fr", max_results: int = 5) -> list[dict]:
    api = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(query)}&format=json&srlimit={max_results}&srprop=snippet"
    )
    data = json.loads(_http_get(api, timeout=20))
    out = []
    for it in (data.get("query", {}).get("search", []) or [])[:max_results]:
        title = it.get("title", "")
        url = f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        snippet = (it.get("snippet") or "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
        out.append({"title": title, "url": url, "snippet": snippet[:400]})
    return out


def fallback_search(query: str, max_results: int = 5) -> dict:
    q = (query or "").strip()
    for lang in ("fr", "en"):
        try:
            found = wikipedia_search(q, lang=lang, max_results=max_results)
            if found:
                return {"results": found, "engine": f"wikipedia-{lang}", "query": q}
        except Exception as exc:  # noqa: BLE001
            last = str(exc)[:120]
            continue
    return {"results": [], "engine": "none", "query": q, "error": last if "last" in dir() else "aucun résultat"}


def _load_colab_main():
    try:
        from colab import main as m  # type: ignore

        return m
    except Exception:
        return None


def run_http_step(kind: str, target: str) -> dict:
    """Une étape HTTP (search|fetch|deep). Réutilise colab.main si possible."""
    m = _load_colab_main()
    task = {"target": target, "kind": kind}
    if m is not None:
        if kind == "fetch":
            data = m.run_fetch(task)
        elif kind == "deep":
            data = m.run_deep(task, fetch_n=2)
        else:
            data = m.run_search(task, fetch_top=1)
        return data
    if kind == "fetch":
        try:
            html = _http_get(target)
            return {"kind": "fetch", "url": target, "title": target, "text": html[:4000]}
        except Exception as exc:  # noqa: BLE001
            return {"kind": "fetch", "url": target, "error": str(exc)[:200], "text": ""}
    found = fallback_search(target)
    found["kind"] = kind
    return found


def compact_hits(data: dict, limit: int = 5) -> list[dict]:
    kind = str(data.get("kind") or "")
    hits: list[dict] = []
    if kind in ("search", "deep") or data.get("results"):
        for it in (data.get("results") or [])[:limit]:
            if not isinstance(it, dict):
                continue
            text = str(it.get("text") or "")
            hits.append(
                {
                    "title": str(it.get("title") or "")[:180],
                    "url": str(it.get("url") or "")[:400],
                    "snippet": str(it.get("snippet") or "")[:280],
                    "excerpt": " ".join(text.split())[:360] if text else "",
                }
            )
    elif data.get("url") or data.get("text"):
        hits.append(
            {
                "title": str(data.get("title") or "")[:180],
                "url": str(data.get("url") or "")[:400],
                "snippet": str(data.get("description") or "")[:280],
                "excerpt": " ".join(str(data.get("text") or "").split())[:800],
            }
        )
    return hits


def parse_next_action(raw: str) -> dict:
    """JSON {done, kind, target, say} — défaut : stop."""
    text = (raw or "").strip()
    js = None
    try:
        js = json.loads(text)
    except ValueError:
        import re

        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                js = json.loads(m.group(0))
            except ValueError:
                js = None
    if not isinstance(js, dict):
        return {"done": True, "kind": "", "target": "", "say": "stop (réponse illisible)"}
    done = bool(js.get("done"))
    kind = str(js.get("kind") or "").strip().lower()
    if kind not in ("search", "fetch", "deep", ""):
        kind = "search"
    return {
        "done": done or not str(js.get("target") or "").strip(),
        "kind": kind or "search",
        "target": str(js.get("target") or "").strip()[:400],
        "say": str(js.get("say") or "")[:200],
    }


PLAN_SYSTEM = (
    "Tu pilotes une recherche HTTP SANS navigateur JS. Tu reçois la question "
    "et les hits déjà obtenus. Réponds UNIQUEMENT en JSON :\n"
    '{"done": true|false, "kind": "search|fetch|deep", "target": "...", "say": "je …"}\n'
    "- done=true si tu as assez pour répondre (cite dates exactes des faits).\n"
    "- sinon kind=fetch + URL d'un hit, ou search + requête plus précise.\n"
    "- say : une phrase pour l'humain. Max 1 action. N'invente pas d'URL."
)


def decide_next(question: str, steps: list[dict], llm=None) -> dict:
    if llm is None:
        return {"done": True, "kind": "", "target": "", "say": "pas de LLM — fin après cette étape"}
    blob = json.dumps(
        [{"say": s.get("say"), "kind": s.get("kind"), "hits": s.get("hits")} for s in steps],
        ensure_ascii=False,
    )[:6000]
    user = f"Question : {question}\nÉtapes déjà faites :\n{blob}\nProchaine action ?"
    raw = llm(PLAN_SYSTEM, user)
    return parse_next_action(raw or "")


def print_step(say: str, kind: str, hits: list[dict], engine: str = "") -> None:
    print(f"\n▶ {say or kind}")
    print(f"  [{kind}] moteur={engine or '?'} · {len(hits)} hit(s)")
    for i, h in enumerate(hits, 1):
        print(f"  {i}. {h.get('title') or '(sans titre)'}")
        if h.get("url"):
            print(f"     {h['url']}")
        extra = h.get("snippet") or h.get("excerpt") or ""
        if extra:
            print(f"     « {extra[:160]} »")


def push_result(kind: str, data: dict, question: str) -> dict:
    if not PUSH_TO_SITE or not MAIN_SITE_URL:
        return {"mode": "local"}
    payload = {"kind": kind, "task_id": None, "data": {**data, "meta": {"origin": "colab-agent", "question": question[:300]}}}
    try:
        code, resp = _http_json("POST", MAIN_SITE_URL + "/api/research/results", payload, timeout=40)
        return {"mode": "ok" if code == 200 else "erreur", "code": code, "detail": str(resp)[:160]}
    except Exception as exc:  # noqa: BLE001
        return {"mode": "erreur", "detail": str(exc)[:160]}


def run_agent(question: str, *, max_steps: int = MAX_STEPS, llm=None, runner=None, log=print) -> dict:
    """Boucle agent : search → hits → (fetch|search|stop). `runner`/`llm` injectables."""
    runner = runner or run_http_step
    steps: list[dict] = []
    kind, target, say = "search", question, f"je cherche « {question[:80]} »"
    for i in range(max(1, max_steps)):
        log(f"\n── étape {i + 1}/{max_steps} · {kind} ──")
        data = runner(kind, target)
        hits = compact_hits(data)
        rec = {
            "say": say,
            "kind": kind,
            "target": target,
            "engine": data.get("engine") or data.get("http_status") or "http",
            "hits": hits,
            "error": data.get("error"),
            "data": data,
        }
        steps.append(rec)
        print_step(say, kind, hits, str(rec["engine"]))
        nxt = decide_next(question, steps, llm=llm)
        if nxt.get("done") or i == max_steps - 1:
            rec["stop"] = nxt.get("say") or "terminé"
            break
        kind, target, say = nxt["kind"], nxt["target"], nxt.get("say") or f"je {nxt['kind']} {nxt['target'][:60]}"
    return {"question": question, "steps": steps, "generated_at": _now_iso()}


def _optional_mistral():
    key = (os.environ.get("COLAB_LLM_API_KEY") or os.environ.get("MISTRAL_API_KEY") or "").strip()
    if not key:
        try:
            from getpass import getpass

            key = getpass("Clé Mistral optionnelle (Entrée = agent sans LLM, 1 search) : ").strip()
        except Exception:
            key = ""
    if not key:
        return None

    def llm(system: str, user: str) -> str:
        body = {
            "model": MISTRAL_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": 400,
        }
        raw = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            MISTRAL_API_BASE.rstrip("/") + "/chat/completions",
            data=raw,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": UA,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""

    return llm


def main(prompt=input) -> int:
    print("═" * 64)
    print(f" 🔎 RECHERCHE AGENTIQUE v{SCRIPT_VERSION} — HTTP only (pas de navigateur JS)")
    print(f" Site : {MAIN_SITE_URL or '(local)'} · max {MAX_STEPS} étapes")
    print("═" * 64)
    try:
        q = prompt("Question à chercher (ex. dernier modèle Anthropic) : ").strip()
    except (EOFError, KeyboardInterrupt):
        return 1
    if not q:
        print("Aucune question.")
        return 1
    llm = _optional_mistral()
    report = run_agent(q, llm=llm)
    last = report["steps"][-1] if report["steps"] else {}
    push = push_result(str(last.get("kind") or "search"), last.get("data") or {}, q)
    print(f"\n📤 push site : {push.get('mode')} {push.get('detail', '')}")
    print("🏁 Fin. Relance le chat du site : list_research_results / search_knowledge (dates).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
