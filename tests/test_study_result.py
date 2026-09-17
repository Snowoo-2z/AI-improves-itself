"""Tests de la phase « piqûre » du pipeline de recherche : étude des résultats bruts.

On vérifie, SANS aucun appel réseau (le chat de repli est monkeypatché) :
- `study_result` : structuration (1er appel) → vérification (2e appel) → écriture
  dans la base de connaissances si les deux passes acceptent ;
- le rejet à la vérification (approve=false) n'écrit RIEN ;
- le résultat brut vide est ignoré ;
- la déduplication (titre identique déjà en base) ;
- la skill `add_knowledge` (écriture IA) ;
- l'injection de la date du jour dans le prompt système assemblé.

Lancer :  python tests/test_study_result.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core import store as store_module  # noqa: E402
from core.ai import providers as P  # noqa: E402
from core.prompt_system import registry  # noqa: E402
from core.research import service as research_service  # noqa: E402
from core.research import service as service_module  # noqa: E402 (alias, comme le code produit)
from core.skills import manager as skills  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


# ----------------------------------------------------------------- fixtures ----
class FakeProvider:
    """Provider factice : renvoie un contenu scripté via `chat(messages, tools)`."""

    name = "mistral-fake"

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[tuple[list[dict], list | None]] = []

    def failover(self, messages, tools=None):
        """side_effect pour `chat_with_failover` : enregistre l'appel réel et
        renvoie l'issue avec la prochaine réponse scriptée."""
        self.calls.append((messages, tools))
        content = self.replies.pop(0)
        return P.FailoverOutcome(
            result=P.ProviderResult(content=content, provider=self.name, model="fake-1"),
            provider=self,
            errors=[],
            attempts=[],
            fell_back_to_demo=False,
        )


def _install(results: list):  # collection research_results pré-remplie
    store_module.reset_store_cache()
    s = store_module.get_store()
    for coll in ("research_results", "knowledge"):
        coll_path = __import__("core.store", fromlist=["_path"])._path(coll)
        if os.path.exists(coll_path):
            os.remove(coll_path)
    for r in results:
        s.add("research_results", r)
    return s


def _snapshot_paths() -> dict[str, str | None]:
    """Sauvegarde les fichiers data touchés pour les restaurer AVANT de quitter
    (knowledge.json est un seed suivi par git : le test ne doit pas le clobber)."""
    from core.store import _path

    snap = {}
    for coll in ("knowledge", "research_results", "research_tasks"):
        p = _path(coll)
        snap[coll] = open(p, encoding="utf-8").read() if os.path.exists(p) else None
    return snap


def _restore(snap: dict[str, str | None]) -> None:
    from core.store import _path

    for coll, content in snap.items():
        p = _path(coll)
        if content is None:
            if os.path.exists(p):
                os.remove(p)
        else:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(content)


def _study(result: dict):
    return service_module.study_result(result)


_SNAP = _snapshot_paths()


# ------------------------------------------------------------------- 1 : ok ---
print("== 1. Structuration + vérification → entrée écrite ==")
_s = _install([])
fp = FakeProvider([
    json.dumps({"ok": True, "title": "LLM Mistral 3", "category": "ia",
                "date": "2026-09-01", "summary": "Nouveau modèle, rapide et moins cher.",
                "source": "https://mistral.ai", "confidence": 0.9}),
    json.dumps({"approve": True,
                "json": {"title": "LLM Mistral 3", "category": "ia", "date": "2026-09-01",
                         "summary": "Nouveau modèle, rapide et moins cher.", "source": "https://mistral.ai"},
                "confidence": 0.95, "issues": ""}),
])
with mock.patch.object(service_module, "chat_with_failover", side_effect=fp.failover):
    out = _study({"kind": "fetch", "data": {"text": "Mistral lance un nouveau modèle."}, "id": "r1"})

check("statut added", out.get("status") == "added", json.dumps(out))
check("2 appels LLM effectués", len(fp.calls) == 2, f"{len(fp.calls)} appels")
check("entrée conservée", out.get("entry", {}).get("title") == "LLM Mistral 3")
check("2e passe = vérification (brut + entrée)", "Entrée proposée" in fp.calls[1][0][1]["content"])
# le 1er appel reçoit la date du jour quelque part
check("la date du jour est donnée à l'IA (1er appel)", "Aujourd'hui" in fp.calls[0][0][1]["content"])
knowledge = _s.list("knowledge")
check("écrite dans la base", len(knowledge) == 1 and knowledge[0]["title"] == "LLM Mistral 3", json.dumps(knowledge))

