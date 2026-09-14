"""Persistance des données.

Deux couches :
- LocalStore  : fichiers JSON dans core/data/ — fonctionne sans rien configurer
                (dev local, démo). C'est le mode par défaut.
- SupabaseStore : Postgres via l'API REST PostgREST — activé automatiquement
                quand SUPABASE_URL + SUPABASE_SERVICE_KEY sont dans .env.

Même interface pour les deux, donc basculer vers Supabase ne change rien au reste.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

import httpx

from core.ai.config import REPO_ROOT, env

DATA_DIR = os.path.join(REPO_ROOT, "core", "data")
_lock = threading.Lock()


# ---------------------------------------------------------------- Local ----
def _path(name: str) -> str:
    if name == "research_tasks":
        # Source de vérité unique des tâches de recherche : c'est ce fichier que
        # le notebook Colab télécharge et exécute (colab/main.py).
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
    def list(self, name: str, default=None):
        return _load(name, default if default is not None else [])

    def add(self, name: str, item: dict) -> dict:
        with _lock:
            items = self.list(name)
            item = dict(item)
            item.setdefault("id", uuid.uuid4().hex[:12])
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


# ---------------------------------------------------------------- Supabase ----
class SupabaseStore:
    """Client minimal PostgREST (pas de SDK requis)."""

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


def get_store():
    if env("SUPABASE_URL") and (env("SUPABASE_SERVICE_KEY") or env("SUPABASE_ANON_KEY")):
        return SupabaseStore()
    return LocalStore()
