"""Tests du backend GitHub (repo privé comme base JSON).

Aucun appel réseau : un `httpx.MockTransport` simule l'API Contents de GitHub
(GET/PUT avec sha, 404, 409 de conflit) avec un « repo » en mémoire.

Lancer :  python tests/test_github_store.py     (aucune dépendance de test)
"""
from __future__ import annotations

import base64
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import httpx  # noqa: E402

from core import store as store_module  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


# ---------------------------------------------------------------------------
# Faux GitHub : repo en mémoire {chemin: (contenu_json_str, sha)}
# ---------------------------------------------------------------------------
class FakeGitHub:
    def __init__(self):
        self.files: dict[str, tuple[str, str]] = {}
        self.calls: list[tuple[str, str]] = []  # (méthode, chemin)
        self.fail_next_put_with_409 = 0
        self._n = 0

    def _sha(self) -> str:
        self._n += 1
        return f"sha{self._n:04d}"

    def handler(self, request: httpx.Request) -> httpx.Response:
        prefix = "/repos/octo/data-priv/contents/"
        assert request.url.path.startswith(prefix), request.url.path
        path = request.url.path[len(prefix):]
        auth = request.headers.get("authorization", "")
        if auth != "Bearer ghp_test":
            return httpx.Response(401, json={"message": "Bad credentials"}, request=request)
        self.calls.append((request.method, path))
        if request.method == "GET":
            if path not in self.files:
                return httpx.Response(404, json={"message": "Not Found"}, request=request)
            content, sha = self.files[path]
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            return httpx.Response(200, json={"sha": sha, "content": b64}, request=request)
        if request.method == "PUT":
            body = json.loads(request.content.decode("utf-8"))
            if self.fail_next_put_with_409 > 0:
                self.fail_next_put_with_409 -= 1
                return httpx.Response(409, json={"message": "does not match"}, request=request)
            if path in self.files and body.get("sha") != self.files[path][1]:
                return httpx.Response(409, json={"message": "sha does not match"}, request=request)
            if path not in self.files and body.get("sha"):
                return httpx.Response(422, json={"message": "sha present but no file"}, request=request)
            raw = base64.b64decode(body["content"]).decode("utf-8")
            json.loads(raw)  # doit être du JSON valide
            new_sha = self._sha()
            self.files[path] = (raw, new_sha)
            return httpx.Response(200 if body.get("sha") else 201,
                                  json={"content": {"sha": new_sha}}, request=request)
        return httpx.Response(405, json={"message": "nope"}, request=request)


def make_store(fake: FakeGitHub) -> store_module.GitHubStore:
    os.environ["GITHUB_TOKEN"] = "ghp_test"
    os.environ["GITHUB_REPO"] = "octo/data-priv"
    os.environ.pop("GITHUB_BRANCH", None)
    os.environ.pop("GITHUB_DIR", None)
    client = httpx.Client(transport=httpx.MockTransport(fake.handler))
    return store_module.GitHubStore(client=client)


print("== GitHubStore : lectures / écritures ==")
fake = FakeGitHub()
s = make_store(fake)

check("list sur repo vide → défaut", s.list("dev_requests") == [])
check("GET sur data/dev_requests.json", fake.calls == [("GET", "data/dev_requests.json")], str(fake.calls))

item = s.add("dev_requests", {"title": "hello", "status": "open"})
check("add retourne id + created_at", bool(item.get("id")) and "created_at" in item)
check("création sans sha (201)", len(item["id"]) == 32)
stored = json.loads(fake.files["data/dev_requests.json"][0])
check("fichier créé avec l'item", len(stored) == 1 and stored[0]["title"] == "hello")

item2 = s.add("dev_requests", {"title": "deux"})
check("2e add append", len(json.loads(fake.calls and fake.files["data/dev_requests.json"][0])) == 2)
check("ids uniques", item["id"] != item2["id"])

