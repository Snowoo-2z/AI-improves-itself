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
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core import store as store_module  # noqa: E402
from core.ai import providers as P  # noqa: E402
from core.prompt_system import registry  # noqa: E402
from core.research import service as service_module  # noqa: E402
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
