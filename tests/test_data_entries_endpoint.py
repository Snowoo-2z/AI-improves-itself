"""Tests de l'endpoint d'écriture explicite de la base de connaissances
(`POST /api/data/entries`), utilisé par l'analyseur de discussions Colab.

Sans réseau : TestClient (ASGI en mémoire), backend local isolé
(snapshot/suppression/restauration de core/data/knowledge.json, comme
test_study_result.py). On vérifie :
- ajout d'une entrée nouvelle (les 5 champs de la base uniquement),
- titre existant → mise à jour (pas de doublon, id conservé),
- summary identique → doublon ignoré,
- date non ISO → nulle (portabilité Supabase),
- entrée invalide (titre vide) → 422 pydantic,
- bilan {added, updated, skipped, counts} cohérent.

Lancer :  python tests/test_data_entries_endpoint.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

TMP = tempfile.mkdtemp(prefix="aiis_data_entries_test_")
_ORIG_BACKEND = os.environ.get("STORE_BACKEND")
os.environ["STORE_BACKEND"] = "local"  # jamais de backend distant en test

from fastapi.testclient import TestClient  # noqa: E402

from core import store as store_module  # noqa: E402
from core.server import app  # noqa: E402

client = TestClient(app)

FAILED: list[str] = []
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


# Base locale isolée : snapshot de knowledge.json (le seed y vit — s'il
# manquait, le défaut `_knowledge_seed()` serait vide) + restauration en fin.
KNOWLEDGE_PATH = store_module._path("knowledge")
_snapshot = open(KNOWLEDGE_PATH, encoding="utf-8").read() if os.path.exists(KNOWLEDGE_PATH) else None
assert _snapshot is not None, "core/data/knowledge.json (seed) manquant dans le repo"
store_module.reset_store_cache()

print("== 1. État initial (seed) ==")
r = client.get("/api/data/entries")
check("GET /api/data/entries → 200", r.status_code == 200)
initial = r.json()
check("seed présent (Zelda + Mistral…)", isinstance(initial.get("entries"), list) and initial["count"] >= 5,
      str(initial.get("count")))
check("seed contient « Mistral AI »", any(e.get("title") == "Mistral AI" for e in initial["entries"]))

print("== 2. Ajout d'une entrée nouvelle ==")
payload = {
    "entries": [{
        "title": "Tears of the Kingdom (vérifié)",
        "category": "jeux-vidéo",
        "date": "2023-05-12",
        "summary": "Suite de Breath of the Wild, sortie le 12 mai 2023 sur Switch.",
        "source": "https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Tears_of_the_Kingdom",
    }],
    "updated_by": "colab-analyseur",
    "note": "test",
}
r = client.post("/api/data/entries", json=payload)
check("POST → 200", r.status_code == 200, r.text[:200])
body = r.json()
check("added=1", body.get("counts", {}).get("added") == 1, json.dumps(body.get("counts")))
check("updated=0", body.get("counts", {}).get("updated") == 0)
check("provenance renvoyée", body.get("updated_by") == "colab-analyseur")
after = client.get("/api/data/entries").json()["entries"]
new_entry = next((e for e in after if e.get("title") == "Tears of the Kingdom (vérifié)"), None)
check("entrée visible via GET", new_entry is not None)
if new_entry:
    check("les 5 champs + id seulement", set(new_entry) <= {"id", "title", "category", "date", "summary", "source", "created_at"},
          str(set(new_entry)))
    check("source = URL de la preuve", new_entry.get("source", "").startswith("https://"))

print("== 3. Titre existant → mise à jour (pas de doublon) ==")
r = client.post("/api/data/entries", json={
    "entries": [{
        "title": "mistral ai",  # normalisé : identique à « Mistral AI »
        "category": "ia",
        "date": "2023-09-01",
        "summary": "Lab d'IA français — résumé CORRIGÉ par l'analyseur.",
        "source": "colab-analyseur",
    }],
    "updated_by": "colab-analyseur",
})
check("POST → 200", r.status_code == 200, r.text[:200])
body = r.json()
check("updated=1 (normalisation titre insensible à la casse/espaces)",
      body.get("counts", {}).get("updated") == 1, json.dumps(body.get("counts")))
check("added=0", body.get("counts", {}).get("added") == 0)
after = client.get("/api/data/entries").json()["entries"]
mistral = [e for e in after if e.get("title") == "Mistral AI"]
check("une seule entrée « Mistral AI » (aucune réinsertion)", len(mistral) == 1, str(len(mistral)))
if mistral:
    check("summary corrigé EN PLACE (entrée seed sans id, via update_first)",
          "CORRIGÉ" in mistral[0].get("summary", ""))
    check("source remplacée", mistral[0].get("source") == "colab-analyseur")
# aucune entrée ORPHILINE mal patchée (le bug : update(None) touchait la 1re
# entrée sans id — ici « The Legend of Zelda » doit rester intacte)
zelda = next((e for e in after if e.get("title") == "The Legend of Zelda"), None)
check("la 1re entrée du seed (sans id) reste intacte",
      zelda is not None and zelda.get("date") == "1986-02-21" and "Premier Zelda" in zelda.get("summary", ""),
      json.dumps(zelda or {})[:160])

print("== 4. Doublon identique → ignoré ==")
r = client.post("/api/data/entries", json={
    "entries": [{
        "title": "Mistral AI",
        "category": "ia",
        "date": "2023-09-01",
        "summary": "Lab d'IA français — résumé CORRIGÉ par l'analyseur.",
        "source": "colab-analyseur",
    }],
})
body = r.json()
check("skipped=1", body.get("counts", {}).get("skipped") == 1, json.dumps(body.get("counts")))
check("raison de saut fournie", bool(body.get("skipped", [{}])[0].get("reason")))
after = client.get("/api/data/entries").json()["entries"]
check("pas de doublon créé", len([e for e in after if e.get("title") == "Mistral AI"]) == 1)

print("== 5. Doublon par summary (titre différent) → ignoré ==")
r = client.post("/api/data/entries", json={
    "entries": [{
        "title": "Autre titre pour la même info",
        "category": "ia",
        "date": "",
        "summary": "Lab d'IA français — résumé CORRIGÉ par l'analyseur.",
        "source": "colab-analyseur",
    }],
})
body = r.json()
check("skipped=1 (summary déjà présent)", body.get("counts", {}).get("skipped") == 1, json.dumps(body.get("counts")))

print("== 6. Date non ISO → nulle (portabilité Supabase) ==")
r = client.post("/api/data/entries", json={
    "entries": [{
        "title": "Entrée sans date valide",
        "category": "test",
        "date": "hier",
        "summary": "Une info sans date ISO.",
        "source": "colab-analyseur",
    }],
})
check("POST → 200", r.status_code == 200, r.text[:200])
entry = r.json().get("added", [{}])[0]
check("date → null", entry.get("date") is None, json.dumps(entry)[:200])

print("== 7. Entrées invalides ==")
r = client.post("/api/data/entries", json={"entries": [{"title": "  ", "summary": "x"}]})
body = r.json() if r.status_code == 200 else {}
check("titre vide après strip → sautée (le lot passe)",
      r.status_code == 200 and body.get("counts", {}).get("skipped") == 1, str(r.status_code) + " " + r.text[:120])
r = client.post("/api/data/entries", json={"entries": [{"title": "ok"}]})
check("summary manquant → 422", r.status_code == 422, str(r.status_code))
r = client.post("/api/data/entries", json={"entries": []})
check("liste vide → 422", r.status_code == 422, str(r.status_code))

print("== 8. Batch mixte (1 ajout + 1 update + 1 doublon) ==")
r = client.post("/api/data/entries", json={
    "entries": [
        {"title": "Batch Ajout", "category": "test", "date": "", "summary": "Nouvelle info.", "source": "colab-analyseur"},
        {"title": "Mistral AI", "category": "ia", "date": "2023-09-01",
         "summary": "Lab d'IA français — résumé CORRIGÉ v2.", "source": "colab-analyseur"},
        {"title": "Batch Ajout", "category": "test", "date": "", "summary": "Nouvelle info.", "source": "colab-analyseur"},
    ],
    "updated_by": "colab-analyseur",
})
check("POST → 200", r.status_code == 200, r.text[:200])
counts = r.json().get("counts", {})
check("added=1 / updated=1 / skipped=1",
      counts.get("added") == 1 and counts.get("updated") == 1 and counts.get("skipped") == 1,
      json.dumps(counts))

# ------------------------------------------------------------------- fin ----
if _snapshot is None:
    if os.path.exists(KNOWLEDGE_PATH):
        os.remove(KNOWLEDGE_PATH)
else:
    with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as fh:
        fh.write(_snapshot)
store_module.reset_store_cache()
if _ORIG_BACKEND is None:
    os.environ.pop("STORE_BACKEND", None)
else:
    os.environ["STORE_BACKEND"] = _ORIG_BACKEND
shutil.rmtree(TMP, ignore_errors=True)

print()
print(f"RÉSULTAT : {len(PASSED)} ✅ / {len(FAILED)} ❌")
if FAILED:
    print("ÉCHECS :")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