# ------------------------------------------------------------------- 2 : veto ----
print("== 2. Vérification négative → rien d'écrit ==")
_s = _install([])
fp = FakeProvider([
    json.dumps({"ok": True, "title": "X", "category": "ia", "date": "2026-09-02",
                "summary": "rumeur non vérifiable.", "source": "?", "confidence": 0.8}),
    json.dumps({"approve": False, "json": {}, "confidence": 0.2,
                "issues": "info non sourcée, invérifiable"}),
])
with mock.patch.object(service_module, "chat_with_failover", side_effect=fp.failover):
    out = _study({"kind": "note", "data": {"content": "une rumeur..."}, "id": "r2"})
check("statut rejected", out.get("status") == "rejected", json.dumps(out))
check("raison = veto du vérifieur", "invérifiable" in out.get("reason", ""), out.get("reason", ""))
check("rien d'écrit", _s.list("knowledge") == [])

# ------------------------------------------------------------------- 3 : vide ----
print("== 3. Résultat brut vide ==")
_s = _install([])
before_calls = 0
with mock.patch.object(service_module, "chat_with_failover") as m:
    out = _study({"kind": "fetch", "data": {"text": "   "}, "id": "r3"})
    before_calls = m.call_count
check("statut skipped", out.get("status") == "skipped", json.dumps(out))
check("aucun appel LLM pour du vide", before_calls == 0, f"{before_calls} appels")

# ------------------------------------------------------------------- 4 : doublon ----
print("== 4. Déduplication ==")
_s = _install([{"kind": "note", "data": {"content": "x"}, "id": "r-dup"}])
_s.add("knowledge", {"title": "Déjà là", "category": "ia", "date": "2026-09-01",
                     "summary": "déjà en base", "source": "colab"})
fp = FakeProvider([
    json.dumps({"ok": True, "title": "Déjà là", "category": "ia", "date": "2026-09-03",
                "summary": "duplicat exact du titre", "source": "colab", "confidence": 0.9}),
    json.dumps({"approve": True,
                "json": {"title": "Déjà là", "category": "ia", "date": "2026-09-03",
                         "summary": "duplicat exact du titre", "source": "colab"},
                "confidence": 0.9, "issues": ""}),
])
with mock.patch.object(service_module, "chat_with_failover", side_effect=fp.failover):
    out = _study({"kind": "note", "data": {"content": "déjà là"}, "id": "r4"})
check("statut duplicate", out.get("status") == "duplicate", json.dumps(out))
check("base inchangée (1 seule entrée)", len(_s.list("knowledge")) == 1)

# ------------------------------------------------------------------- 5 : skill ----
print("== 5. Skill add_knowledge (écriture IA) ==")
_s = _install([])
res = skills.execute("add_knowledge", {"title": "Entrée IA", "category": "web",
                                   "date": "2026-09-05", "summary": "résumé IA", "source": "https://x.y"})
check("skill → ok", res.get("ok") is True, json.dumps(res))
check("l'entrée est dans la base", any(e.get("title") == "Entrée IA" for e in _s.list("knowledge")))
res_bad = skills.execute("add_knowledge", {"title": "  "})
check("skill sans title/summary refusée", res_bad.get("ok") is False, json.dumps(res_bad))
check("skill présente dans la liste", any(s["id"] == "add_knowledge" for s in skills.list_skills()))
# date invalide → remplacée par aujourd'hui (format valide)
res_d = skills.execute("add_knowledge", {"title": "SansDate", "summary": "x"})
found = next(e for e in _s.list("knowledge") if e.get("title") == "SansDate")
check("date par défaut au format ISO", bool(__import__("re").match(r"^\d{4}-\d{2}-\d{2}$", found.get("date", ""))), found.get("date", ""))

# ------------------------------------------------------------------- 6 : date ----
print("== 6. Injection de la date du jour dans le prompt système ==")
header = registry.current_date_header()
check("la date du jour est présente", "DATE DU JOUR" in header, header[:120])
assembled = registry.assemble_system_prompt([{"id": "main", "scope": "global", "version": 1, "content": "corps"}])
check("le prompt assemblé commence par la date", assembled.startswith("## DATE DU JOUR"), assembled[:120])
check("la date contient une année", any(ch.isdigit() for ch in header), header)

