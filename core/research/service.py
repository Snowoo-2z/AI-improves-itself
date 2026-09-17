"""Pipeline de recherche : tâches → exécution (notebook Colab) → résultats → étude.

- `create_task` / `add_result` / `mark_task` : la file et les résultats bruts
  (utilisés par le serveur API ET par le notebook Colab).
- `add_result` déclenche `study_result` : le moteur Mistral (ou la chaîne de
  repli) RELIT le résultat brut, le STRUCTURE en entrée de base de connaissances
  (1er appel), et une 2e passe VÉRIFIE la cohérence/pertinence avant d'écrire.
  La date du jour est fournie à l'IA (elle ne la connaît pas sinon).
- `study_result` : l'IA étudie le résultat et décide si la base de
  connaissances doit être mise à jour. C'est le « pas de réflexion » du pipeline
  de recherche (phase 2, désormais implémenté).
"""
from __future__ import annotations

import json
import re
import time
import unicodedata

from core import store as store_module
from core.ai.providers import LocalDemoProvider, chat_with_failover

#: Contenu brut envoyé au LLM par résultat (borné : l'étude ne doit pas consumer
#: tout le quota gratuit sur un seul fetch géant).
STUDY_MAX_CHARS = 5000
#: Seuil de validation d'une entrée (le LLM note de 0 à 1 la confiance qu'il a
#: dans la structure produite ; en dessous on n'écrit rien — 2e passe de
#: vérification incluse).
MIN_CONFIDENCE = 0.55

#: Filet anti-perte du pipeline : si le moteur d'analyse est en repos (429/quota)
#: quand le push Colab arrive, l'étude est marquée `retryable` et ré-essayée
#: automatiquement (cooldown + plafond de tentatives) aux prochains événements.
RETRY_COOLDOWN_S = 1800  # 30 min entre deux tentatives automatiques
RETRY_MAX_ATTEMPTS = 5


def create_task(kind: str, target: str, reason: str = "", by: str = "human") -> dict:
    if kind not in ("search", "fetch", "note", "deep"):
        raise ValueError("kind doit être 'search', 'fetch', 'note' ou 'deep'")
    if not target:
        raise ValueError("target est requis")
    s = store_module.get_store()
    return s.add(
        "research_tasks",
        {"kind": kind, "target": target[:500], "reason": reason[:500], "by": by, "status": "pending"},
    )


def add_result(
    kind: str,
    data: dict,
    task_id: str | None = None,
    *,
    study: bool = True,
    force_study: bool = False,
) -> dict:
    s = store_module.get_store()
    # task_id est persisté DANS le résultat : la page /colab l'affiche pour
    # rattacher le résultat à sa tâche, et Supabase utilise la FK research_results.task_id.
    item = s.add(
        "research_results",
        {"kind": kind, "data": data, "task_id": task_id, "status": "done"},
    )
    if task_id:
        s.update("research_tasks", task_id, {"status": "done", "updated_at": _now_iso()})
    if study:
        # 2 appels LLM par résultat → on N'EN BLOQUE PAS le HTTP : exécution en
        # arrière-plan, le bilan `study` est réécrit sur l'item une fois fini
        # (visible sur /colab au refresh).
        _spawn_study(item, force=force_study)
        # Un push Colab est un bon moment pour ré-étudier les résultats
        # précédents dont l'étude avait échoué par transitoire (moteur en
        # repos) : c'est ce filet qui évite que l'info « se perde ».
        try:
            retry_stale_studies()
        except Exception:  # noqa: BLE001 — la ré-étude ne casse jamais le push
            pass
    return item


def _spawn_study(item: dict, *, force: bool) -> None:
    import threading

    def _run() -> None:
        prev = item.get("study") or {}
        try:
            outcome = study_result(item, force=force)
        except Exception as exc:  # noqa: BLE001 — l'étude ne casse jamais le site
            outcome = {"status": "error", "reason": f"étude impossible : {exc}", "retryable": True}
        outcome.setdefault("retryable", False)
        outcome["retried_at"] = time.time()
        outcome["retries"] = int(prev.get("retries", 0) or 0) + 1
        try:
            store_module.get_store().update("research_results", item.get("id"), {"study": outcome})
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def retry_stale_studies() -> int:
    """Ré-étudie automatiquement les résultats dont l'étude a échoué TRANSITOIREMENT.

    C'est le filet anti-perte du pipeline de recherche : si le moteur d'analyse
    était en repos (429/quota/démo locale) quand le résultat de Colab est arrivé,
    l'entrée n'a jamais atteint la base de connaissances — l'info restait « perdue »
    pour l'IA. On la ré-essaie ici (cooldown de `RETRY_COOLDOWN_S`, plafond de
    `RETRY_MAX_ATTEMPTS`) à chaque événement déclencheur :
      - nouveau push Colab (`add_result`),
      - lecture des résultats par l'IA (skill `list_research_results`),
      - bouton « Ré-étudier » de la page /colab (endpoint dédié).
    Retourne le nombre de ré-études planifiées.
    """
    s = store_module.get_store()
    now = time.time()
    retried = 0
    try:
        items = s.list("research_results")
    except Exception:  # noqa: BLE001
        return 0
    for item in items:
        st = item.get("study") or {}
        if st.get("status") not in ("skipped", "error"):
            continue
        if not st.get("retryable"):
            continue  # rejet / doublon / contenu vide : ré-essayer ne changerait rien
        if int(st.get("retries", 0) or 0) >= RETRY_MAX_ATTEMPTS:
            continue
        if now - float(st.get("retried_at", 0) or 0) < RETRY_COOLDOWN_S:
            continue
        _spawn_study(item, force=False)
        retried += 1
    return retried


