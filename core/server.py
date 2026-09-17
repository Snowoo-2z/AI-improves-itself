"""Serveur du projet AI-improves-itself.

Sert :
- le site statique (site/) à la racine,
- l'API du cœur IA (/api/*) : chat, prompt système, skills, /request,
  /colab (recherche), /data (base de connaissances).

Démarrage (depuis la racine du repo) :
    python core/server.py            # ou : uvicorn core.server:app --port 8000
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from typing import Any

# Permet `python core/server.py` (commande documentée dans le README) : la racine
# du repo doit être importable pour charger le paquet `core.*`.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from core import store as store_module  # noqa: E402
from core.ai.chat import handle_chat, handle_chat_stream  # noqa: E402
from core.ai.config import env  # noqa: E402
from core.ai import providers  # noqa: E402
from core.prompt_system import registry  # noqa: E402
from core.research import service as research  # noqa: E402
from core.skills import manager as skills_manager  # noqa: E402

SITE_DIR = os.path.join(REPO_ROOT, "site")
COLAB_DIR = os.path.join(REPO_ROOT, "colab")

app = FastAPI(
    title="AI-improves-itself",
    description="Un projet de recherche : une IA qui s'améliore d'elle-même (prompt versionné, skills, recherche web).",
    version="0.1.0",
)

# ------------------------------------------------------------------ API ----
# Vision : limites de sécurité des images reçues. Le front les encode en
# data-URL base64 (pas de stockage ni d'upload de fichier côté serveur) :
# 2 Mo binaires suffisent pour une photo/capture, sans faire exploser le
# contexte ni le temps d'appel. Les data-URL ne quittent le serveur que vers
# les API des providers IA.
MAX_UPLOAD_IMAGES = 4
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MIN_DATA_BYTES = 32  # sol plancher : une vraie image fait au moins quelques octets signés


def _image_blocks(message: dict) -> list[dict]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == "image_url"]


def _looks_binary(raw: bytes) -> bool:
    return b"\x00" in raw or b"\xff" in raw or raw.startswith((b"\x89PNG", b"GIF8"))


def _b64_mime(raw: bytes) -> str | None:
    if raw.startswith((b"\x89PNG", b"GIF8", b"BM", b"RIFF")):
        return "image/png" if raw.startswith(b"\x89") else "image/gif" if raw.startswith(b"GIF8") else "image/x"
    return None


def _validate_images(messages: list) -> None:
    """Rejette proprement (400) les images trop grosses / trop nombreuses / sans
    format, avant le moindre appel LLM. La validation s'applique à tout
    l'historique : le front renvoie la conversation entière à chaque tour.
    """
    total = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        for b in _image_blocks(m):
            total += 1
            if total > MAX_UPLOAD_IMAGES:
                raise HTTPException(400, f"trop d'images : max {MAX_UPLOAD_IMAGES}")
            img = b.get("image_url")
            url = img.get("url") if isinstance(img, dict) else img
            url = str(url or "")
            if not url:
                raise HTTPException(400, "image sans URL")
            if url.startswith(("http://", "https://")):
                continue
            if not url.startswith("data:"):
                raise HTTPException(400, "image invalide : URL http(s) ou data-URL base64 attendue")
            header, _, payload = url[5:].partition(",")  # « data:… » sans le préfixe
            header = header.lower()
            mime = header.split(";", 1)[0]
            if not payload:
                raise HTTPException(400, "data-URL vide")
            if mime and not mime.startswith("image/"):
                raise HTTPException(400, f"type d'image non supporté : {mime}")
            if not header.endswith(";base64"):
                raise HTTPException(400, "seuls les data-URL base64 sont acceptés")
            try:
                raw = base64.b64decode(payload, validate=True)
            except Exception:  # noqa: BLE001
                raise HTTPException(400, "data-URL base64 invalide")
            if len(raw) < MIN_DATA_BYTES:
                raise HTTPException(400, "image vide ou corrompue")
            if len(raw) > MAX_IMAGE_BYTES:
                raise HTTPException(400, "image trop lourde : max 2 Mo")
            # Signature binaire introuvable et MIME absent → inclassable.
            if not _looks_binary(raw) and _b64_mime(raw) is None and not mime:
                raise HTTPException(400, "image non reconnue (png, jpg, gif, webp, …)")


class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., description="Historique complet [{role, content}]")
    thinking: bool | str = Field(
        default=False,
        description=(
            "Mode Pensée : effort de réflexion choisi en bas de la barre de chat — "
            "'low' | 'medium' | 'high' | 'off'. Compat historique : true (⇒ medium) / false (⇒ off)."
        ),
    )


class PromptEditRequest(BaseModel):
    new_content: str
    reason: str = "édition manuelle"
    scope: str = "main"


class RequestItem(BaseModel):
    title: str
    description: str = ""
    type: str = "other"
    from_role: str = "human"  # 'ai' | 'human'


class ResearchTask(BaseModel):
    kind: str = "search"  # search | fetch | note | deep
    target: str
    reason: str = ""
    by: str = "human"


class ResearchResult(BaseModel):
    kind: str = "note"
    data: dict[str, Any]
    task_id: str | None = None


@app.get("/health")
def health() -> dict:
    """Sonde légère pour Render (aucun accès store/réseau : 200 tant que le process vit)."""
    return {"ok": True}


@app.get("/api/status")
def status() -> dict:
    s = store_module.get_store()
    main = registry.get_current("main")
    # `health_report()` ne fait AUCUN appel réseau : il lit l'état des moteurs
    # (qui est au repos, pourquoi, dans combien de temps il est re-testé).
    health = providers.health_report()
    provider_name = providers.primary_provider_name()
    return {
        "store_backend": getattr(s, "backend", "local"),
        "store_repo": getattr(s, "repo", "") or "",
        "primary_provider": provider_name,
        "model": health["limits"].get(provider_name, {}).get("model", ""),
        "demo_mode": provider_name == "demo-local",
        "provider_errors": health["errors"],
        "provider_retry_in_s": health["retry_in_s"],
        "provider_retry_in_human": health["retry_in_human"],
        "provider": health,
        "prompt_main_version": main.get("version"),
        "prompt_updated_by": main.get("updated_by"),
        "prompts": [
            {"id": p["id"], "scope": p.get("scope"), "version": p.get("version")}
            for p in registry.load_all().values()
        ],
        "counts": {
            "dev_requests": len(s.list("dev_requests")),
            "research_tasks": len(s.list("research_tasks")),
            "research_results": len(s.list("research_results")),
            "knowledge": len(s.list("knowledge", default=_knowledge_seed())),
        },
    }


@app.post("/api/providers/retest")
def retest_providers(payload: dict | None = None) -> dict:
    """Re-tester la chaîne de providers à la demande (bouton « retester » du site).

    `force=true` réveille aussi les moteurs au repos : utile après avoir changé
    une clé dans `.env`, mais ça consomme un appel par provider — sur un tier
    gratuit à 50 requêtes/jour (OpenRouter), à ne pas spammer.
    """
    force = bool((payload or {}).get("force"))
    report = providers.ping_chain(force=force)
    providers.invalidate_provider_cache()
    health = providers.health_report()
    return {
        "ok": True,
        "ping": report,
        "active": health["active"],
        "errors": health["errors"],
        "retry_in_human": health["retry_in_human"],
    }


def _knowledge_seed() -> list[dict]:
    import json

    path = os.path.join(REPO_ROOT, "core", "data", "knowledge.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    if not req.messages:
        raise HTTPException(400, "messages vide")
    _validate_images(req.messages)
    return handle_chat(req.messages, thinking=req.thinking)


def _sse(data: dict) -> str:
    """Sérialise un événement Serveur-Sent Events (`data:` + JSON)."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class TitleRequest(BaseModel):
    messages: list[dict] = Field(..., description="Un seul message utilisateur décrivant ce qu'il faut titrer")


