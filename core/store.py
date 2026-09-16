"""Persistance des données.

Trois couches, même interface :
- LocalStore   : fichiers JSON dans core/data/ — fonctionne sans rien configurer
                 (dev local, démo). C'est le mode par défaut.
- GitHubStore  : un fichier JSON par collection dans un repo GitHub privé, via
                 l'API Contents — activé quand GITHUB_TOKEN + GITHUB_REPO sont
                 dans .env (voir docs/GITHUB-BACKEND.md).
- SupabaseStore : Postgres via l'API REST PostgREST — activé quand
                 SUPABASE_URL + SUPABASE_SERVICE_KEY sont dans .env.

Sélection via STORE_BACKEND : auto (défaut) | local | github | supabase.
En auto : supabase (si configuré) → github (si configuré) → local.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
import uuid
from typing import Any

import httpx

from core.ai.config import REPO_ROOT, env

DATA_DIR = os.path.join(REPO_ROOT, "core", "data")
_lock = threading.Lock()


# ---------------------------------------------------------------- Local ----
def _path(name: str) -> str:
    if name == "research_tasks":
        # Source de vérité unique des tâches de recherche : c'est ce fichier que
        # le notebook Colab télécharge et exécute (colab/main.py). L'emplacement
        # est surchargeable via RESEARCH_TASKS_PATH (chemin absolu ou relatif au
        # repo), utile pour pointer Colab vers un dossier précis.
        custom = (env("RESEARCH_TASKS_PATH") or "").strip()
        if custom:
            p = custom if os.path.isabs(custom) else os.path.join(REPO_ROOT, custom)
            return p if p.endswith(".json") else os.path.join(p, "tasks.json")
        return os.path.join(REPO_ROOT, "colab", "tasks.json")
    return os.path.join(DATA_DIR, f"{name}.json")


def _load(name: str, default):
    p = _path(name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return default


def _save(name: str, data) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    p = _path(name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


class LocalStore:
    backend = "local"

    def list(self, name: str, default=None):
        return _load(name, default if default is not None else [])

    def add(self, name: str, item: dict) -> dict:
        with _lock:
            items = self.list(name)
            item = dict(item)
            # UUID complet (32 hex) : valide côté Postgres (schéma Supabase en uuid),
            # contrairement à l'ancien hex[:12].
            item.setdefault("id", uuid.uuid4().hex)
            item.setdefault("created_at", time.time())
            items.append(item)
            _save(name, items)
            return item

    def update(self, name: str, item_id: str, patch: dict) -> dict | None:
        with _lock:
            items = self.list(name)
            for it in items:
                if str(it.get("id")) == str(item_id):
                    it.update(patch)
                    _save(name, items)
                    return it
        return None

    def find(self, name: str, **conds) -> dict | None:
        for it in reversed(self.list(name)):
            if all(str(it.get(k)) == str(v) for k, v in conds.items()):
                return it
        return None

    def seed_if_empty(self, name: str, seed: list) -> None:
        if not os.path.exists(_path(name)):
            _save(name, seed)


# ---------------------------------------------------------------- GitHub ----
class GitHubStore:
    """Base JSON hébergée dans un repo GitHub privé (API Contents).

    Un fichier par collection : {GITHUB_DIR}/{name}.json — sauf research_tasks,
    qui vit dans `RESEARCH_TASKS_PATH` du repo (défaut `colab/tasks.json`,
    même convention que le LocalStore, pour que le notebook Colab tombe sur le
    même fichier). Toute tâche créée — par l'IA ou par un humain — est donc
    synchronisée dans le repo de données à cet emplacement.

    Config (.env) : GITHUB_TOKEN (fine-grained PAT, Contents lecture+écriture
    sur ce seul repo), GITHUB_REPO (owner/repo), GITHUB_BRANCH (défaut main),
    GITHUB_DIR (défaut data), RESEARCH_TASKS_PATH (défaut colab/tasks.json).
    Guide complet : docs/GITHUB-BACKEND.md.

    Robustesse : lecture avec petit cache TTL (15 s, pour ne pas ralentir
    /api/status qui liste 4 collections), écritures en read-modify-write avec
    rejeu sur conflit de sha (409), verrou global comme le LocalStore.
    """

    backend = "github"
    READ_TTL = 15.0

    def __init__(self, client: httpx.Client | None = None):
        repo = (env("GITHUB_REPO") or "").strip().strip("/")
        token = (env("GITHUB_TOKEN") or "").strip()
        if not repo or "/" not in repo or not token:
            raise RuntimeError("GITHUB_REPO (owner/repo) + GITHUB_TOKEN requis pour le backend github.")
        self.repo = repo
        self.token = token
        self.branch = (env("GITHUB_BRANCH") or "main").strip() or "main"
        self.dir = (env("GITHUB_DIR") or "data").strip().strip("/") or "data"
        self._client = client  # injecté par les tests (httpx.MockTransport)
        self._cache: dict[str, tuple[float, Any]] = {}  # name -> (expiration, données)
        self._shas: dict[str, str | None] = {}  # name -> sha (None = fichier absent)

    # -- bas niveau ------------------------------------------------------
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _path(self, name: str) -> str:
        if name == "research_tasks":
            # Emplacement des tâches dans le repo de données : `research_tasks_path`
            # est le chemin choisi par l'utilisateur (ex. "colab/tasks.json" ou
            # "recherche/taches.json"), sinon `colab/tasks.json`. C'est CE fichier
            # que le notebook Colab constate (les tâches créées par l'IA ou par un
            # humain y sont écrites) — voir docs/GITHUB-BACKEND.md.
            custom_path = (env("RESEARCH_TASKS_PATH") or "").strip().strip("/")
            if custom_path:
                if custom_path.endswith(".json"):
                    return custom_path
                if "/" in custom_path:
                    return f"{custom_path.rstrip('/')}/research_tasks.json"
                return f"{custom_path}/research_tasks.json"
            return "colab/tasks.json"
        return f"{self.dir}/{name}.json"

    def _url(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{path}"

    def _request(self, method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", 15)
        if self._client is not None:
            return self._client.request(method, url, **kwargs)
        return httpx.request(method, url, **kwargs)

    @staticmethod
    def _encode(data) -> str:
        raw = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _decode(payload: dict):
        raw = base64.b64decode(payload.get("content") or "").decode("utf-8")
        return json.loads(raw)

    def _read_fresh(self, name: str) -> tuple[list, str | None]:
        """Lecture directe (sans cache TTL). Retourne (données, sha)."""
        r = self._request("GET", self._url(self._path(name)),
                          headers=self._headers(), params={"ref": self.branch})
        if r.status_code == 404:
            self._shas[name] = None
            return [], None
        r.raise_for_status()
        payload = r.json()
        self._shas[name] = payload.get("sha")
        try:
            data = self._decode(payload)
        except (ValueError, KeyError):
            data = []
        return data if isinstance(data, list) else [], self._shas[name]

    def _put(self, name: str, data: list, sha: str | None) -> tuple[bool, str]:
        """Écriture. Retourne (ok, \"\" | \"conflict\" | \"HTTP xxx\")."""
        body: dict[str, Any] = {
            "message": f"data: {name} ({len(data)} entrées)",
            "content": self._encode(data),
            "branch": self.branch,
        }
        if sha:
            body["sha"] = sha
        r = self._request("PUT", self._url(self._path(name)), headers=self._headers(), json=body)
        if r.status_code in (200, 201):
            try:
                self._shas[name] = r.json().get("content", {}).get("sha")
            except ValueError:
                self._shas.pop(name, None)
            return True, ""
        if r.status_code == 409:
            return False, "conflict"
        if r.status_code == 422:
            try:
                msg = str(r.json().get("message", ""))
            except ValueError:
                msg = ""
            if "sha" in msg.lower():
                return False, "conflict"
        return False, f"HTTP {r.status_code}"

    def _mutate(self, name: str, fn) -> Any:
        """Read-modify-write avec rejeu sur conflit (3 tentatives max)."""
        with _lock:
            last_err = "conflict"
            for _ in range(3):
                current, sha = self._read_fresh(name)
                new_data, result = fn(list(current))
                ok, err = self._put(name, new_data, sha)
                if ok:
                    self._cache[name] = (time.time() + self.READ_TTL, new_data)
                    return result
                last_err = err
                if err != "conflict":
                    break
            raise RuntimeError(f"GitHub store : écriture {name} impossible ({last_err}).")

    # -- interface Store -------------------------------------------------
    def list(self, name: str, default=None):
        default = default if default is not None else []
        cached = self._cache.get(name)
        if cached and cached[0] > time.time():
            return cached[1]
        try:
            data, sha = self._read_fresh(name)
        except httpx.HTTPStatusError:
            raise  # 401/403/5xx : erreur de config ou côté GitHub → bruyant, à corriger
        except httpx.HTTPError as exc:
            # Panne réseau/timeout uniquement : servir le défaut plutôt que de
            # mettre le site à genoux (le health-check Render, lui, ne touche
            # jamais au store — voir GET /health).
            print(f"[store] GitHub injoignable ({exc.__class__.__name__}) → défaut pour {name}.",
                  file=sys.stderr)
            return default
        if sha is None and isinstance(default, list) and default:
            # Fichier absent + seed fourni (cas de "knowledge") : on crée le
            # fichier dans le repo pour que la donnée y vive vraiment ensuite.
            # Best-effort : un échec réseau ne doit pas casser la lecture.
            try:
                ok, _ = self._put(name, default, None)
                if ok:
                    data = list(default)
            except Exception:
                pass
            if not data:
                return default
        self._cache[name] = (time.time() + self.READ_TTL, data)
        return data if sha is not None or not default else default

    def add(self, name: str, item: dict) -> dict:
        def _append(items: list):
            it = dict(item)
            it.setdefault("id", uuid.uuid4().hex)
            it.setdefault("created_at", time.time())
            items.append(it)
            return items, it

        return self._mutate(name, _append)

    def update(self, name: str, item_id: str, patch: dict) -> dict | None:
        def _patch(items: list):
            for it in items:
                if str(it.get("id")) == str(item_id):
                    it.update(patch)
                    return items, it
            return items, None

        return self._mutate(name, _patch)

    def find(self, name: str, **conds) -> dict | None:
        for it in reversed(self.list(name)):
            if all(str(it.get(k)) == str(v) for k, v in conds.items()):
                return it
        return None

    def seed_if_empty(self, name: str, seed: list) -> None:
        data, sha = self._read_fresh(name)
        if sha is None or not data:
            ok, err = self._put(name, seed, sha)
            if ok:
                self._cache[name] = (time.time() + self.READ_TTL, list(seed))
            else:
                raise RuntimeError(f"GitHub store : seed {name} impossible ({err}).")


# ---------------------------------------------------------------- Supabase ----
class SupabaseStore:
    """Client minimal PostgREST (pas de SDK requis)."""

    backend = "supabase"

    def __init__(self):
        self.base = (env("SUPABASE_URL") or "").rstrip("/") + "/rest/v1"
        self.key = env("SUPABASE_SERVICE_KEY") or env("SUPABASE_ANON_KEY") or ""

    def _headers(self, extra: dict | None = None):
        h = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if extra:
            h.update(extra)
        return h

    def list(self, table: str, default=None):
        r = httpx.get(f"{self.base}/{table}", headers=self._headers(), params={"select": "*"}, timeout=15)
        r.raise_for_status()
        return r.json()

    def add(self, table: str, item: dict) -> dict:
        payload = dict(item)
        payload.pop("id", None)  # généré côté Postgres
        r = httpx.post(
            f"{self.base}/{table}",
            headers=self._headers({"Prefer": "return=representation"}),
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else payload

    def update(self, table: str, item_id: str, patch: dict) -> dict | None:
        r = httpx.patch(
            f"{self.base}/{table}?id=eq.{item_id}",
            headers=self._headers({"Prefer": "return=representation"}),
            json=patch,
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None

    def find(self, table: str, **conds) -> dict | None:
        filt = " and ".join(f"{k}=eq.{v}" for k, v in conds.items())
        r = httpx.get(f"{self.base}/{table}?select=*&{filt}", headers=self._headers(), timeout=15)
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None

    def seed_if_empty(self, table: str, seed: list) -> None:
        try:
            if not self.list(table):
                for item in seed:
                    self.add(table, item)
        except Exception:
            pass  # seeding best-effort ; le schéma SQL gère le reste


# ---------------------------------------------------------------- Sélection ----
_store_instance = None


def _supabase_configured() -> bool:
    return bool(env("SUPABASE_URL") and (env("SUPABASE_SERVICE_KEY") or env("SUPABASE_ANON_KEY")))


def _github_configured() -> bool:
    repo = (env("GITHUB_REPO") or "").strip()
    return bool(repo and "/" in repo and (env("GITHUB_TOKEN") or "").strip())


def get_store():
    """Retourne le backend actif (mémorisé par processus).

    STORE_BACKEND = auto (défaut) | local | github | supabase.
    En auto : supabase (si configuré) → github (si configuré) → local.
    Un backend explicite mal configuré retombe sur local avec un avertissement
    (mieux que de faire planter toutes les requêtes API).
    """
    global _store_instance
    want = (env("STORE_BACKEND") or "auto").strip().lower()
    if want == "auto":
        if _supabase_configured():
            want = "supabase"
        elif _github_configured():
            want = "github"
        else:
            want = "local"
    if _store_instance is None or getattr(_store_instance, "backend", "local") != want:
        cls = {"supabase": SupabaseStore, "github": GitHubStore, "local": LocalStore}.get(want, LocalStore)
        try:
            _store_instance = cls()
        except Exception as exc:
            print(f"[store] backend '{want}' inutilisable ({exc}) → repli sur local.", file=sys.stderr)
            _store_instance = LocalStore()
    return _store_instance


def reset_store_cache() -> None:
    """Oublie l'instance mémorisée (tests, ou relecture du .env à chaud)."""
    global _store_instance
    _store_instance = None
