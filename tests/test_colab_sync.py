"""Tests du script Colab v2 (colab/main.py) et du kind `deep` côté serveur.

Aucun appel réseau : fichiers redirigés vers un dossier temporaire
(RESEARCH_TASKS_PATH + COLAB_RESULTS_PATH), HTTP mocké, LLM mocké.
On vérifie :
- merge_tasks : le statut le plus avancé gagne (une tâche done ne
  ressuscite jamais — le bug v1 qui ré-exécutait tout à chaque run),
- select_unpushed : seuls les résultats pushed=false sont repoussés,
- parseurs DDG html/lite + cascade web_search (mock),
- extraction HTML (titre, meta description, article prioritaire),
- parse_llm_json tolérant + redact() des clés API,
- can_fetch (robots.txt, mock),
- kind `deep` : create_task serveur + étude (study_result).

Lancer :  python tests/test_colab_sync.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Fichiers de test isolés AVANT tout import (colab/main.py fige ses chemins
# à l'import ; core/store lit l'env à chaque appel).
TMP = tempfile.mkdtemp(prefix="aiis_colab_test_")
os.environ["RESEARCH_TASKS_PATH"] = os.path.join(TMP, "tasks.json")
os.environ["COLAB_RESULTS_PATH"] = os.path.join(TMP, "results.json")
_ORIG_BACKEND = os.environ.get("STORE_BACKEND")
os.environ["STORE_BACKEND"] = "local"  # jamais de backend distant en test

_spec = importlib.util.spec_from_file_location("colab_main_v2", os.path.join(REPO_ROOT, "colab", "main.py"))
assert _spec and _spec.loader
colab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(colab)

from core import store as store_module  # noqa: E402
from core.ai import providers as P  # noqa: E402
from core.research import service as service_module  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


print("== 0. Version du script ==")
check("COLAB_SCRIPT_VERSION >= 2", getattr(colab, "COLAB_SCRIPT_VERSION", 1) >= 2)
check("chemins de test isolés", colab.TASKS_PATH.startswith(TMP) and colab.RESULTS_PATH.startswith(TMP))
check("cache local par défaut = tasks_cache.json (le serveur possède les tâches)",
      colab._resolve_json_path("", "tasks_cache.json").endswith("tasks_cache.json"))
_seed = json.load(open(os.path.join(REPO_ROOT, "colab", "tasks.json"), encoding="utf-8"))
check("colab/tasks.json reste un seed de démo versionné",
      isinstance(_seed, list) and any(t.get("id") == "task-demo-1" for t in _seed))

print("== 1. merge_tasks : le statut le plus avancé gagne (bug v1 corrigé) ==")
m = colab.merge_tasks(
    [{"id": "A", "status": "pending", "target": "x"}],
    [{"id": "A", "status": "done", "target": "x"}],
)
check("distant done écrase local pending (seed ressuscité)", len(m) == 1 and m[0]["status"] == "done", json.dumps(m))
m = colab.merge_tasks(
    [{"id": "A", "status": "done", "target": "x"}],
    [{"id": "A", "status": "pending", "target": "x"}],
)
check("local done survit à distant pending (push statut perdu)", m[0]["status"] == "done", json.dumps(m))
m = colab.merge_tasks(
    [{"id": "A", "status": "pending"}, {"id": "B", "status": "pending"}],
    [{"id": "B", "status": "done"}, {"id": "C", "status": "pending"}],
)
by = {t["id"]: t["status"] for t in m}
check("union par id + statuts fusionnés", by == {"A": "pending", "B": "done", "C": "pending"}, json.dumps(by))
m = colab.merge_tasks([{"id": "D", "status": "failed"}], [{"id": "D", "status": "pending"}])
check("failed terminal ne redevient pas pending", m[0]["status"] == "failed")
m = colab.merge_tasks([{"kind": "note", "target": "sans id"}], [])
check("tâche locale sans id conservée", len(m) == 1 and m[0]["target"] == "sans id")
m = colab.merge_tasks([{"id": "E", "status": "pending"}], [{"id": "E", "status": "pending", "target": "hello"}])
check("le distant complète les champs manquants", m[0].get("target") == "hello", json.dumps(m))

print("== 2. select_unpushed : retry sans doublons ==")
res = [
    {"task_id": "a", "pushed": True},
    {"task_id": "b"},  # entrée v1 (sans champ) : supposée poussée, pas de re-push massif
    {"task_id": "c", "pushed": False},
    {"task_id": "d", "pushed": False, "push_error": "boom"},
]
todo = colab.select_unpushed(res)
check("seuls les pushed=false repartent", [e["task_id"] for e in todo] == ["c", "d"])

print("== 3. Parseurs DDG (fixtures, sans réseau) ==")
DDG_HTML = """
<div class="result">
<a class="result__a" href="//duckduckgo.com/l/?kh=-1&amp;uddg=https%3A%2F%2Fexample.com%2Fpage">Example <b>Title</b></a>
<a class="result__snippet" href="//duckduckgo.com/l/?kh=-1&amp;uddg=https%3A%2F%2Fexample.com%2Fpage">Snippet text here.</a>
</div>
<div class="result">
<a class="result__a" href="https://direct.example.com/x">Second Title</a>
</div>
"""
parsed = colab.parse_ddg_html(DDG_HTML, 5)
check("ddg-html : 2 résultats", len(parsed) == 2, json.dumps(parsed)[:200])
check("ddg-html : uddg décodée", parsed[0]["url"] == "https://example.com/page", parsed[0]["url"])
check("ddg-html : titre débalisé", parsed[0]["title"] == "Example Title", parsed[0]["title"])
check("ddg-html : snippet capturé", parsed[0]["snippet"] == "Snippet text here.", parsed[0]["snippet"])
check("ddg-html : lien direct gardé tel quel", parsed[1]["url"] == "https://direct.example.com/x")
DDG_LITE = """
<tr><td>1.</td><td><a rel="nofollow" href="https://lite.example.com/a">Lite Title</a></td></tr>
<tr><td></td><td class='result-snippet'>Lite snippet here</td></tr>
"""
lite = colab.parse_ddg_lite(DDG_LITE, 5)
check("ddg-lite : 1 résultat + snippet", len(lite) == 1 and lite[0]["snippet"] == "Lite snippet here",
      json.dumps(lite)[:200])

print("== 4. Cascade web_search (HTTP mocké) ==")


def _fake_ddg_down(url, timeout=30, retries=1):
    if "html.duckduckgo.com" in url:
        raise RuntimeError("bloqué (challenge)")
    if "lite.duckduckgo.com" in url:
        return (200, DDG_LITE, url)
    raise AssertionError(f"ne devrait pas aller plus loin : {url}")


with mock.patch.object(colab, "_http_get", side_effect=_fake_ddg_down):
    out = colab.web_search("test")
check("html KO → lite sert (engine tracé)", out.get("engine") == "ddg-lite" and len(out["results"]) == 1,
      json.dumps(out)[:200])


def _fake_wiki_only(url, timeout=30, retries=1):
    if "duckduckgo" in url:
        return (200, "<html>rien</html>", url)
    if "fr.wikipedia.org" in url:
        return (200, json.dumps({"query": {"search": [{"title": "Chat", "snippet": "un <b>félin</b> domestique"}]}}), url)
    raise AssertionError(f"ne devrait pas aller plus loin : {url}")


with mock.patch.object(colab, "_http_get", side_effect=_fake_wiki_only):
    out = colab.web_search("chat")
check("ddg vide → wikipedia-fr sert", out.get("engine") == "wikipedia-fr", json.dumps(out)[:160])
check("snippet wikipédia débalisé", out["results"][0]["snippet"] == "un félin domestique",
      out["results"][0]["snippet"])

print("== 5. Extraction HTML ==")
PAGE = """<html><head><title>Page Title &amp; Co</title>
<meta name="description" content="Meta desc here"></head>
<body><nav>menu</nav><article><h1>Hello</h1><p>Contenu principal.</p></article>
<aside>pub</aside><script>var x = 1;</script></body></html>"""
check("titre extrait + entités décodées", colab.extract_title(PAGE) == "Page Title & Co", colab.extract_title(PAGE))
check("meta description extraite", colab.extract_meta_description(PAGE) == "Meta desc here")
txt = colab.html_to_text(PAGE)
check("article conservé", "Contenu principal" in txt, txt[:120])
check("script/nav/aside jetés", "var x" not in txt and "pub" not in txt and "menu" not in txt, txt[:120])

print("== 6. parse_llm_json + redact ==")
check("JSON pur", colab.parse_llm_json('{"a": 1}') == {"a": 1})
check("JSON fencé ```json", colab.parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1})
check("JSON noyé dans du texte", colab.parse_llm_json('voici {"a": 1} ok') == {"a": 1})
check("texte sans JSON → None", colab.parse_llm_json("nawak") is None)
check("vide → None", colab.parse_llm_json("") is None)
secret = "sk-SECRET1234567890"
check("redact masque la clé", secret not in colab.redact(f"erreur {secret} fin", [secret]),
      colab.redact(f"erreur {secret} fin", [secret]))
check("redact ignore les secrets trop courts", colab.redact("abc", ["abc"]) == "abc")

print("== 7. can_fetch (robots.txt mocké) ==")


def _fake_robots(url, timeout=10):
    return (200, "User-agent: *\nDisallow: /prive/\n", url)


colab._ROBOTS_CACHE.clear()
check("URL interdite refusée", colab.can_fetch("https://r.test/prive/x", _get=_fake_robots) is False)
check("URL autorisée acceptée", colab.can_fetch("https://r.test/public", _get=_fake_robots) is True)


def _boom(url, timeout=10):
    raise RuntimeError("robots down")


colab._ROBOTS_CACHE.clear()
check("robots injoignable → on tente (best-effort)", colab.can_fetch("https://r2.test/x", _get=_boom) is True)
check("schéma non-http refusé", colab.can_fetch("ftp://x/y") is False)

print("== 8. Serveur : kind deep accepté ==")
store_module.reset_store_cache()
try:
    item = service_module.create_task("deep", "sujet x", "parce que", by="ai")
    check("create_task(deep) → pending", item.get("kind") == "deep" and item.get("status") == "pending",
          json.dumps(item)[:160])
except ValueError as exc:
    check("create_task(deep) → pending", False, str(exc))
try:
    service_module.create_task("zzz", "x")
    check("kind inconnu rejeté", False)
except ValueError:
    check("kind inconnu rejeté", True)
# la skill expose deep à l'IA
from core.skills import manager as skills  # noqa: E402

tool = next(s for s in skills.list_skills() if s["id"] == "add_research_task")
check("skill add_research_task propose deep", "deep" in tool["parameters"]["properties"]["kind"]["enum"])

print("== 9. Serveur : étude d'un résultat deep ==")


class FakeProvider:
    name = "mistral-fake"

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[tuple[list[dict], list | None]] = []

    def failover(self, messages, tools=None):
        self.calls.append((messages, tools))
        content = self.replies.pop(0)
        return P.FailoverOutcome(
            result=P.ProviderResult(content=content, provider=self.name, model="fake-1"),
            provider=self,
            errors=[],
            attempts=[],
            fell_back_to_demo=False,
        )


# knowledge isolée : snapshot + suppression (restaurée en fin de test).
_knowledge_path = store_module._path("knowledge")
_knowledge_snap = open(_knowledge_path, encoding="utf-8").read() if os.path.exists(_knowledge_path) else None
if os.path.exists(_knowledge_path):
    os.remove(_knowledge_path)
store_module.reset_store_cache()
_s = store_module.get_store()
fp = FakeProvider([
    json.dumps({"ok": True, "title": "Mistral 2026", "category": "ia", "date": "2026-09-01",
                "summary": "Nouveautés.", "source": "https://mistral.ai", "confidence": 0.9}),
    json.dumps({"approve": True,
                "json": {"title": "Mistral 2026", "category": "ia", "date": "2026-09-01",
                         "summary": "Nouveautés.", "source": "https://mistral.ai"},
                "confidence": 0.9, "issues": ""}),
])
deep_data = {
    "query": "Mistral 2026",
    "engine": "ddg-html",
    "results": [
        {"title": "Annonce", "url": "https://mistral.ai/nouveau", "snippet": "un extrait pertinent",
         "text": "le contenu de la page lue"},
    ],
}
with mock.patch.object(service_module, "chat_with_failover", side_effect=fp.failover):
    out = service_module.study_result({"kind": "deep", "data": deep_data, "id": "r-deep"})
check("study deep → added", out.get("status") == "added", json.dumps(out)[:200])
first_user = fp.calls[0][0][1]["content"] if fp.calls else ""
check("snippets transmis à l'IA (1er appel)", "extrait pertinent" in first_user, first_user[:200])
check("textes lus transmis à l'IA (1er appel)", "page lue" in first_user)
check("entrée écrite en base", any(e.get("title") == "Mistral 2026" for e in _s.list("knowledge")))

print("== 10. run_all 100 % local (note, sans réseau) ==")
with open(os.environ["RESEARCH_TASKS_PATH"], "w", encoding="utf-8") as fh:
    json.dump([{"id": "t-note-1", "kind": "note", "target": "contenu local",
                "reason": "test", "by": "human", "status": "pending"}], fh)
if os.path.exists(os.environ["COLAB_RESULTS_PATH"]):
    os.remove(os.environ["COLAB_RESULTS_PATH"])
_orig_site = colab.MAIN_SITE_URL
colab.MAIN_SITE_URL = ""  # mode local pur : aucun appel réseau possible
try:
    done = colab.run_all(push=False, poll_study=False)
finally:
    colab.MAIN_SITE_URL = _orig_site
check("1 tâche note exécutée localement", len(done) == 1 and done[0]["kind"] == "note")
tasks_after = json.load(open(os.environ["RESEARCH_TASKS_PATH"], encoding="utf-8"))
check("tâche locale passée done", tasks_after[0]["status"] == "done")
results_after = json.load(open(os.environ["COLAB_RESULTS_PATH"], encoding="utf-8"))
check("résultat persisté avec pushed=false", results_after[0].get("pushed") is False)
check("re-run : rien à refaire (idempotent)", colab.merge_tasks(tasks_after, [])[0]["status"] == "done")


# ------------------------------------------------------------------- fin ----
if _knowledge_snap is None:
    if os.path.exists(_knowledge_path):
        os.remove(_knowledge_path)
else:
    with open(_knowledge_path, "w", encoding="utf-8") as fh:
        fh.write(_knowledge_snap)
store_module.reset_store_cache()
if _ORIG_BACKEND is None:
    os.environ.pop("STORE_BACKEND", None)
else:
    os.environ["STORE_BACKEND"] = _ORIG_BACKEND
os.environ.pop("RESEARCH_TASKS_PATH", None)
os.environ.pop("COLAB_RESULTS_PATH", None)
shutil.rmtree(TMP, ignore_errors=True)

print()
print(f"RÉSULTAT : {len(PASSED)} ✅ / {len(FAILED)} ❌")
if FAILED:
    print("ÉCHECS :")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