@app.post("/api/title")
def generate_title(req: TitleRequest) -> dict:
    """Titre court généré par le modèle pour nommer une conversation.

    Best-effort : un seul appel, sans outils, via la chaîne de repli habituelle.
    Si tout échoue (démo locale / quota), on renvoie un titre vide — le front
    garde alors le titre provisoire et l'utilisateur pourra toujours renommer.
    """
    from core.ai.providers import LocalDemoProvider, chat_with_failover

    # Constructeur minimal : pas de garde-fous par mots-clés, pas de skills.
    system = (
        "Tu es un utilitaire de titrage. Réponds UNIQUEMENT par un titre court "
        "(2 à 6 mots), sans guillemets, sans point final, sans phrase."
    )
    messages: list[dict] = [{"role": "system", "content": system}, *req.messages]

    try:
        outcome = chat_with_failover(messages, None)
        result = outcome.result
        raw = (result.content or "").strip()
        if isinstance(outcome.provider, LocalDemoProvider):
            raise ValueError("démo locale : pas de titrage réel")
        title = re.sub(r"^[\"'«]+|[\"'»]+$", "", raw).strip()
        title = re.split(r"[\n\r]", title)[0].strip(" .—-")
        if not title or len(title) > 100:
            raise ValueError("titre vide ou trop long")
        return {"title": title, "provider": result.provider or outcome.provider.name, "model": getattr(result, "model", "") or ""}
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return {"title": "", "provider": "", "model": ""}


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Variante streamée de /api/chat (SSE) — la réponse finale arrive jeton par jeton.

    Format : un événement `token` par delta de texte UNIQUEMENT pour la réponse
    finale, puis un événement `done` portant le contenu complet + les events
    (tools/prompt_update) + les warnings.
    """
    if not req.messages:
        raise HTTPException(400, "messages vide")
    _validate_images(req.messages)

    def _generator():
        for ev in handle_chat_stream(req.messages, thinking=req.thinking):
            yield _sse(ev)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/prompt-system")
def prompt_system() -> dict:
    return {"prompts": list(registry.load_all().values())}


@app.post("/api/prompt-system/{scope}")
def edit_prompt(scope: str, req: PromptEditRequest) -> dict:
    """Édition humaine du prompt système (même versionnage que l'IA)."""
    try:
        prompt = registry.apply_modification(
            scope, req.new_content, req.reason or "édition manuelle", author="human", trigger="manuel"
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "scope": scope, "version": prompt["version"]}


@app.get("/api/skills")
def skills() -> dict:
    return {"skills": skills_manager.list_skills()}


@app.get("/api/requests")
def requests_list() -> dict:
    items = store_module.get_store().list("dev_requests")
    return {"requests": sorted(items, key=lambda r: str(r.get("created_at", "")), reverse=True)}


@app.post("/api/requests")
def requests_add(req: RequestItem) -> dict:
    item = store_module.get_store().add(
        "dev_requests",
        {
            "title": req.title[:140],
            "description": req.description,
            "type": req.type,
            "from_role": req.from_role,
            "status": "open",
        },
    )
    return {"ok": True, "id": item.get("id")}


@app.get("/api/research/tasks")
def research_tasks() -> dict:
    items = store_module.get_store().list("research_tasks")
    return {"tasks": sorted(items, key=lambda r: str(r.get("created_at", "")), reverse=True)}


@app.post("/api/research/tasks")
def research_task_add(req: ResearchTask) -> dict:
    try:
        item = research.create_task(req.kind, req.target, req.reason, by=req.by)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "id": item.get("id")}


