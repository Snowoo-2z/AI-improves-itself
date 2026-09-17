"""Recherche agentique — 1 cellule Colab (copier-coller).

Pas de navigateur JS (Colab n'en a pas). Le script :

  1. propose 2 modes :
       - « recherche personnalisée » : tu tapes ta question libre ;
       - « tâches du site » : la file pending est rapatriée (GET
         /api/research/tasks) et l'agent traite chaque tâche (statuts PATCH
         + résultats POST /api/research/results avec le vrai task_id) ;
  2. dit ce qu'il fait (« je cherche … ») ;
  3. exécute HTTP (DDG → Wikipédia → fetch HTML, robots.txt) ;
  4. affiche les hits ; éventuellement Mistral choisit l'étape suivante
     (fetch une URL, autre search, stop) — max MAX_STEPS ;
  5. pousse les résultats au site (POST /api/research/results).

Robustesse clé (bug v1 corrigé) : une clé collée à la main peut contenir
des caractères typographiques (tiret cadratin « — », apostrophe courbe,
retour à la ligne…) que HTTP refuse dans ses en-têtes (latin-1 seulement) —
cela plantait tout le run avec UnicodeEncodeError. La clé est maintenant
nettoyée (_sanitize_api_key) et un appel LLM qui échoue (clé refusée,
réseau…) arrête proprement l'agent au lieu de lever un traceback.

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

SCRIPT_VERSION = 2
MAIN_SITE_URL = os.environ.get("MAIN_SITE_URL", "https://aiis-core.onrender.com").rstrip("/")
MAX_STEPS = 4
#: Mode « tâches » : borne le run (sessions Colab limitées). AGENT_MAX_TASKS=1…
try:
    MAX_TASKS_PER_RUN = max(1, int(os.environ.get("AGENT_MAX_TASKS", "3") or 3))
except ValueError:
    MAX_TASKS_PER_RUN = 3
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


# ------------------------------------------------- clé API (bug v1 : —) ------
#: Caractères qui s'invitent dans un collage (traitement de texte, chat…) et
#: que HTTP refuse dans un en-tête (latin-1 seulement) : « — » faisait planter
#: urllib avec UnicodeEncodeError avant même d'appeler l'API Mistral.
_KEY_TYPO_FIXES = {
    "\u2014": "-",  # — tiret cadratin
    "\u2013": "-",  # – tiret demi-cadratin
    "\u2212": "-",  # − signe moins
    "\u2018": "'",  # ‘ apostrophe courbe
    "\u2019": "'",  # ’ apostrophe courbe
    "\u201c": '"',  # “ guillemet courbe ouvrant
    "\u201d": '"',  # ” guillemet courbe fermant
    "\u00a0": "",   # espace insécable
    "\u200b": "",   # espace sans chasse (zéro largeur)
    "\ufeff": "",   # BOM
}


def _sanitize_api_key(raw: str) -> tuple[str, list[str]]:
    """Nettoie une clé API collée à la main. Une clé d'API est ASCII : on
    retire espaces/retours à la ligne, guillemets d'encadrement, BOM et on
    convertit les caractères typographiques (— → -, ’ → '…). Retourne
    (clé propre, avertissements humains) — plus jamais de traceback."""
    notes: list[str] = []
    key = str(raw or "").replace("\ufeff", "").replace("\u200b", "")
    key = key.strip().strip('"').strip("'").strip()
    joined = "".join(key.split())  # colle les retours à la ligne / espaces internes
    if joined != key:
        notes.append("espaces/retours à la ligne retirés")
        key = joined
    fixed = "".join(_KEY_TYPO_FIXES.get(ch, ch) for ch in key)
    if fixed != key:
        notes.append("caractères typographiques convertis (— → -, ’ → '…)")
        key = fixed
    bad = sorted({ch for ch in key if ord(ch) > 127})
    if bad:
        notes.append("caractères non-ASCII ignorés : " + ", ".join(f"U+{ord(c):04X}" for c in bad))
        key = "".join(ch for ch in key if ord(ch) <= 127)
    return key, notes


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
    try:
        raw = llm(PLAN_SYSTEM, user)
    except Exception as exc:  # noqa: BLE001 — clé refusée, réseau, encodage : arrêt propre
        msg = " ".join(str(exc).split())[:160] or type(exc).__name__
        return {"done": True, "kind": "", "target": "", "say": f"LLM indisponible ({msg}) — fin après cette étape"}
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


def push_result(kind: str, data: dict, question: str, task_id: str | None = None) -> dict:
    if not PUSH_TO_SITE or not MAIN_SITE_URL:
        return {"mode": "local"}
    payload = {
        "kind": kind,
        "task_id": task_id,
        "data": {**data, "meta": {"origin": "colab-agent", "question": question[:300]}},
    }
    try:
        code, resp = _http_json("POST", MAIN_SITE_URL + "/api/research/results", payload, timeout=40)
        return {"mode": "ok" if code == 200 else "erreur", "code": code, "detail": str(resp)[:160]}
    except Exception as exc:  # noqa: BLE001
        return {"mode": "erreur", "detail": str(exc)[:160]}


def run_agent(
    question: str,
    *,
    max_steps: int = MAX_STEPS,
    llm=None,
    runner=None,
    log=print,
    first_kind: str = "search",
) -> dict:
    """Boucle agent : search → hits → (fetch|search|stop). `runner`/`llm` injectables.
    `first_kind` : première étape (search par défaut ; fetch/deep pour les tâches du site)."""
    runner = runner or run_http_step
    steps: list[dict] = []
    kind = str(first_kind or "search").strip().lower()
    if kind not in ("search", "fetch", "deep"):
        kind = "search"
    verbs = {"search": "cherche", "fetch": "lis", "deep": "creuse"}
    target = question
    say = f"je {verbs.get(kind, 'cherche')} « {question[:80]} »"
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
            log(f"\n⏹ {rec['stop']}")
            break
        kind, target, say = nxt["kind"], nxt["target"], nxt.get("say") or f"je {nxt['kind']} {nxt['target'][:60]}"
    return {"question": question, "steps": steps, "generated_at": _now_iso()}


# ---------------------------------------------------- mode 2 : tâches -------
def pull_pending_tasks(limit: int | None = None, _json=None, retry_wait_s: float = 10.0) -> list[dict] | None:
    """Tâches pending/processing du site (None = serveur injoignable).
    Réveille le serveur au besoin (Render gratuit : ~1 min au réveil)."""
    if not MAIN_SITE_URL:
        return []
    j = _json or _http_json
    last = ""
    for attempt in (1, 2):
        try:
            code, data = j("GET", MAIN_SITE_URL + "/api/research/tasks", timeout=75)
            if code == 200 and isinstance(data, dict):
                tasks = [
                    t
                    for t in (data.get("tasks") or [])
                    if isinstance(t, dict) and t.get("status") in ("pending", "processing")
                ]
                tasks.reverse()  # FIFO : l'API trie par date décroissante, on joue la plus ancienne d'abord
                return tasks[:limit] if limit else tasks
            last = f"HTTP {code}"
        except Exception as exc:  # noqa: BLE001
            last = " ".join(str(exc).split())[:160]
        if attempt == 1:
            print("  ⏳ serveur peut-être endormi (plan gratuit Render : ~1 min) — nouvel essai…")
            if retry_wait_s:
                time.sleep(retry_wait_s)
    print(f"! tâches du site injoignables ({last}).")
    return None


def mark_task(task_id, status: str, retries: int = 2) -> bool:
    """PATCH le statut d'une tâche (best-effort, avec réessai)."""
    if not PUSH_TO_SITE or not MAIN_SITE_URL or not task_id:
        return False
    last = ""
    for attempt in range(retries):
        try:
            code, _data = _http_json(
                "PATCH",
                MAIN_SITE_URL + "/api/research/tasks/" + urllib.parse.quote(str(task_id)),
                {"status": status},
                timeout=25,
            )
            if code == 200:
                return True
            if code == 404:
                print(f"  ! tâche {task_id} inconnue du serveur (404).")
                return False
            last = f"HTTP {code}"
        except Exception as exc:  # noqa: BLE001
            last = " ".join(str(exc).split())[:120]
        if attempt < retries - 1:
            time.sleep(2)
    print(f"  ! statut {status} non poussé (tâche {task_id}) : {last}")
    return False


def execute_task(task: dict, *, llm=None, runner=None, log=print) -> dict:
    """Exécute UNE tâche du site avec l'agent, puis pousse statut + résultat."""
    tid = task.get("id")
    kind = str(task.get("kind") or "search").strip().lower()
    if kind not in ("search", "fetch", "note", "deep"):
        kind = "search"
    target = str(task.get("target") or "").strip()
    log(f"\n🧩 tâche {str(tid)[:14] or '(sans id)'} · {kind} : {target[:90]}")
    mark_task(tid, "processing")
    try:
        if not target:
            raise ValueError("cible vide")
        if kind == "note":  # rien à chercher : on pousse la note telle quelle
            data = {"kind": "note", "content": target}
            n_steps = 0
        else:
            report = run_agent(target, llm=llm, runner=runner, log=log, first_kind=kind)
            n_steps = len(report.get("steps") or [])
            last = report["steps"][-1] if report["steps"] else {}
            data = last.get("data") or {}
            kind = str(last.get("kind") or kind)  # le résultat a le type de sa DERNIÈRE étape
        push = push_result(kind, data, target, task_id=tid)
        if push.get("mode") == "erreur":
            log("   ! push KO — tâche laissée « processing » : elle sera rejouée au prochain run")
            return {"task_id": tid, "kind": kind, "target": target, "ok": False, "error": "push " + str(push.get("detail"))[:160], "steps": n_steps}
        mark_task(tid, "done")
        log(f"   ✅ done · {n_steps} étape(s) · push : {push.get('mode')}")
        return {"task_id": tid, "kind": kind, "target": target, "ok": True, "steps": n_steps, "push": push}
    except Exception as exc:  # noqa: BLE001 — une tâche KO n'arrête pas la file
        mark_task(tid, "failed")
        msg = " ".join(str(exc).split())[:180]
        log(f"   ❌ failed : {msg}")
        return {"task_id": tid, "kind": kind, "target": target, "ok": False, "error": msg}


def run_tasks_mode(llm=None, *, max_tasks: int | None = None, fetch_tasks=None, runner=None, log=print) -> dict:
    """Mode 2 : l'agent traite la file pending du site (statuts + résultats poussés)."""
    fetch = fetch_tasks or (lambda: pull_pending_tasks())
    tasks = fetch()
    if tasks is None:
        log("! file de tâches injoignable — le serveur dort ? Relance dans 1 min, ou passe en mode recherche personnalisée.")
        return {"ok": False, "error": "file de tâches injoignable", "done": []}
    cap = MAX_TASKS_PER_RUN if max_tasks is None else max(0, int(max_tasks))
    tasks = [t for t in tasks if isinstance(t, dict)][:cap]
    log(f"📥 {len(tasks)} tâche(s) à traiter (max {cap} par run — AGENT_MAX_TASKS pour changer)")
    if not tasks:
        log("Rien à faire ✅ — ajoute des tâches sur le site (skill add_research_task ou page /colab).")
        return {"ok": True, "done": []}
    done = [execute_task(t, llm=llm, runner=runner, log=log) for t in tasks]
    ok = sum(1 for d in done if d.get("ok"))
    log(f"\n🏁 {ok}/{len(done)} tâche(s) traitée(s) — résultats visibles sur /colab (étude serveur ~1 min).")
    return {"ok": True, "done": done}


def _optional_mistral():
    raw = (os.environ.get("COLAB_LLM_API_KEY") or os.environ.get("MISTRAL_API_KEY") or "").strip()
    if not raw:
        try:
            from getpass import getpass

            raw = getpass("Clé Mistral optionnelle (Entrée = agent sans LLM, 1 search) : ")
        except Exception:
            raw = ""
    key, notes = _sanitize_api_key(raw)
    for n in notes:
        print(f"  ⚠️ clé API : {n}")
    if not key:
        return None

    def llm(system: str, user: str) -> str:
        body = {
            "model": MISTRAL_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": 400,
        }
        raw_body = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            MISTRAL_API_BASE.rstrip("/") + "/chat/completions",
            data=raw_body,
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
    print(f" Site : {MAIN_SITE_URL or '(local)'} · max {MAX_STEPS} étapes · {MAX_TASKS_PER_RUN} tâche(s)/run")
    print("═" * 64)
    try:
        mode = prompt("Mode — 1 = recherche personnalisée · 2 = tâches du site (pending) [1] : ").strip()
    except (EOFError, KeyboardInterrupt):
        return 1
    llm = _optional_mistral()
    if mode == "2":
        summary = run_tasks_mode(llm=llm)
        return 0 if summary.get("ok") else 1
    try:
        q = prompt("Question à chercher (ex. dernier modèle Anthropic) : ").strip()
    except (EOFError, KeyboardInterrupt):
        return 1
    if not q:
        print("Aucune question.")
        return 1
    report = run_agent(q, llm=llm)
    last = report["steps"][-1] if report["steps"] else {}
    push = push_result(str(last.get("kind") or "search"), last.get("data") or {}, q)
    print(f"\n📤 push site : {push.get('mode')} {push.get('detail', '')}")
    print("🏁 Fin. Relance le chat du site : list_research_results / search_knowledge (dates).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