def mark_task(task_id: str, status: str) -> dict | None:
    s = store_module.get_store()
    return s.update("research_tasks", task_id, {"status": status, "updated_at": _now_iso()})


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ----------------------------------------------------------------- study -----
def _today_string() -> str:
    """Date du jour (locale serveur), pour que l'IA sache « aujourd'hui ».

    Sans elle, un modèle ne connaît pas la date exacte → il ne peut pas dater
    une info web (« vérifié le … »). Le fuseau suit celui du serveur (Europe/Paris
    en local ; UTC sur Render).
    """
    from datetime import datetime

    return datetime.now().astimezone().strftime("%A %d %B %Y (%Z)")


def _clip(text: str, limit: int = STUDY_MAX_CHARS) -> str:
    return (text or " ").strip()[:limit]


def _entry_shape_hint() -> str:
    """Schéma cible d'une entrée de la base de connaissances (knowledge.json)."""
    return (
        "La base de connaissances a ce format d'entrée : "
        "{title, category, date (ISO \"AAAA-MM-JJ\"), summary, source}. "
        "category : thème court en minuscules (ex: ia, jeux-vidéo, infra, web, science...). "
        "summary : 1 à 3 phrases factuelles SOURCÉES. source : URL d'origine ou \"colab\"."
    )


_SYSTEM_DRAFT = (
    "Tu es l'étape « structuration » du pipeline de recherche du projet "
    "AI-improves-itself. Un notebook Colab a récupéré du contenu web brut "
    "(recherche, page, ou note). Transforme-le en UNE entrée utile pour une base "
    "de connaissances versionnée.\n"
    "Réponds UNIQUEMENT en JSON valide (pas de markdown, pas de prose) :\n"
    + _entry_shape_hint()
    + "\n"
    '{"ok": true|false, "title": "...", "category": "...", "date": "AAAA-MM-JJ", '
    '"summary": "...", "source": "...", "confidence": 0.0, "skip_reason": "..."}\n'
    "- ok=false quand le contenu ne permet AUCUNE entrée utile (page vide, erreur, "
    "pub, déjà du contenu sans substance). skip_reason explique alors pourquoi.\n"
    "- confidence : de 0 à 1 ta certitude que l'entrée est exacte et bien sourcée.\n"
    "- La date de l'entrée = la date du FAIT relaté si elle est connue, sinon la "
    "date du jour (fournie dans l'utilisateur) avec pour source la mention \"vérifié le <date>\"."
)


_SYSTEM_VERIFY = (
    "Tu es l'étape « vérification » du pipeline de recherche du projet "
    "AI-improves-itself. Tu reçois (1) le contenu web brut récupéré par Colab et "
    "(2) l'entrée de base de connaissances proposée par une 1re passe.\n"
    "Réponds UNIQUEMENT en JSON valide (pas de markdown) :\n"
    '{"approve": true|false, "json": {entrée corrigée OU identique}, "confidence": 0.0, "issues": "..."}\n'
    "- approve=false si l'entrée est incohérente, non pertinente, non sourcée, "
    "ou contient une info non présentable (privée, illégale, hors charte).\n"
    "- Si approve=true mais qu'une correction s'impose (date, catégorie, résumé), "
    "mets l'entrée CORRIGÉE dans \"json\". Sinon renvoie la même entrée.\n"
    "- confidence finale : 0 à 1 (ta certitude après vérification).\n"
    "- \"issues\" : une phrase si tu as corrigé ou rejeté, sinon vide."
)


def _extract_json(raw: str) -> dict | None:
    """Le JSON de la réponse LLM peut être entouré de markdown ```json …```."""
    if isinstance(raw, dict):
        return raw
    text = raw or ""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
    return None