@app.patch("/api/research/tasks/{task_id}")
def research_task_mark(task_id: str, payload: dict) -> dict:
    """Mettre à jour le statut d'une tâche (utilisé par le script Colab)."""
    status = str(payload.get("status", "")).strip()
    if status not in ("pending", "processing", "done", "failed"):
        raise HTTPException(400, "status doit être pending|processing|done|failed")
    if research.mark_task(task_id, status) is None:
        raise HTTPException(404, "tâche introuvable")
    return {"ok": True, "id": task_id, "status": status}


@app.get("/api/research/results")
def research_results(task_id: str | None = None) -> dict:
    """Résultats de recherche, optionnellement filtrés par tâche.

    `?task_id=…` sert au notebook Colab v2 (déduplication des pushs + attente
    ciblée des bilans d'étude). Sans filtre : comportement v1 inchangé.
    """
    items = store_module.get_store().list("research_results")
    if task_id:
        items = [r for r in items if str(r.get("task_id")) == task_id]
    return {"results": sorted(items, key=lambda r: str(r.get("created_at", "")), reverse=True)}


@app.post("/api/research/results")
def research_result_add(req: ResearchResult) -> dict:
    """Point d'entrée utilisé par le notebook Colab."""
    item = research.add_result(req.kind, req.data, task_id=req.task_id)
    return {"ok": True, "id": item.get("id")}


class StudyRequest(BaseModel):
    force: bool = False


@app.post("/api/research/results/{result_id}/study")
def research_result_study(result_id: str, req: StudyRequest | None = None) -> dict:
    """Relance l'étude IA d'un résultat (structuration + vérification).

    Bouton « Ré-étudier » de la page /colab : utile quand l'étude automatique a
    échoué par transitoire (moteur en repos au moment du push Colab). Sans
    `force`, on ne relance que ce qui a un sens : résultat jamais étudié, ou
    étude skipped/error. `force=true` contourne (coûte 2 appels LLM).
    """
    s = store_module.get_store()
    item = next((r for r in s.list("research_results") if str(r.get("id")) == str(result_id)), None)
    if item is None:
        raise HTTPException(404, "résultat introuvable")
    study = item.get("study") or {}
    force = bool(req and req.force)
    if not force and study.get("status") not in (None, "skipped", "error"):
        raise HTTPException(
            409, f"aucune raison de ré-étudier (statut actuel : {study.get('status')}) — force=true pour forcer"
        )
    research._spawn_study(item, force=force)
    return {"ok": True, "id": result_id, "status": "étude relancée en arrière-plan"}


@app.get("/api/data/entries")
def data_entries() -> dict:
    s = store_module.get_store()
    items = s.list("knowledge", default=_knowledge_seed())
    return {"entries": items, "count": len(items)}


