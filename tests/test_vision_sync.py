"""Tests de la vision (blocs image_url) et de la synchro des tâches de recherche.

Aucun appel réseau : on vérifie
- la normalisation des messages multimédia côté provider (`_build_messages`),
- la validation des images côté serveur (`_validate_images`),
- que la réponse « vision » ne devient jamais une bulle vide en démo,
- que RESEARCH_TASKS_PATH déplace le fichier des tâches (local + GitHub mock).

Lancer :  python tests/test_vision_sync.py
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
from fastapi import HTTPException  # noqa: E402

from core import store as store_module  # noqa: E402
from core.ai import providers as P  # noqa: E402
from core.server import _validate_images  # noqa: E402
from core.ai.chat import _last_user_text, _textify_user_messages  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


print("== 1. Normalisation des messages vision (provider) ==")
prov = P.OpenAICompatProvider("mistral", "https://x.invalid/v1", "k", ("ministral-8b-latest",), min_interval=0.0)
msgs = prov._build_messages([
    {"role": "system", "content": "sys"},
    {"role": "user", "content": [
        {"type": "text", "text": "décris"},
        {"type": "image_url", "image_url": {"url": "https://e.com/a.png"}},
    ]},
    {"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]},
    {"role": "user", "content": "bonjour"},
])
check("system inchangé", msgs[0]["content"] == "sys")
check("texte + image transmis tels quels", msgs[1]["content"][0]["type"] == "text" and msgs[1]["content"][1]["type"] == "image_url")
check("image seule → préfixe texte conservé + image derrière",
      msgs[2]["content"][0]["text"] == "[image]" and msgs[2]["content"][1]["type"] == "image_url")
check("message texte pur inchangé", msgs[3]["content"] == "bonjour")

print("== 2. Validation des images côté serveur ==")
tiny_png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
data_url = "data:image/png;base64," + tiny_png
_validate_images([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://e.com/x.png"}}]}])
check("URL http(s) acceptée", True)


def _reject(msgs) -> str:
    try:
        _validate_images(msgs)
        return ""
    except HTTPException as exc:
        return exc.detail


check("data-URL base64 valide acceptée", _reject([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": data_url}}]}]) == "")
check("trop d'images refusé", "max 4" in _reject([{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": f"https://e.com/i{i}.png"}} for i in range(5)
]}]))
check("MIME non image refusé", "non supporté" in _reject([{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": "data:text/plain;base64,aGVsbG8="}}
]}]))
check("base64 invalide refusé", "base64 invalide" in _reject([{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,###"}}
]}]))
big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * (3 * 1024 * 1024)).decode()
check("image trop lourde refusée", "2 Mo" in _reject([{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + big}}
]}]))

print("== 3. Tour vision : extraction du texte / conversion ==")
check("_last_user_text voit le texte des blocs",
      "regarde" in _last_user_text([{"role": "user", "content": [{"type": "text", "text": "regarde"}, {"type": "image_url", "image_url": {"url": "https://e.com/a.png"}}]}]))
converted = _textify_user_messages([{"role": "user", "content": [{"type": "text", "text": "regarde"}, {"type": "image_url", "image_url": {"url": "https://e.com/a.png"}}]}])
check("_textify_user_messages → contenu texte (image marquée en texte)",
      isinstance(converted[0]["content"], str) and "regarde" in converted[0]["content"] and "[image" in converted[0]["content"])

print("== 4. Réponse vision jamais vide (démo locale) ==")
from core.ai.chat import handle_chat  # noqa: E402

for key in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)
P.reset_chain_cache() if hasattr(P, "reset_chain_cache") else None
out = handle_chat([{"role": "user", "content": [{"type": "text", "text": "décris"}, {"type": "image_url", "image_url": {"url": data_url}}]}])
check("la démo répond un texte explicite (pas une bulle vide)", len(out.get("reply", "")) > 10, out.get("reply", ""))
check("la démo annonce la vision indisponible", "vision" in out.get("reply", "").lower())

print("== 5. RESEARCH_TASKS_PATH (local) ==")
tmp = os.path.join(REPO_ROOT, "core", "data", "_tmp_test_tasks_dir")
os.makedirs(tmp, exist_ok=True)
os.environ["RESEARCH_TASKS_PATH"] = "core/data/_tmp_test_tasks_dir/research/tasks.json"
from core.store import _path  # noqa: E402

resolved = _path("research_tasks")
check("le chemin local suit RESEARCH_TASKS_PATH", "research/tasks.json" in resolved.replace("\\", "/"), resolved)
os.environ.pop("RESEARCH_TASKS_PATH", None)
check("défaut local = colab/tasks.json", _path("research_tasks").replace("\\", "/").endswith("colab/tasks.json"))
import shutil  # noqa: E402

shutil.rmtree(tmp, ignore_errors=True)

print("== 6. RESEARCH_TASKS_PATH (GitHub mock) ==")


class FakeGitHub:
    def __init__(self):
        self.files = {}
        self._n = 0

    def _sha(self):
        self._n += 1
        return f"sha{self._n:04d}"

    def handler(self, request: httpx.Request) -> httpx.Response:
        prefix = "/repos/octo/data-priv/contents/"
        path = request.url.path[len(prefix):]
        if request.method == "GET":
            if path not in self.files:
                return httpx.Response(404, json={"message": "Not Found"}, request=request)
            content, sha = self.files[path]
            b64 = base64.b64encode(content.encode()).decode()
            return httpx.Response(200, json={"sha": sha, "content": b64}, request=request)
        if request.method == "PUT":
            body = json.loads(request.content)
            raw = base64.b64decode(body["content"]).decode()
            new_sha = self._sha()
            self.files[path] = (raw, new_sha)
            return httpx.Response(200 if body.get("sha") else 201, json={"content": {"sha": new_sha}}, request=request)
        return httpx.Response(405, json={"message": "nope"}, request=request)


os.environ["GITHUB_TOKEN"] = "ghp_test"
os.environ["GITHUB_REPO"] = "octo/data-priv"
os.environ["RESEARCH_TASKS_PATH"] = "recherche/taches.json"
os.environ.pop("GITHUB_DIR", None)
os.environ.pop("GITHUB_BRANCH", None)
fake = FakeGitHub()
gs = store_module.GitHubStore(client=httpx.Client(transport=httpx.MockTransport(fake.handler)))
check("_path github suit RESEARCH_TASKS_PATH", gs._path("research_tasks") == "recherche/taches.json", gs._path("research_tasks"))
check("les autres collections restent dans GITHUB_DIR", gs._path("dev_requests") == "data/dev_requests.json")
item = gs.add("research_tasks", {"kind": "search", "target": "x", "by": "ai", "status": "pending"})
check("la tâche (auteur ai) est écrite au chemin voulu", "recherche/taches.json" in fake.files)
stored = json.loads(fake.files["recherche/taches.json"][0])
check("la tâche synchronisée contient by=ai + status", stored[0].get("by") == "ai" and stored[0].get("status") == "pending")
gs2_item = gs.add("research_tasks", {"kind": "fetch", "target": "https://e.com", "by": "human", "status": "pending"})
check("une tâche humaine part au même endroit", len(json.loads(fake.files["recherche/taches.json"][0])) == 2)
# chemin « dossier seul »
gs._path  # noqa: B018
os.environ["RESEARCH_TASKS_PATH"] = "recherche"
check("dossier seul → research_tasks.json", store_module.GitHubStore(client=httpx.Client(transport=httpx.MockTransport(fake.handler)))._path("research_tasks") == "recherche/research_tasks.json")
os.environ.pop("RESEARCH_TASKS_PATH", None)
check("défaut github = colab/tasks.json", store_module.GitHubStore(client=httpx.Client(transport=httpx.MockTransport(fake.handler)))._path("research_tasks") == "colab/tasks.json")

os.environ.pop("GITHUB_TOKEN", None)
os.environ.pop("GITHUB_REPO", None)
os.environ.pop("RESEARCH_TASKS_PATH", None)
store_module.reset_store_cache()

print("\n" + "=" * 68)
print(f"RÉSULTAT : {len(PASSED)} vérifications OK, {len(FAILED)} en échec")
if FAILED:
    for item in FAILED:
        print("  ✗ " + item)
    sys.exit(1)
print("Tout est vert ✅")