# ------------------------------------------------------------------- 7 : 2 appels ----
print("== 7. add_result déclenche l'étude en arrière-plan ==")
_s = _install([])
with mock.patch.object(service_module, "_spawn_study") as spawn:
    item = service_module.add_result("note", {"content": "du contenu"}, task_id=None)
check("add_result planifie une étude", spawn.call_count == 1, f"{spawn.call_count}")
check("le résultat est stocké en statut done", item.get("status") == "done")
# force_study=True esseule le seuil de confiance bas
fp = FakeProvider([
    json.dumps({"ok": True, "title": "Basse confiance", "category": "ia", "date": "2026-09-01",
                "summary": "peu fiable mais forcé", "source": "colab", "confidence": 0.1}),
    json.dumps({"approve": True,
                "json": {"title": "Basse confiance", "category": "ia", "date": "2026-09-01",
                         "summary": "peu fiable mais forcé", "source": "colab"},
                "confidence": 0.1, "issues": ""}),
])
with mock.patch.object(service_module, "chat_with_failover", side_effect=fp.failover):
    out_for = service_module.study_result({"kind": "note", "data": {"content": "x"}, "id": "rf"}, force=True)
check("force=True passe malgré une confiance basse", out_for.get("status") == "added", json.dumps(out_for))


# ------------------------------------------------------------------- 8 : retryable ----
print("== 8. Bilan d'étude : les échecs transitoires sont marqués retryable ==")
_s = _install([])
demo = P.LocalDemoProvider()
with mock.patch.object(
    service_module,
    "chat_with_failover",
    side_effect=lambda messages, tools=None: P.FailoverOutcome(
        result=P.ProviderResult(content="", provider="demo-local", model="demo-local"),
        provider=demo,
        errors=["mistral: au repos"],
        attempts=[],
        fell_back_to_demo=True,
    ),
):
    out_demo = service_module.study_result({"kind": "fetch", "data": {"text": "Anthropic annonce un nouveau modèle."}, "id": "r-demo"})
check("moteur indisponible → skipped", out_demo.get("status") == "skipped", json.dumps(out_demo))
check("moteur indisponible → retryable=true", out_demo.get("retryable") is True)

fp_veto = FakeProvider([
    json.dumps({"ok": True, "title": "Y", "category": "ia", "date": "2026-09-02",
                "summary": "rumeur.", "source": "?", "confidence": 0.9}),
    json.dumps({"approve": False, "json": {}, "confidence": 0.1, "issues": "non sourcée"}),
])
with mock.patch.object(service_module, "chat_with_failover", side_effect=fp_veto.failover):
    out_veto = service_module.study_result({"kind": "note", "data": {"content": "rumeur..."}, "id": "r-veto"})
check("rejet → retryable=false (ré-essayer ne changerait rien)",
      out_veto.get("status") == "rejected" and not out_veto.get("retryable"), json.dumps(out_veto))

# ------------------------------------------------------------------- 9 : auto-retry ----
print("== 9. retry_stale_studies : ré-étudie les échecs transitoires (filet anti-perte) ==")
_s = _install([])
stale = _s.add("research_results", {"kind": "fetch", "data": {"text": "Anthropic annonce un nouveau modèle."}, "status": "done"})
_s.update("research_results", stale["id"], {"study": {
    "status": "skipped", "reason": "moteur d'analyse indisponible", "retryable": True,
    "retried_at": 0, "retries": 0}})
not_retry = _s.add("research_results", {"kind": "note", "data": {"content": "x"}, "status": "done"})
_s.update("research_results", not_retry["id"], {"study": {
    "status": "rejected", "reason": "rejetée", "retryable": False, "retried_at": 0, "retries": 0}})
cooled = _s.add("research_results", {"kind": "note", "data": {"content": "y"}, "status": "done"})
_s.update("research_results", cooled["id"], {"study": {
    "status": "skipped", "reason": "moteur indisponible", "retryable": True,
    "retried_at": time.time(), "retries": 0}})
maxed = _s.add("research_results", {"kind": "note", "data": {"content": "z"}, "status": "done"})
_s.update("research_results", maxed["id"], {"study": {
    "status": "error", "reason": "erreur", "retryable": True,
    "retried_at": 0, "retries": service_module.RETRY_MAX_ATTEMPTS}})

