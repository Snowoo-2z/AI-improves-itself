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
from core.research import service as research_service

KNOWLEDGE_PATH = os.path.join(REPO_ROOT, "core", "data", "knowledge.json")

SKILLS: list[dict] = [
    {
        "id": "search_knowledge",
        "name": "Rechercher dans la base de connaissances",
        "description": (
            "Interroge la base de connaissances du projet (jeux, IA, infra...). "
            "Retourne jusqu'à 3 entrées réellement pertinentes : les sujets explicites "
            "de la requête doivent être présents (la source/URL compte aussi : une URL "
            "anthropic.com répond à « anthropic »), sinon la correspondance est signalée "
            "partial=true — vérifie alors la pertinence avant de t'y appuyer. "
            "ATTENTION : si l'utilisateur demande le PLUS RÉCENT / DERNIER élément "
            "d'une catégorie, passe use_date=true pour un tri par date ISO décroissante "
            "(la date de l'entrée = date du FAIT, pas la date d'insertion). "
            "Le premier résultat est alors le plus récent ; un modèle plus ancien "
            "(ex. Mythos 5, 2026-06-23) ne doit PAS être présenté comme le dernier "
            "s'il existe une entrée plus récente (ex. Claude Fable 5.1, 2026-09-10). "
            "Sans use_date, la base renvoie dans l'ordre d'insertion. "
            "Si la base est vide et que l'info peut venir du web : liste d'abord les résultats "
            "de recherche (list_research_results) AVANT de programmer une nouvelle tâche. "
            "Ne boucle pas sur cette skill à chaque tour : réponds honnêtement ou programme une recherche web."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mots-clés de la recherche."},
                "use_date": {
                    "type": "boolean",
                    "description": (
                        "true = tri par date du FAIT (ISO) décroissante. "
                        "Activé tout seul si la requête parle de dernier/récent/modèle/jeu/sortie."
                    ),
                },
                "date": {
                    "type": "string",
                    "description": (
                        "Date ISO AAAA-MM-JJ ou année AAAA : ne garder que les faits "
                        "à cette date (jour) ou jusqu'à cette année (as-of). "
                        "Utile pour « dernier modèle en 2026 »."
                    ),
                },
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
        "id": "web_agent",
        "name": "Agent de recherche web (immédiat, sans navigateur)",
        "description": (
            "Pilote UNE étape de recherche HTTP tout de suite dans ce tour "
            "(pas de navigateur JS — Colab non plus). kind=search (requête) | "
            "fetch (URL) | deep (recherche + lecture des 2 meilleures pages). "
            "Passe `say` : une phrase pour l'utilisateur (« je cherche le dernier "
            "modèle Anthropic »). Les hits reviennent avec titre, url, date si "
            "présente, extrait. Ensuite : fetch l'URL utile, ou add_knowledge "
            "avec la DATE DU FAIT, ou add_research_task si la page est 100 % JS. "
            "N'enchaîne pas plus de 3 étapes web_agent par message."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["search", "fetch", "deep"]},
                "target": {"type": "string", "description": "Requête (search/deep) ou URL (fetch)."},
                "say": {
                    "type": "string",
                    "description": "Ce que tu fais, en une phrase, visible dans le chat.",
                },
            },
            "required": ["kind", "target"],
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
            "de façon asynchrone en arrière-plan. ATTENTION : les résultats ne sont pas "
            "disponibles immédiatement dans ce tour ; après avoir programmé la tâche, "
            "réponds à l'utilisateur avec tes connaissances actuelles en mentionnant la programmation."
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
        "description": (
            "Lis les résultats de recherche déjà exécutés par le notebook Colab, en extrait "
            "compact : cible de la tâche, date, statut de l'étude IA (study_status) et extrait "
            "du contenu (study_status=skipped/error avec study_reason : l'étude échouait "
            "transitoirement, elle est ré-essayée automatiquement — le contenu reste exploitable). "
            "Passe query=« mots-clés du sujet » pour ne garder que les résultats pertinents. "
            "pending_tasks liste les tâches EN ATTENTE : leurs résultats n'existent pas encore "
            "(ne pas les annoncer). C'est LA skill à appeler quand l'utilisateur redemande une "
            "info web que tu as cherchée avant et que search_knowledge ne trouve pas : les "
            "résultats bruts ne sont JAMAIS perdus."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Nombre de résultats (défaut 5, max 20)."},
                "query": {"type": "string", "description": "Mots-clés du sujet (ex: « dernier modèle anthropic ») pour filtrer les résultats pertinents."},
            },
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
    as_of = str(args.get("date", "") or "").strip()
    temporal = _looks_temporal(query) or bool(as_of)
    use_date = bool(args.get("use_date", False)) or temporal
    entries = _load_knowledge()
    partial = False
    if query:
        query_terms = _search_tokens(query)
        # Les termes de sujet (OpenAI, Mistral, Zelda, …) sont obligatoires
        # quand ils existent. Les termes génériques (« dernier modèle ») ne
        # doivent pas transformer n'importe quelle entrée de la base en réponse.
        required_terms = [t for t in query_terms if t not in _SEARCH_GENERIC_TERMS]
        terms = required_terms or query_terms
        scored: list[tuple[int, int, int, dict]] = []
        soft: list[tuple[int, int, int, dict]] = []
        for index, entry in enumerate(entries):
            title = str(entry.get("title", ""))
            # La source compte dans la recherche : une URL (anthropic.com/news/…)
            # porte le nom de l'éditeur même quand titre/résumé ne le disent pas.
            haystack = (
                f"{title} {entry.get('summary', '')} {entry.get('category', '')} "
                f"{entry.get('source', '')}"
            )
            tokens = set(_search_tokens(haystack))
            if not terms or all(_term_matches(term, tokens) for term in terms):
                # Favoriser le titre et les entrées qui couvrent le plus de mots,
                # tout en conservant l'ordre d'insertion pour les égalités.
                title_tokens = set(_search_tokens(title))
                title_hits = sum(_term_matches(term, title_tokens) for term in terms)
                score = sum(_term_matches(term, tokens) for term in query_terms)
                scored.append((title_hits, score, index, entry))
            elif len(required_terms) >= 2:
                # Correspondance PARTIELLE : la requête compte plusieurs termes de
                # sujet et aucun n'est complet. On ne renvoie que les entrées qui
                # en couvrent la moitié ou plus — jamais toute la base (l'ancien
                # fallback poussait le LLM à s'appuyer sur du contenu non
                # pertinent). Le drapeau `partial` dans la réponse oblige le LLM
                # à vérifier la pertinence avant de s'appuyer dessus.
                matched = sum(1 for term in required_terms if _term_matches(term, tokens))
                if matched >= (len(required_terms) + 1) // 2:
                    title_tokens = set(_search_tokens(title))
                    title_hits = sum(1 for term in required_terms if _term_matches(term, title_tokens))
                    soft.append((matched, title_hits, index, entry))
        if scored:
            scored.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
            entries = [item[3] for item in scored]
        elif soft:
            soft.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
            entries = [item[3] for item in soft]
            partial = True
        else:
            # Important : une recherche sans résultat reste sans résultat.
            entries = []
    if as_of:
        entries = _filter_by_as_of(entries, as_of)
    if use_date:
        entries = sorted(
            entries,
            key=lambda e: _entry_date(e) or "0000-00-00",
            reverse=True,
        )
    top = entries[:3]
    timeline = [
        {"date": _entry_date(e), "title": e.get("title")}
        for e in entries
        if _entry_date(e)
    ][:12]
    undated = sum(1 for e in entries if not _entry_date(e))
    if partial:
        note = (
            "correspondance PARTIELLE : ces entrées ne couvrent pas tous les termes de la "
            "requête — vérifie la pertinence avant de t'y appuyer, et complète éventuellement "
            "avec list_research_results(query=...) si l'info vient du web."
        )
    elif use_date:
        note = (
            "tri par date de FAIT (ISO, plus récent d'abord) — cite la date de chaque "
            "entrée ; le premier daté est le plus récent. Les faits sans date ISO ne "
            "comptent pas comme « dernier »."
        )
        if as_of:
            note += f" Filtre date/année : {as_of}."
        if undated:
            note += f" {undated} entrée(s) sans date exacte, ignorées dans la chronologie."
    else:
        note = "ordre d'insertion (plus ancien d'abord)"
    return {
        "entries": [
            {
                "title": e.get("title"),
                "category": e.get("category"),
                "date": _entry_date(e) or e.get("date") or None,
                "dated": bool(_entry_date(e)),
                "summary": e.get("summary"),
                "source": e.get("source"),
            }
            for e in top
        ],
        "timeline": timeline,
        "count": len(entries),
        "used_date_sort": use_date,
        "as_of": as_of or None,
        "partial": partial,
        "note": note,
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


def _h_web_agent(args: dict) -> dict:
    """Une étape agent : dire → exécuter HTTP → renvoyer les hits."""
    from core.research import agent as research_agent
    from core.research import service as research_service

    kind = str(args.get("kind", "search") or "search")
    target = str(args.get("target", "") or "").strip()
    say = str(args.get("say", "") or "").strip()[:240]
    if not target:
        return {"ok": False, "error": "target est requis."}
    if not research_agent.network_allowed():
        return {
            "ok": False,
            "error": "agent hors-ligne (AIIS_AGENT_OFFLINE=1) — utilise add_research_task.",
            "say": say,
        }
    step = research_agent.run_step(kind, target)
    if not step.get("ok"):
        step["say"] = say
        return step
    # Persiste comme un résultat de recherche (visible /colab + list_research_results).
    try:
        item = research_service.add_result(
            kind,
            {k: v for k, v in (step.get("data") or {}).items() if k != "text" or len(str(v)) < 8000},
            study=True,
        )
        step["result_id"] = item.get("id")
    except Exception as exc:  # noqa: BLE001
        step["persist_error"] = str(exc)[:160]
    out = {
        "ok": True,
        "say": say or f"{kind} « {target[:80]} »",
        "kind": step.get("kind"),
        "target": step.get("target"),
        "engine": step.get("engine"),
        "browser": step.get("browser"),
        "hits": step.get("hits") or [],
        "count": step.get("count", 0),
        "error": step.get("error"),
        "next_hint": step.get("next_hint"),
        "result_id": step.get("result_id"),
    }
    return out


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
    return {
        "ok": True,
        "id": item.get("id"),
        "status": "pending",
        "message": (
            "Tâche enregistrée. L'exécution est asynchrone (Colab / worker) : "
            "aucun résultat n'est disponible immédiatement dans ce tour. "
            "Conclus et réponds à l'utilisateur avec tes connaissances actuelles."
        ),
    }


def _research_excerpt(data: Any, limit: int = 260) -> str:
    """Extrait lisible (borné) du contenu brut d'un résultat de recherche.

    Le dump JSON complet peut faire des dizaines de Ko (texte de pages lues) :
    la skill ne donne à l'IA que ce qu'elle peut réellement exploiter.
    """
    if not isinstance(data, dict):
        text = str(data or "")
    elif isinstance(data.get("summary"), dict) and data["summary"].get("summary"):
        text = str(data["summary"]["summary"])
    elif data.get("text"):
        text = str(data["text"])
    elif data.get("content"):
        text = str(data["content"])
    else:
        parts = []
        for it in (data.get("results") or [])[:4]:
            if not isinstance(it, dict):
                continue
            line = str(it.get("title", ""))
            if it.get("snippet"):
                line += f" — {it['snippet']}"
            parts.append(line)
        text = "\n".join(parts) or json.dumps(data, ensure_ascii=False)
    text = " ".join(str(text).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _h_list_research_results(args: dict) -> dict:
    """Les résultats de recherche sous forme d'extrait compact.

    - `query` (mots-clés du sujet) : ne garde que les résultats pertinents
      (cible de la tâche + contenu), au lieu du dump brut des N derniers.
    - `pending_tasks` : les tâches encore en attente du notebook Colab — leurs
      résultats n'existent PAS encore (ne pas dire à l'utilisateur qu'ils sont
      disponibles).
    - Filet anti-perte : la lecture déclenche la ré-étude automatique des
      résultats dont l'étude avait échoué par transitoire (moteur en repos).
    """
    s = store_module.get_store()
    limit = max(1, min(int(args.get("limit", 5) or 5), 20))
    query = str(args.get("query", "") or "").strip()

    try:
        research_service.retry_stale_studies()
    except Exception:  # noqa: BLE001 — la ré-étude ne doit jamais casser la lecture
        pass

    tasks = {str(t.get("id")): t for t in s.list("research_tasks")}
    results = s.list("research_results")
    try:
        results = sorted(results, key=lambda r: str(r.get("created_at", "")), reverse=True)
    except Exception:
        pass

    query_terms: list[str] = []
    if query:
        query_terms = [t for t in _search_tokens(query) if t not in _SEARCH_GENERIC_TERMS] or _search_tokens(query)

    digests: list[dict] = []
    for r in results:
        task = tasks.get(str(r.get("task_id"))) or {}
        data = r.get("data") or {}
        study = r.get("study") or {}
        digest = {
            "id": r.get("id"),
            "kind": r.get("kind"),
            "task_id": r.get("task_id"),
            "target": task.get("target", ""),
            "task_status": task.get("status", ""),
            "created_at": r.get("created_at", ""),
            "study_status": study.get("status", "in_progress"),
            "study_reason": study.get("reason", ""),
            "knowledge_title": (study.get("entry") or {}).get("title", ""),
            "excerpt": _research_excerpt(data),
        }
        if query_terms:
            hay = _norm(
                f"{digest['target']} {digest['excerpt']} "
                f"{json.dumps(data, ensure_ascii=False)[:2000]}"
            )
            if not any(_term_matches(t, set(_search_tokens(hay))) for t in query_terms):
                continue
        digests.append(digest)

    top = digests[:limit]
    pending = [
        {"id": t.get("id"), "kind": t.get("kind"), "target": t.get("target"), "status": t.get("status")}
        for t in sorted(
            (t for t in tasks.values() if t.get("status") in ("pending", "processing")),
            key=lambda t: str(t.get("created_at", "")),
            reverse=True,
        )[:5]
    ]
    if not top:
        if query:
            note = (
                f"aucun résultat ne correspond à « {query} » — la tâche est peut-être encore en "
                f"attente (voir pending_tasks) ou n'a pas encore été exécutée par le notebook Colab"
            )
        else:
            note = "aucun résultat disponible"
    else:
        note = (
            f"{len(top)} résultat(s) affiché(s) sur {len(results)} — les résultats bruts sont "
            f"conservés : ceux dont l'étude a échoué (study_status=skipped/error) sont ré-étudiés "
            f"automatiquement"
        )
    return {
        "results": top,
        "count": len(results),
        "pending_tasks": pending,
        "note": note,
    }


_SKILL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR_RE = re.compile(r"^\d{4}$")

# Requêtes pour lesquelles une date de FAIT est indispensable (sinon « dernier »
# tombe sur n'importe quelle entrée sans chronologie).
_TEMPORAL_QUERY_TERMS = {
    "dernier", "derniere", "latest", "newest", "recent", "recente", "recents",
    "recentes", "nouveau", "nouvelle", "nouveaux", "nouvelles", "modele",
    "modeles", "model", "models", "jeu", "jeux", "sortie", "sorties", "version",
    "versions", "release", "lancement",
}


def _looks_temporal(query: str) -> bool:
    tokens = set(_search_tokens(query))
    return bool(tokens.intersection(_TEMPORAL_QUERY_TERMS))


def _entry_date(entry: dict) -> str:
    d = str(entry.get("date") or "").strip()
    return d if _SKILL_DATE_RE.match(d) else ""


def _filter_by_as_of(entries: list[dict], as_of: str) -> list[dict]:
    """Filtre optionnel : jour exact, ou année (faits ≤ 31/12 de cette année)."""
    as_of = str(as_of or "").strip()
    if not as_of:
        return entries
    if _SKILL_DATE_RE.match(as_of):
        return [e for e in entries if _entry_date(e) == as_of]
    if _YEAR_RE.match(as_of):
        end = f"{as_of}-12-31"
        return [e for e in entries if _entry_date(e) and _entry_date(e) <= end]
    return entries


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
    "web_agent": _h_web_agent,
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
