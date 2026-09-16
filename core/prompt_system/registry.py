"""Prompt système versionné — le cœur du concept.

Chaque prompt est un fichier JSON (core/prompt_system/prompts/*.json) :
  { id, scope, version, content, keywords, history: [...] }

- `scope: "global"`      → toujours chargé (prompt principal).
- `scope: "<spécialisé>"` → garde-fou : chargé uniquement si un des
  `keywords` apparaît dans le message utilisateur.
- L'IA peut modifier le `content` via la skill `modify_prompt_system` :
  version incrémentée, historique conservé, notification au dev (/request).
- Les humains peuvent aussi éditer (endpoint POST) et tout est réversible
  depuis l'historique (page /prompt du site).
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

from core.ai.config import REPO_ROOT, env

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
MAX_HISTORY = 30


def _prompt_file(prompt_id: str) -> str:
    return os.path.join(PROMPTS_DIR, f"{prompt_id}.json")


def load_all() -> dict[str, dict]:
    prompts: dict[str, dict] = {}
    if not os.path.isdir(PROMPTS_DIR):
        return prompts
    for fn in sorted(os.listdir(PROMPTS_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(PROMPTS_DIR, fn), "r", encoding="utf-8") as fh:
            p = json.load(fh)
        prompts[p["id"]] = p
    return prompts


def get_current(prompt_id: str = "main") -> dict:
    prompts = load_all()
    if prompt_id not in prompts:
        raise KeyError(f"prompt inconnu : {prompt_id}")
    return prompts[prompt_id]


def save_prompt(p: dict) -> None:
    path = _prompt_file(p["id"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(p, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def select_for_user_input(text: str) -> list[dict]:
    """Garde-fous : choisir quels prompts charger selon les mots-clés."""
    text_l = text.lower()
    chosen: list[dict] = []
    for p in load_all().values():
        if p.get("scope") == "global":
            chosen.append(p)
            continue
        if any(k in text_l for k in p.get("keywords", [])):
            chosen.append(p)
    chosen.sort(key=lambda p: (p.get("scope") != "global", p["id"]))
    return chosen


def current_date_header() -> str:
    """Date du jour injectée dans le prompt système — l'IA ne la connaît pas.

    Sans elle, un modèle ne sait pas « aujourd'hui » : c'est exactement le défaut
    historique du projet (question « dernier Zelda » → l'IA a répondu avec le
    jeu de 1986, incapable de se situer en 2026). Le fuseau suit le serveur.
    """
    try:
        now = datetime.now().astimezone()
    except Exception:  # noqa: BLE001
        # datetime.now().astimezone() peut échouer sur un système sans tz local.
        now = datetime.now()
    return (
        "## DATE DU JOUR (aujourd'hui pour toi, ne l'ignore jamais)\n"
        f"Nous sommes le {now.strftime('%A %d %B %Y')}, "
        f"{now.strftime('%H:%M')} (fuseau du serveur ; "
        f"nom système du fuseau : {now.tzinfo or 'inconnu'}). "
        "Quand une info a une date, compare-la à aujourd'hui : « le plus récent », "
        "« le dernier » signifient le plus proche de cette date."
    )


def assemble_system_prompt(chosen: list[dict]) -> str:
    """Assembler le prompt système final (global + modules spécialisés + date)."""
    parts: list[str] = [current_date_header()]
    for p in chosen:
        header = f"## PROMPT [{p['id']} · {p.get('scope', 'global')} · v{p.get('version', 1)}]"
        parts.append(f"{header}\n{p['content']}")
    return "\n\n---\n\n".join(parts)


def _sanitized(content: str) -> str | None:
    """Garde-fou sécurité : refuser un prompt contenant une clé API."""
    if len(content) < 40 or len(content) > 12000:
        return "Contenu refusé : longueur hors limites (40 à 12 000 caractères)."
    for key in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "SUPABASE_SERVICE_KEY"):
        value = env(key)
        if value and len(value) > 8 and value in content:
            return "Contenu refusé : une clé API a été détectée dans le prompt."
    if re.search(r"\b(api[_-]?key|sk-[A-Za-z0-9]{16,})\b", content) and re.search(r"=\s*['\"]?[A-Za-z0-9_-]{16,}", content):
        return "Contenu refusé : motif de clé API détecté dans le prompt."
    return None


def apply_modification(
    scope: str,
    new_content: str,
    reason: str,
    author: str = "ai",
    trigger: str = "auto",
) -> dict:
    """Appliquer une modification du prompt système (IA ou humain).

    - version incrémentée, historique conservé (MAX_HISTORY entrées)
    - garde-fou anti-fuite de clés API
    - notification dans la file /request (type prompt_update)
    Retourne le prompt mis à jour.
    """
    from core import store  # import local pour éviter la dépendance circulaire

    s = store.get_store()
    prompt = get_current(scope)
    refusal = _sanitized(new_content)
    if refusal:
        raise PermissionError(refusal)

    old_version = prompt.get("version", 1)
    prompt.setdefault("history", []).append(
        {
            "version": old_version,
            "content": prompt.get("content", ""),
            "reason": reason,
            "trigger": trigger,
            "author": author,
            "at": time.time(),
        }
    )
    prompt["history"] = prompt["history"][-MAX_HISTORY:]
    prompt["version"] = old_version + 1
    prompt["content"] = new_content.strip()
    prompt["updated_at"] = time.time()
    prompt["updated_by"] = author
    save_prompt(prompt)

    s.add(
        "dev_requests",
        {
            "title": f"[{'IA' if author == 'ai' else 'Humain'}] Prompt « {scope} » → v{prompt['version']}",
            "description": reason,
            "type": "prompt_update",
            "from_role": "ai" if author == "ai" else "human",
            "status": "info",
        },
    )
    return prompt
