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

print("[3] _sanitize_api_key — bug v1 : « — » cassait l'en-tête HTTP (latin-1)")
BOOM = "abc23456789012345678901—xyz4567"  # tiret cadratin U+2014 à la position 30 de « Bearer … »
try:
    ("Bearer " + BOOM).encode("latin-1")
    check("repro : — casse bien latin-1", False, "aurait dû lever UnicodeEncodeError")
except UnicodeEncodeError:
    check("repro : — casse bien latin-1", True)
key, notes = ag._sanitize_api_key('  "' + BOOM + '"\n')
check("clé nettoyée (— → -, guillemets, espaces)", key == "abc23456789012345678901-xyz4567", repr(key))
check("en-tête latin-1 OK après nettoyage", ("Bearer " + key).encode("latin-1") is not None)
check("avertissement émis", bool(notes), str(notes))
check("apostrophe courbe", ag._sanitize_api_key("a’b\u2019c")[0] == "a'b'c")
check("espaces internes/retours retirés", ag._sanitize_api_key("a b\nc\r\nd")[0] == "abcd")
check("non-ASCII restants ignorés", ag._sanitize_api_key("clé!")[0] == "cl!")
check("clé vide → ('', [])", ag._sanitize_api_key("   ") == ("", []))

print("[4] LLM en échec → arrêt propre (plus de traceback)")
def llm_boom(_sys, _user):
    raise RuntimeError("HTTP Error 401: Unauthorized")


nxt = ag.decide_next("q", [{"say": "x", "kind": "search", "hits": []}], llm=llm_boom)
check("decide_next survit", nxt["done"] is True and "LLM" in nxt["say"], str(nxt))
calls2: list[tuple[str, str]] = []


def runner2(kind, target):
    calls2.append((kind, target))
    return {"kind": kind, "engine": "fake", "results": [{"title": "t", "url": "https://x.test", "snippet": "s"}]}


rep2 = ag.run_agent("test", max_steps=4, llm=llm_boom, runner=runner2, log=lambda *_a, **_k: None)
check("run_agent survit (1 étape, stop LLM KO)", len(rep2["steps"]) == 1 and "LLM" in rep2["steps"][0].get("stop", ""), str(rep2["steps"][-1].get("stop")))

print("[5] first_kind — une tâche fetch commence par fetch")
calls3: list[str] = []


def runner3(kind, target):
    calls3.append(kind)
    return {"kind": kind, "url": target, "title": "t", "text": "contenu"}


ag.run_agent("https://x.test/page", max_steps=1, llm=None, runner=runner3, log=lambda *_a, **_k: None, first_kind="fetch")
check("première étape = fetch", calls3[0] == "fetch", str(calls3))
check("première étape par défaut = search", ag.run_agent("q", max_steps=1, llm=None, runner=runner3, log=lambda *_a, **_k: None) is not None and calls3[-1] == "search")

print("[6] pull_pending_tasks (API mockée)")
def j_ok(method, url, payload=None, timeout=30):
    assert method == "GET" and url.endswith("/api/research/tasks"), url
    return 200, {"tasks": [  # le serveur trie par date décroissante (plus récentes d'abord)
        {"id": "t3", "kind": "search", "target": "C", "status": "processing", "created_at": "2026-09-17"},
        {"id": "t2", "kind": "search", "target": "B", "status": "pending", "created_at": "2026-09-16"},
        {"id": "t1", "kind": "fetch", "target": "https://a", "status": "pending", "created_at": "2026-09-14"},
        {"id": "t0", "kind": "search", "target": "done", "status": "done", "created_at": "2026-09-13"},
    ]}


tasks = ag.pull_pending_tasks(_json=j_ok, retry_wait_s=0)
check("pending + processing seulement", [t["id"] for t in tasks] == ["t1", "t2", "t3"], str([t["id"] for t in tasks]))
check("FIFO : plus ancienne d'abord", tasks[0]["id"] == "t1", str([t["id"] for t in tasks]))
check("done exclue", all(t["id"] != "t0" for t in tasks))
check("limit", [t["id"] for t in ag.pull_pending_tasks(limit=1, _json=j_ok, retry_wait_s=0)] == ["t1"])


def j_ko(method, url, payload=None, timeout=30):
    raise RuntimeError("connexion refusée")


check("serveur KO → None (2 essais)", ag.pull_pending_tasks(_json=j_ko, retry_wait_s=0) is None)

print("[7] push_result / mark_task avec task_id (HTTP mocké)")
sent: list[tuple[str, str, dict]] = []
_orig_json, _orig_push = ag._http_json, ag.PUSH_TO_SITE