captured: list[str] = []
def _fake_spawn(item, *, force=False):
    captured.append(item.get("id"))
    _s.update("research_results", item.get("id"), {"study": {
        "status": "added", "entry": {"title": "ré-étudié"}, "retryable": False,
        "retried_at": time.time(), "retries": 1}})

with mock.patch.object(service_module, "_spawn_study", side_effect=_fake_spawn):
    n1 = service_module.retry_stale_studies()
check("une seule ré-étude planifiée (seule la staled hors cooldown)", n1 == 1, f"n={n1} captured={captured}")
check("le bon résultat a été ré-étudié", captured == [stale["id"]], str(captured))
check("le cooldown bloque une ré-étude immédiate", service_module.retry_stale_studies() == 0)
captured.clear()
# après simulation du cooldown écoulé : le second échec transitoire est repris
_s.update("research_results", cooled["id"], {"study": {
    "status": "skipped", "reason": "moteur indisponible", "retryable": True,
    "retried_at": time.time() - service_module.RETRY_COOLDOWN_S - 1, "retries": 1}})
with mock.patch.object(service_module, "_spawn_study", side_effect=_fake_spawn):
    n2 = service_module.retry_stale_studies()
check("après le cooldown, l'autre échec transitoire est repris", n2 == 1 and captured == [cooled["id"]], f"n={n2} captured={captured}")

# ------------------------------------------------------------------- 10 : push ----
print("== 10. Un push Colab déclenche la ré-étude des échecs antérieurs ==")
_s = _install([])
with mock.patch.object(service_module, "_spawn_study") as spawn, \
     mock.patch.object(service_module, "retry_stale_studies") as retry:
    service_module.add_result("note", {"content": "nouveau push"}, task_id=None)
check("add_result planifie l'étude du nouveau résultat", spawn.call_count == 1, f"{spawn.call_count}")
check("add_result déclenche retry_stale_studies", retry.call_count == 1, f"{retry.call_count}")

# ------------------------------------------------------------------- 11 : skill ----
print("== 11. list_research_results : extrait compact, query, tâches en attente ==")
_s = _install([])
task_done = _s.add("research_tasks", {"kind": "search", "target": "dernier modèle anthropic",
                                      "reason": "question utilisateur", "by": "ai", "status": "done"})
task_pend = _s.add("research_tasks", {"kind": "deep", "target": "état de l'art agents auto-améliorants",
                                      "reason": "veille", "by": "ai", "status": "pending"})
r1 = _s.add("research_results", {"kind": "search", "task_id": task_done["id"], "status": "done",
    "data": {"results": [{"title": "Anthropic annonce Claude Opus 4.5",
                          "url": "https://www.anthropic.com/news/opus-4-5",
                          "snippet": "Nouveau modèle de raisonnement."}]}})
r2 = _s.add("research_results", {"kind": "fetch", "task_id": None, "status": "done",
    "data": {"text": "Un article sur les jeux vidéo rétro et leurs émulateurs."}})

with mock.patch.object(research_service, "retry_stale_studies"):
    all_res = skills.execute("list_research_results", {})
    q_res = skills.execute("list_research_results", {"query": "anthropic"})
    none_res = skills.execute("list_research_results", {"query": "zzznonexistent"})
check("les 2 résultats sont listés", all_res.get("count") == 2, json.dumps(all_res.get("count")))
check("extrait compact (pas le dump data brut)",
      all("data" not in r for r in all_res["results"]) and
      any("Claude Opus 4.5" in r.get("excerpt", "") for r in all_res["results"]),
      json.dumps(all_res["results"][:1])[:200])
check("la cible de la tâche est rattachée",
      any(r.get("target") == "dernier modèle anthropic" for r in all_res["results"]))
check("query : seul le résultat pertinent reste", [r["id"] for r in q_res["results"]] == [r1["id"]],
      json.dumps(q_res["results"]))
check("query sans correspondance → vide + note explicite",
      none_res["results"] == [] and "attente" in none_res.get("note", ""), none_res.get("note", ""))
check("la tâche en attente est visible (pending_tasks)",
      any(p["id"] == task_pend["id"] for p in all_res.get("pending_tasks", [])),
      json.dumps(all_res.get("pending_tasks")))

# ------------------------------------------------------------------- fin ----
_restore(_SNAP)
store_module.reset_store_cache()
print()
print(f"RÉSULTAT : {len(PASSED)} ✅ / {len(FAILED)} ❌")
if FAILED:
    print("ÉCHECS :")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