upd = s.update("dev_requests", item["id"], {"status": "done"})
check("update existant", upd is not None and upd["status"] == "done")
check("update absent → None", s.update("dev_requests", "nope", {"a": 1}) is None)
check("find", (s.find("dev_requests", title="deux") or {}).get("id") == item2["id"])

print("== research_tasks → colab/tasks.json ==")
s.add("research_tasks", {"kind": "search", "target": "x"})
check("tasks dans colab/tasks.json", "colab/tasks.json" in fake.files)

print("== seed auto de knowledge ==")
fake2 = FakeGitHub()
s2 = make_store(fake2)
seed = [{"title": "Zelda", "date": "1986-02-21"}]
check("list knowledge absent → seed", s2.list("knowledge", default=seed) == seed)
check("seed persisté dans le repo", json.loads(fake2.files["data/knowledge.json"][0]) == seed)

print("== conflit 409 → rejeu ==")
fake3 = FakeGitHub()
s3 = make_store(fake3)
s3.add("dev_requests", {"title": "a"})
fake3.fail_next_put_with_409 = 1  # le prochain PUT échoue 1 fois, puis passe
itm = s3.add("dev_requests", {"title": "b"})
check("add malgré un 409 (rejeu)", itm["title"] == "b")
check("les 2 items présents", len(json.loads(fake3.files["data/dev_requests.json"][0])) == 2)

print("== cache TTL lectures ==")
fake4 = FakeGitHub()
s4 = make_store(fake4)
s4.add("dev_requests", {"title": "a"})
n_calls = len(fake4.calls)
s4.list("dev_requests")
s4.list("dev_requests")
check("2 listes consécutives = 0 appel HTTP (cache)", len(fake4.calls) == n_calls, str(fake4.calls))
check("auth Bearer sur chaque appel", True)  # le fake rejette en 401 sinon

print("== sélection du backend ==")
os.environ.pop("SUPABASE_URL", None)
os.environ["GITHUB_TOKEN"] = "ghp_test"
os.environ["GITHUB_REPO"] = "octo/data-priv"
os.environ["STORE_BACKEND"] = "auto"
store_module.reset_store_cache()
check("auto + github configuré → GitHubStore", store_module.get_store().backend == "github")
os.environ.pop("GITHUB_TOKEN", None)
os.environ.pop("GITHUB_REPO", None)
store_module.reset_store_cache()
check("auto sans rien → LocalStore", store_module.get_store().backend == "local")
os.environ["STORE_BACKEND"] = "github"  # forcé mais mal configuré
store_module.reset_store_cache()
check("github forcé KO → repli local (pas de crash)", store_module.get_store().backend == "local")
os.environ.pop("STORE_BACKEND", None)
store_module.reset_store_cache()

print("== panne réseau → défaut (pas de crash), 401 → bruyant ==")


def _boom(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("dns down", request=request)


os.environ["GITHUB_TOKEN"] = "ghp_test"
os.environ["GITHUB_REPO"] = "octo/data-priv"
s_boom = store_module.GitHubStore(client=httpx.Client(transport=httpx.MockTransport(_boom)))
check("list sur panne réseau → défaut", s_boom.list("dev_requests", default=[{"a": 1}]) == [{"a": 1}])


def _denied(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"message": "Bad credentials"}, request=request)


s_401 = store_module.GitHubStore(client=httpx.Client(transport=httpx.MockTransport(_denied)))
try:
    s_401.list("dev_requests")
    check("401 → exception (reste bruyant)", False)
except httpx.HTTPStatusError:
    check("401 → exception (reste bruyant)", True)

os.environ.pop("GITHUB_TOKEN", None)
os.environ.pop("GITHUB_REPO", None)
store_module.reset_store_cache()

print("\n" + "=" * 68)
print(f"RÉSULTAT : {len(PASSED)} vérifications OK, {len(FAILED)} en échec")
if FAILED:
    for item in FAILED:
        print("  ✗ " + item)
    sys.exit(1)
print("Tout est vert ✅")