class KnowledgeEntry(BaseModel):
    """Entrée de base de connaissances — UNIQUEMENT les 5 champs de la base
    (`knowledge.json` / table Supabase `knowledge`) : portabilité des 3
    backends garantie (aucun champ inconnu à la persistance)."""

    title: str = Field(..., min_length=1, max_length=200)
    category: str = "divers"
    date: str = ""
    summary: str = Field(..., min_length=1, max_length=1500)
    source: str = "colab-analyseur"


class KnowledgeEntriesRequest(BaseModel):
    entries: list[KnowledgeEntry] = Field(..., min_length=1, max_length=20)
    updated_by: str = "human"
    note: str = ""


@app.post("/api/data/entries")
def data_entries_add(req: KnowledgeEntriesRequest) -> dict:
    """Écriture explicite de la base de connaissances.

    Utilisé par l'analyseur de discussions Colab (`colab/analyze_discussions.py`),
    qui a déjà fait lui-même les 2 passes (vérification web sourcée + synthèse
    avec la clé Mistral de l'utilisateur) — ici le serveur applique le patch
    validé, sans re-consommer de quota LLM :

    - titre identique (normalisé) à une entrée existante → **mise à jour**,
    - summary identique à une entrée existante → **doublon ignoré**,
    - sinon → **ajout**.

    Provenance : l'origine vit dans `source` (URL de la preuve ou
    « colab-analyseur ») + le `updated_by`/`note` renvoyés dans le bilan.
    Même garde-fou que le pipeline d'étude : l'entrée n'a QUE les 5 champs
    de la base (titré/résumé obligatoires, date ISO ou nulle, longueurs bornées).
    """
    s = store_module.get_store()
    existing = s.list("knowledge", default=_knowledge_seed())
    if not isinstance(existing, list):
        existing = []

    def norm(x: Any) -> str:
        return " ".join(str(x or "").lower().split())

    added: list[dict] = []
    updated: list[dict] = []
    skipped: list[dict] = []
    for e in req.entries:
        title = e.title.strip()
        summary = e.summary.strip()
        if not title or not summary:
            # Vide APRÈS nettoyage : on saute l'entrée (un lot entier doit
            # pouvoir passer — le Colab n'abandonne pas toute la push pour
            # une entrée mal formée).
            skipped.append({"title": title or "(titre vide)", "reason": "titre ou summary vide après nettoyage"})
            continue
        date = e.date.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            date = None
        entry = {
            "title": title[:200],
            "category": (e.category.strip()[:40] or "divers"),
            "date": date,
            "summary": summary[:1500],
            "source": (e.source.strip()[:500] or "colab-analyseur"),
        }
        match = next((x for x in existing if norm(x.get("title")) == norm(title)), None)
        if match is not None:
            # Le titre normalisé identifie l'entrée : on conserve l'orthographe
            # CANONIQUE existante (un payload « mistral ai » ne réécrit pas
            # « Mistral AI »).
            entry["title"] = str(match.get("title"))
            if norm(match.get("summary")) == norm(summary):
                skipped.append({"title": title, "reason": "doublon identique (summary déjà en base)"})
                continue
            if match.get("id"):
                updated_item = s.update("knowledge", match.get("id"), entry)
            else:
                # Entrée LÉGACE sans id (seed knowledge.json) : ciblée par
                # titre exact (jamais d'`update(None, …)` — cf. garde-fou store).
                updated_item = s.update_first("knowledge", {"title": str(match.get("title"))}, entry)
            stored = updated_item if isinstance(updated_item, dict) else entry
            match.update(entry)
            updated.append(stored)
            continue
        dup = next(
            (x for x in existing if norm(x.get("summary")) == norm(summary) and summary), None
        )
        if dup is not None:
            skipped.append({"title": title, "reason": f"summary déjà présent (entrée « {str(dup.get('title'))[:120]} »)"})
            continue
        item = s.add("knowledge", entry)
        stored = {**entry, "id": (item or {}).get("id")}
        existing.append(stored)
        added.append(stored)
    return {
        "ok": True,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "counts": {"added": len(added), "updated": len(updated), "skipped": len(skipped)},
        "updated_by": req.updated_by[:80],
        "note": req.note[:500],
    }


# ------------------------------------------------------------- Static ----
app.mount("/colab-notebook", StaticFiles(directory=COLAB_DIR, html=True), name="colab-notebook")
app.mount("/", StaticFiles(directory=SITE_DIR, html=True), name="site")


if __name__ == "__main__":
    import uvicorn

    # `app` directement (aucun re-import par chemin de module → robuste quelle
    # que soit la façon dont le script est lancé).
    uvicorn.run(app, host="0.0.0.0", port=int(env("PORT", "8000") or 8000), reload=False)