def _asks_llm(system: str, user: str) -> tuple[str | None, str | None]:
    """Un appel structuré/JSON via la chaîne de repli (jamais la démo locale).

    Retourne (content, provider_name). La démo locale ne sait pas analyser : on
    la refuse explicitement pour ne pas écrire d'absurdités dans la base.
    """
    outcome = chat_with_failover(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        None,
    )
    if isinstance(outcome.provider, LocalDemoProvider):
        return None, outcome.provider.name
    return (outcome.result.content or "").strip(), outcome.provider.name


def _clean_entry(js: dict) -> dict | None:
    """Normalise le JSON du modèle en entrée de base (jamais plus de champs que prévu)."""
    title = str(js.get("title") or "").strip()
    summary = str(js.get("summary") or "").strip()
    if not title or not summary:
        return None
    category = str(js.get("category") or "divers").strip()[:40] or "divers"
    date = str(js.get("date") or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        date = ""
    source = str(js.get("source") or "colab").strip()[:500] or "colab"
    return {
        "title": title[:200],
        "category": category,
        "date": date,
        "summary": summary[:1500],
        "source": source,
    }


# Mots trop génériques pour l'ancrage titre↔brut (les noms propres restent exigés).
_GROUNDING_STOP = {
    "acces", "apres", "article", "cette", "chez", "dans", "dernier", "derniere",
    "entre", "etude", "lancement", "modele", "modeles", "nouveau", "nouvelle",
    "partiel", "partielle", "plus", "pour", "projet", "recherche", "selon",
    "suite", "vers", "avec", "sans", "sous", "sur", "une", "des", "les", "the",
    "and", "for", "with", "from", "after", "latest", "model", "models", "news",
}


def _norm_ground(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).lower()


def _distinctive_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", _norm_ground(text))
    out: list[str] = []
    for t in tokens:
        if len(t) < 5:
            continue
        if t.isdigit():
            continue
        if t in _GROUNDING_STOP:
            continue
        out.append(t)
    return out


def _entry_grounded_in_raw(entry: dict, raw: str) -> tuple[bool, str]:
    """Refuse une entrée dont les noms propres du titre n'apparaissent pas dans le brut.

    C'est le filet anti-hallucination : le LLM de structuration peut inventer un
    modèle « Mythos » alors que Colab a lu une page sur Claude. Sans ce test,
    l'entrée empoisonne la base et `search_knowledge(use_date=true)` la sert
    comme « dernier modèle ».
    """
    hay = _norm_ground(raw)
    missing = [t for t in _distinctive_tokens(str(entry.get("title") or "")) if t not in hay]
    if missing:
        return False, "titre non ancré dans le brut (termes absents : " + ", ".join(missing[:6]) + ")"
    return True, ""


def _dedupe(entry: dict) -> bool:
    """Évite de re-écrire une entrée quasi identique déjà en base."""
    s = store_module.get_store()
    try:
        existing = s.list("knowledge", default=[])
    except Exception:  # noqa: BLE001
        return False
    def norm(x: str) -> str:
        return " ".join((x or "").lower().split())

    t = norm(entry.get("title", ""))
    for e in existing:
        if norm(e.get("title", "")) == t:
            return True
        if norm(e.get("summary", "")) == norm(entry.get("summary", "")) and entry.get("summary"):
            return True
    return False


def study_result(result: dict, *, force: bool = False) -> dict:
    """Étudie UN résultat brut → propose une entrée → vérifie → écrit dans `knowledge`.

    2 appels LLM (comme demandé) :
      1. STRUCTURATION : brut + date du jour → {title, category, date, summary, source, confidence}
      2. VÉRIFICATION : brut + entrée proposée → approve / corrigée / confidence finale

    L'écriture dans la base est faite seulement si les deux passes acceptent et
    si aucune entrée dupliquée n'existe déjà. Retourne un résumé CRL (stocké
    dans le résultat et affiché sur /colab).
    """
    kind = result.get("kind", "note")
    data = result.get("data") or {}

    # Matière première lisable selon le kind (bornée). Depuis Colab v2, les
    # search/deep embarquent snippets (+ texte des pages lues) : on les donne
    # à l'IA, sinon elle structurerait sur des titres seuls.
    if kind == "search":
        lines = []
        for it in data.get("results") or []:
            if not isinstance(it, dict):
                continue
            line = f"- {it.get('title', '?')} ({it.get('url', '')})"
            if it.get("snippet"):
                line += f" — {it['snippet']}"
            if it.get("text"):
                line += f"\n  contenu : {str(it['text'])[:900]}"
            lines.append(line)
        raw = _clip("\n".join(lines))
    elif kind == "deep":
        chunks = []
        summary = data.get("summary")
        if isinstance(summary, dict) and summary.get("summary"):
            chunks.append(f"Résumé préparé par Colab : {summary['summary']}")
        for it in (data.get("results") or [])[:6]:
            if not isinstance(it, dict):
                continue
            line = f"- {it.get('title', '?')} ({it.get('url', '')})"
            if it.get("snippet"):
                line += f" — {it['snippet']}"
            if it.get("text"):
                line += f"\n  contenu : {str(it['text'])[:900]}"
            chunks.append(line)
        raw = _clip("\n".join(chunks))
    elif kind == "fetch":
        raw = _clip(str(data.get("text", "") or data.get("title", "") or ""))
    else:
        raw = _clip(str(data.get("content", "") or ""))

    if not raw.strip():
        return {"status": "skipped", "reason": "résultat brut vide"}

    url = str(data.get("url", "") or "").strip()
    if kind == "deep" and not url:  # deep : l'URL vit dans les résultats
        for it in data.get("results") or []:
            if isinstance(it, dict) and it.get("url"):
                url = str(it["url"])
                break
    meta = (
        f"kind={kind}\n"
        + (f"url={url}\n" if url else "")
        + f"récupéré le={_now_iso()}\n"
    )

    draft_user = (
        f"Aujourd'hui (date du jour pour dater la source) : {_today_string()}\n\n"
        f"Contenu récupéré par Colab :\n{raw}\n\n"
        + (f"URL source : {url}\n" if url else "")
    )
    content, provider = _asks_llm(_SYSTEM_DRAFT, draft_user)
    if content is None:
        # Échec TRANSITOIRE : le moteur d'analyse était en repos (429/quota) ou
        # seul la démo locale répond. Le résultat brut reste exploitable →
        # l'étude sera ré-essayée automatiquement (voir `retry_stale_studies`).
        reason = (
            "moteur d'analyse indisponible (démo locale)"
            if provider == "demo-local"
            else "moteur d'analyse indisponible (tous les moteurs en repos)"
        )
        return {"status": "skipped", "reason": reason, "provider": provider, "retryable": True}
    draft = _extract_json(content)
    if not isinstance(draft, dict):
        return {
            "status": "skipped",
            "reason": "sortie du moteur non structurable",
            "provider": provider,
            "retryable": True,  # un moteur qui répond n'importe quoi : ré-essayer ailleurs
        }
    if draft.get("ok") is False and not draft.get("title"):
        return {
            "status": "skipped",
            "reason": str(draft.get("skip_reason") or "contenu sans substance")[:300],
            "provider": provider,
        }

    entry = _clean_entry(draft)
    if entry is None:
        return {"status": "skipped", "reason": "entrée incomplète (title/summary manquants)", "provider": provider}

    # --- 2e passe : vérification -----------------------------------------
    verify_user = (
        f"Aujourd'hui : {_today_string()}\n\n"
        f"=== Contenu brut (Colab) ===\n{raw}\n\n"
        f"=== Entrée proposée (1re passe) ===\n{json.dumps(entry, ensure_ascii=False)}\n"
        f"(métadonnées : {meta})"
    )
    check_raw, check_provider = _asks_llm(_SYSTEM_VERIFY, verify_user)
    approval: dict = {"approve": False, "confidence": 0.0, "issues": ""}
    if check_raw is not None:
        parsed = _extract_json(check_raw)
        if isinstance(parsed, dict):
            approval = parsed
    confidence = _to_float(approval.get("confidence"), float(draft.get("confidence", 0.0)))
    approved = bool(approval.get("approve"))
    if approved and isinstance(approval.get("json"), dict):
        fixed = _clean_entry(approval["json"])
        if fixed:
            entry = fixed
        else:
            approved = False
            approval["issues"] = str(approval.get("issues") or "correction illisible")

    if not approved:
        reason = str(approval.get("issues") or "rejetée à la vérification")[:300]
        return {"status": "rejected", "reason": reason, "provider": provider, "verify_provider": check_provider}
    if confidence < (0.0 if force else MIN_CONFIDENCE):
        return {
            "status": "rejected",
            "reason": f"confiance trop faible ({confidence:.2f} < {MIN_CONFIDENCE})",
            "provider": provider,
            "verify_provider": check_provider,
            "confidence": confidence,
        }
    if not force:
        grounded, ground_reason = _entry_grounded_in_raw(entry, raw)
        if not grounded:
            return {
                "status": "rejected",
                "reason": ground_reason,
                "provider": provider,
                "verify_provider": check_provider,
            }
    if _dedupe(entry):
        return {"status": "duplicate", "reason": "entrée déjà présente dans la base", "confidence": confidence}

    try:
        store_module.get_store().add("knowledge", entry)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": f"écriture impossible : {exc}", "retryable": True}

    return {
        "status": "added",
        "entry": entry,
        "confidence": round(confidence, 2),
        "provider": provider,
        "verify_provider": check_provider,
        "studied_at": _now_iso(),
    }


def _to_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