def j_rec(method, url, payload=None, timeout=30):
    sent.append((method, url, payload or {}))
    return 200, {"ok": True}


ag._http_json, ag.PUSH_TO_SITE = j_rec, True
push = ag.push_result("search", {"results": [], "query": "q"}, "question ?", task_id="task-42")
check("push ok", push.get("mode") == "ok", str(push))
check("POST /api/research/results avec task_id", sent and sent[0][0] == "POST" and sent[0][1].endswith("/api/research/results") and sent[0][2].get("task_id") == "task-42", str(sent[:1]))
ok = ag.mark_task("task-42", "done")
check("PATCH statut", ok and sent[-1][0] == "PATCH" and sent[-1][1].endswith("/api/research/tasks/task-42") and sent[-1][2] == {"status": "done"}, str(sent[-1]))
ag._http_json, ag.PUSH_TO_SITE = _orig_json, False  # la suite : aucun réseau

print("[8] run_tasks_mode — l'agent traite la file (tout mocké)")
task_calls: list[tuple[str, str]] = []


def task_runner(kind, target):
    task_calls.append((kind, target))
    if kind == "fetch":
        return {"kind": "fetch", "url": target, "title": "page", "text": "contenu lu"}
    return {"kind": "search", "engine": "fake", "results": [{"title": "hit", "url": "https://x.test", "snippet": "s"}]}


summary = ag.run_tasks_mode(
    llm=None,
    fetch_tasks=lambda: [
        {"id": "ta", "kind": "search", "target": "sujet A", "status": "pending"},
        {"id": "tb", "kind": "fetch", "target": "https://x.test/doc", "status": "pending"},
        {"id": "tc", "kind": "note", "target": "une note à garder", "status": "pending"},
    ],
    runner=task_runner,
    log=lambda *_a, **_k: None,
)
check("3 tâches traitées", len(summary["done"]) == 3, str(summary))
check("résumé ok", summary.get("ok") is True)
check("toutes réussies", all(d["ok"] for d in summary["done"]), str(summary["done"]))
check("tâche fetch → 1re étape fetch", ("fetch", "https://x.test/doc") in task_calls, str(task_calls))
check("tâche search → étape search", ("search", "sujet A") in task_calls)
check("tâche note : pas d'étape agent", ("search", "une note à garder") not in task_calls and ("note", "une note à garder") not in task_calls, str(task_calls))
note_res = next(d for d in summary["done"] if d["task_id"] == "tc")
check("note ok sans étape", note_res["ok"] and note_res["steps"] == 0, str(note_res))
check("cap max_tasks", len(ag.run_tasks_mode(fetch_tasks=lambda: [{"id": f"t{i}", "kind": "search", "target": "x"} for i in range(9)], runner=task_runner, max_tasks=2, log=lambda *_a, **_k: None)["done"]) == 2)
unreach = ag.run_tasks_mode(fetch_tasks=lambda: None, log=lambda *_a, **_k: None)
check("file injoignable → ok=False", unreach.get("ok") is False and unreach["done"] == [])
empty = ag.run_tasks_mode(fetch_tasks=lambda: [], log=lambda *_a, **_k: None)
check("file vide → ok=True", empty.get("ok") is True and empty["done"] == [])

print("[9] main() — le choix du mode")
_orig_mistral, _orig_tasks = ag._optional_mistral, ag.run_tasks_mode
captured: dict = {}
ag._optional_mistral = lambda: None
ag.run_tasks_mode = lambda llm=None, **kw: captured.update(llm="vu", **kw) or {"ok": True, "done": []}
rc2 = ag.main(prompt=lambda *a, **k: "2")
check("mode 2 → run_tasks_mode avec le LLM", rc2 == 0 and captured.get("llm") == "vu", str(captured))
_orig_agent, _orig_pushres = ag.run_agent, ag.push_result
ag.run_agent = lambda q, **kw: {"steps": [{"kind": "search", "data": {"kind": "search", "results": []}}]}
ag.push_result = lambda kind, data, q, task_id=None: captured.update(push=(kind, task_id)) or {"mode": "ok"}
_answers1 = iter(["1", "question libre"])
rc1 = ag.main(prompt=lambda *a, **k: next(_answers1))
check("mode 1 (défaut) → agent + push sans task_id", rc1 == 0 and captured.get("push") == ("search", None), str(captured.get("push")))
ag._optional_mistral, ag.run_tasks_mode = _orig_mistral, _orig_tasks
ag.run_agent, ag.push_result = _orig_agent, _orig_pushres

print(f"RÉSULTAT : {len(PASSED)} OK, {len(FAILED)} en échec")
if FAILED:
    raise SystemExit(1)
