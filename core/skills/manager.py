"""Skills : les outils que l'IA peut appeler.

Sécurité (important, l'IA s'auto-modifie) :
- Whitelist stricte : seules les skills référencées dans SKILLS sont exécutables.
- L'IA ne modifie JAMAIS le code du projet : elle peut ajuster les DESCRIPTIONS
  de ses skills et demander de nouvelles skills via `request_to_dev` (le dev implémente).
- Chaque exécution est journalisable (retourne le résultat brut).
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from typing import Any, Callable

from core import store as store_module
from core.ai.config import REPO_ROOT

KNOWLEDGE_PATH = os.path.join(REPO_ROOT, "core", "data", "knowledge.json")

SKILLS: list[dict] = [
    {
        "id": "search_knowledge",
        "name": "Rechercher dans la base de connaissances",
        "description": (
            "Interroge la base de connaissances du projet (jeux, IA, infra...). "
            "Retourne jusqu'à 3 entrées réellement pertinentes : les sujets explicites "
            "de la requête doivent être présents, sinon retourne zéro résultat. "
            "ATTENTION : si l'utilisateur demande le PLUS RÉCENT / DERNIER élément "
            "d'une catégorie, passe use_date=true pour un tri par date décroissante ; "
            "sans ça, la base renvoie dans l'ordre d'insertion (du plus ancien au plus récent). "
            "Tu peux regrouper jusqu'à 3 recherches de lecture seule dans une même réponse "
            "pour comparer des requêtes, mais ne boucle pas sur cette skill à chaque tour si "
            "aucune entrée ne correspond : réponds honnêtement ou programme une recherche web."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mots-clés de la recherche."},
                "use_date": {"type": "boolean", "description": "true = tri par date décroissante (plus récent d'abord)."},
            },
            "required": ["query"],
        },
    },
    {
        "id": "modify_prompt_system",
        "name": "Modifier son propre prompt système",
        "description": (
            "Le cœur du projet : modifier le prompt système (scope 'main', 'code', 'recherche'...) "
            "pour corriger un défaut détecté. Versionné + historique + notification au dev. "
            "n'accepte aucun contenu contenant de clé API."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "ID du prompt à modifier (main, code, recherche...)."},
                "reason": {"type": "string", "description": "Pourquoi cette modification (le défaut observé, la trace)."},
                "new_content": {"type": "string", "description": "NOUVEAU contenu COMPLET du prompt (pas un diff)."},
            },
            "required": ["scope", "reason", "new_content"],
        },
    },
    {
        "id": "request_to_dev",
        "name": "Ouvrir une requête au développeur",
        "description": (
            "Page /request : envoyer une requête au dev du projet — nouvelle fonctionnalité, "
            "modif UI, bug, ou nouvelle skill souhaitée. L'IA n'écrit pas de code : elle demande."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titre court de la requête."},
                "description": {"type": "string", "description": "Détails : contexte, comportement attendu, exemples."},
                "type": {"type": "string", "enum": ["feature", "ui", "bug", "skill", "other"]},
            },
            "required": ["title", "description"],
        },
    },
    {
        "id": "add_research_task",
        "name": "Programmer une tâche de recherche web",
        "description": (
            "Ajoute une tâche dans la file /colab : kind='fetch' + URL, "
            "kind='search' + requête (titres + extraits), ou kind='deep' + sujet "
            "(recherche + lecture auto des meilleures pages — idéal pour un état "
            "de l'art ou une question précise). Le notebook Colab (colab/) l'exécute "
            "de façon asynchrone ; les résultats reviennent via list_research_results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["search", "fetch", "deep"]},
                "target": {"type": "string", "description": "URL (fetch) ou requête (search)."},
                "reason": {"type": "string", "description": "Pourquoi l'IA a besoin de cette info."},
            },
            "required": ["kind", "target"],
        },
    },
    {
        "id": "list_research_results",
        "name": "Lire les derniers résultats de recherche",
        "description": "Retourne les N derniers résultats de recherche (tâches exécutées par le notebook Colab).",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Nombre de résultats (défaut 5, max 20)."}},
        },
    },
    {
        "id": "add_knowledge",
        "name": "Ajouter une entrée dans la base de connaissances",
        "description": (
            "Ajoute une entrée à la base de connaissances (page /data) : {title, category, "
            "date ISO AAAA-MM-JJ, summary, source}. À utiliser quand une info vérifiée "
            "(issue de list_research_results ou du web) mérite d'être mémorisée durablement. "
            "Cite toujours la source et la date de récupération."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titre court de l'entrée."},
                "category": {"type": "string", "description": "Thème court (ia, web, jeux-vidéo, infra…)."},
                "date": {"type": "string", "description": "Date du fait (AAAA-MM-JJ), ou date du jour si inconnue."},
                "summary": {"type": "string", "description": "1 à 3 phrases factuelles et sourcées."},
                "source": {"type": "string", "description": "URL d'origine ou provenance (ex: colab)."},
            },
            "required": ["title", "summary"],
        },
    },
    {
        "id": "update_skill_description",
        "name": "Affiner la description d'une de ses skills",
        "description": (
            "Auto-amélioration légère : mettre à jour la DESCRIPTION d'une skill existante "
            "(pas son code — le code, seul le dev le modifie, via /request)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string"},
                "new_description": {"type": "string", "description": "Nouvelle description (10 à 500 caractères)."},
            },
            "required": ["skill_id", "new_description"],
        },
    },
]

_registry: dict[str, dict] = {s["id"]: s for s in SKILLS}


# ------------------------------------------------------------- Handlers ----
def _norm(text: str) -> str:
    """Normalise un texte de recherche de façon stable (accents compris).

    La recherche est utilisée par des modèles qui reformulent souvent la
    question : « modèle », « modele » et « modèles » doivent donc être
    comparables, mais deux sujets distincts comme « modèle » et « OpenAI » ne
    doivent pas être mélangés.
    """
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).lower().strip()


def _search_tokens(text: str) -> list[str]:
    """Retourne les mots significatifs d'une requête ou d'une entrée."""
    return re.findall(r"[a-z0-9]+", _norm(text))


def _word_forms(word: str) -> set[str]:
    """Petite tolérance singulier/pluriel sans faire de matching par substring.

    Le matching précédent testait ``mot in texte`` pour chaque mot de la
    requête. Ainsi « modèle OpenAI » trouvait l'entrée Mistral parce que
    « modèle » est un préfixe de « modèles », alors que « OpenAI » était
    absent. Cette tolérance garde les variantes françaises utiles sans rendre
    un mot absent présent.
    """
    forms = {word}
    if len(word) > 4 and word.endswith("s"):
        forms.add(word[:-1])
    elif len(word) > 3 and word.endswith("x"):
        forms.add(word[:-1])
    return forms


def _term_matches(term: str, tokens: set[str]) -> bool:
    wanted = _word_forms(term)
    return any(wanted.intersection(_word_forms(candidate)) for candidate in tokens)


# Mots qui décrivent la forme de la demande plutôt que le sujet recherché.
# Ils ne doivent pas rendre une entrée Mistral pertinente pour une question
# portant explicitement sur OpenAI, mais ils restent recherchables seuls
# (par exemple la requête « modèle »).
_SEARCH_GENERIC_TERMS = {
    "a", "au", "aux", "avec", "ce", "cette", "d", "dans", "de", "dernier", "derniere",
    "du", "en", "est", "et", "la", "le", "les", "meilleur", "meilleure", "modele",
    "modeles", "nouveau", "nouvelle", "plus", "pour", "quel", "quelle", "quels",
    "quelles", "recent", "recente", "recents", "recentes", "recherche", "sur",
    "the", "un", "une", "what", "latest", "newest", "recently", "version",
}


def _load_knowledge() -> list[dict]:
    # Passe par le Store actif : en mode local c'est le même fichier qu'avant
    # (core/data/knowledge.json), en mode github/supabase ça vient du backend.
    try:
        items = store_module.get_store().list("knowledge", default=[])
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _h_search_knowledge(args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    use_date = bool(args.get("use_date", False))
    entries = _load_knowledge()
    if query:
        query_terms = _search_tokens(query)
        # Les termes de sujet (OpenAI, Mistral, Zelda, …) sont obligatoires
        # quand ils existent. Les termes génériques (« dernier modèle ») ne
        # doivent pas transformer n'importe quelle entrée de la base en réponse.
        required_terms = [t for t in query_terms if t not in _SEARCH_GENERIC_TERMS]
        scored: list[tuple[int, int, int, dict]] = []
        for index, entry in enumerate(entries):
            title = str(entry.get("title", ""))
            haystack = f"{title} {entry.get('summary', '')} {entry.get('category', '')}"
            tokens = set(_search_tokens(haystack))
            terms = required_terms or query_terms
            if not terms or not all(_term_matches(term, tokens) for term in terms):
                continue
            # Favoriser le titre et les entrées qui couvrent le plus de mots,
            # tout en conservant l'ordre d'insertion pour les égalités.
            title_tokens = set(_search_tokens(title))
            title_hits = sum(_term_matches(term, title_tokens) for term in terms)
            score = sum(_term_matches(term, tokens) for term in query_terms)
            scored.append((title_hits, score, index, entry))
        if scored:
            scored.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
            entries = [item[3] for item in scored]
        else:
            # Important : une recherche sans résultat reste sans résultat.
            # L'ancien fallback renvoyait toute la base et le LLM croyait
            # qu'une entrée partiellement similaire répondait à la question.
            entries = []
    # Sans use_date, l'ordre d'insertion est conservé (du plus ancien au plus
    # récent). Le tri explicite est réservé aux questions « dernier/récent ».
    if use_date:
        entries = sorted(entries, key=lambda e: str(e.get("date") or ""), reverse=True)
    top = entries[:3]
    return {
        "entries": [
            {"title": e.get("title"), "category": e.get("category"), "date": e.get("date"), "summary": e.get("summary")}
            for e in top
        ],
        "count": len(entries),
        "used_date_sort": use_date,
        "note": "tri date décroissante appliqué" if use_date else "ordre d'insertion (plus ancien d'abord)",
    }


def _h_modify_prompt_system(args: dict) -> dict:
    from core.prompt_system import registry

    scope = str(args.get("scope", "main"))
    reason = str(args.get("reason", "")).strip()
    new_content = str(args.get("new_content", ""))
    if not reason:
        return {"ok": False, "error": "reason est requis (explique le défaut qui motive la modification)."}
    prompt = registry.apply_modification(scope, new_content, reason, author="ai", trigger="auto")
    return {"ok": True, "scope": scope, "version": prompt["version"]}


def _h_request_to_dev(args: dict) -> dict:
    s = store_module.get_store()
    item = s.add(
        "dev_requests",
        {
            "title": str(args.get("title", "(sans titre)")[:140]),
            "description": str(args.get("description", "")),
            "type": str(args.get("type", "other")),
            "from_role": "ai",
            "status": "open",
        },
    )
    return {"ok": True, "id": item.get("id"), "status": "open"}


def _h_add_research_task(args: dict) -> dict:
    s = store_module.get_store()
    kind = str(args.get("kind", "search"))
    target = str(args.get("target", "")).strip()
    if not target:
        return {"ok": False, "error": "target est requis (URL ou requête)."}
    item = s.add(
        "research_tasks",
        {
            "kind": kind,
            "target": target[:500],
            "reason": str(args.get("reason", ""))[:500],
            "by": "ai",
            "status": "pending",
        },
    )
    return {"ok": True, "id": item.get("id"), "status": "pending"}


def _h_list_research_results(args: dict) -> dict:
    s = store_module.get_store()
    limit = int(args.get("limit", 5) or 5)
    results = s.list("research_results")
    try:
        results = sorted(results, key=lambda r: str(r.get("created_at", "")), reverse=True)
    except Exception:
        pass
    return {"results": results[: min(limit, 20)]}


_SKILL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _h_add_knowledge(args: dict) -> dict:
    s = store_module.get_store()
    title = str(args.get("title", "")).strip()
    summary = str(args.get("summary", "")).strip()
    if not title or not summary:
        return {"ok": False, "error": "title et summary sont requis."}
    date = str(args.get("date", "")).strip()
    if not _SKILL_DATE_RE.match(date):
        date = time.strftime("%Y-%m-%d", time.gmtime())
    item = s.add(
        "knowledge",
        {
            "title": title[:200],
            "category": str(args.get("category", "divers")).strip()[:40] or "divers",
            "date": date,
            "summary": summary[:1500],
            "source": str(args.get("source", "ai")).strip()[:500] or "ai",
            "added_by": "ai",
        },
    )
    return {"ok": True, "id": item.get("id"), "title": item.get("title")}


def _h_update_skill_description(args: dict) -> dict:
    skill_id = str(args.get("skill_id", ""))
    new_description = str(args.get("new_description", "")).strip()
    if skill_id not in _registry:
        return {"ok": False, "error": f"skill inconnue : {skill_id}"}
    if not (10 <= len(new_description) <= 500):
        return {"ok": False, "error": "new_description doit faire entre 10 et 500 caractères."}
    # Les descriptions sont persistées dans un fichier de surcouches (éditable par l'IA,
    # reviewable par l'humain dans git) — le code des skills reste intouchable.
    overlay_path = os.path.join(REPO_ROOT, "core", "skills", "descriptions.json")
    overlay = {}
    if os.path.exists(overlay_path):
        try:
            with open(overlay_path, "r", encoding="utf-8") as fh:
                overlay = json.load(fh)
        except (ValueError, OSError):
            overlay = {}
    overlay[skill_id] = {"description": new_description, "updated_at": time.time()}
    with open(overlay_path, "w", encoding="utf-8") as fh:
        json.dump(overlay, fh, indent=2, ensure_ascii=False)
    return {"ok": True, "skill_id": skill_id}


HANDLERS: dict[str, Callable[[dict], dict]] = {
    "search_knowledge": _h_search_knowledge,
    "modify_prompt_system": _h_modify_prompt_system,
    "request_to_dev": _h_request_to_dev,
    "add_research_task": _h_add_research_task,
    "list_research_results": _h_list_research_results,
    "add_knowledge": _h_add_knowledge,
    "update_skill_description": _h_update_skill_description,
}


# ----------------------------------------------------------------- API ----
def _load_overlays() -> dict:
    p = os.path.join(REPO_ROOT, "core", "skills", "descriptions.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, OSError):
            return {}
    return {}


def list_skills() -> list[dict]:
    overlays = _load_overlays()
    out = []
    for s in SKILLS:
        s = dict(s)
        ov = overlays.get(s["id"])
        if ov and ov.get("description"):
            s["description"] = ov["description"]
            s["description_updated_by"] = "ai"
        out.append(s)
    return out


def to_openai_tools() -> list[dict]:
    """Format OpenAI `tools` (compatible Mistral/Gemini/Groq/OpenRouter)."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["id"],
                "description": s["description"],
                "parameters": s["parameters"],
            },
        }
        for s in list_skills()
    ]


def execute(name: str, args: dict) -> dict:
    """Exécuter une skill (whitelist stricte)."""
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"skill inconnue ou non autorisée : {name}"}
    if not isinstance(args, dict):
        return {"ok": False, "error": "arguments invalides (objet JSON attendu)"}
    try:
        return handler(args)
    except PermissionError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — on ne fait jamais tomber le chat
        import sys

        print(f"[skills] {name} → {exc}", file=sys.stderr)
        return {"ok": False, "error": f"erreur d'exécution : {exc}"}
