"""Analyseur automatique de discussions — 1 cellule Colab (copier-coller ou téléchargement).

Ce script est le « pilotage » complet demandé par le projet : tu fournis UNE clé
Mistral, tu sélectionnes 1 à N de TES discussions (stockées dans le localStorage
du navigateur, clé `aiis.convos.v1`), et le script — piloté par
`ministral-8b-latest` — fait TOUT :

  1. EXTRACTION  : pour chaque discussion, Mistral extrait les affirmations
                   factuelles vérifiables (dates, personnes, événements,
                   versions, nombres) + la requête de recherche web optimale.
  2. RECHERCHE   : le script exécute ces recherches (multi-moteurs SANS clé :
                   DuckDuckGo HTML → DDG lite → Wikipédia FR/EN + lecture des
                   meilleures pages, robots.txt honoré — même cascade que
                   colab/main.py v2, « pleine puissance Colab »).
  3. VÉRIFICATION: pour chaque affirmation, Mistral rend un verdict sourcé :
                   correcte / incorrecte (avec la correction) / invérifiable.
                   Si invérifiable, Mistral reformule la requête → 2e essai.
  4. BASE DE DONNÉES : Mistral propose le patch de la base de connaissances
                   (corrections si une info est fausse, ajouts si absente).
                   La base distante (GET /api/data/entries du site) est
                   récupérée en amont ; le patch est poussé au site en
                   fin de run (POST /api/data/entries — endpoint dédié ;
                   repli automatique sur une note de recherche si le serveur
                   est encore sur l'ancienne version).
  5. RENDU STRUCTURÉ : rapport console + 3 fichiers téléchargeables :
                   rapport_analyse_discussions.md (humain),
                   analyse_discussions_<ts>.json (machine, complet),
                   knowledge_base_maj.json (base complète après corrections).

Sécurité (mêmes règles que main.py v2) :
- la clé Mistral est saisie en `getpass` (jamais affichée), vit EN RAM
  uniquement, est expurgée de tous les logs/rappports/payloads (redact()) ;
- les discussions ne quittent le notebook que vers l'API Mistral (analyse)
  et le site (rendu) — jamais vers un moteur de recherche ;
- la clé n'est JAMAIS poussée au site (les payloads sont expurgés).

Coût (tier gratuit Mistral) : ~1 ping + par discussion 1 extraction +
1 verdict par affirmation (≤ MAX_CLAIMS, max 1 reformulation) + 1 patch
base ≈ 8 appels MAX par discussion, sur `ministral-8b-latest` (le modèle le
plus économe du pool — cf. docs/FREE-TIERS.md). Throttle intégré : ≥1.05 s
entre deux appels (la limite ~1 req/s de la clé gratuite).

Exécution :
- Google Colab : ouvre colab/analyze_discussions.ipynb (1 cellule) OU colle
  ce script tel quel dans une cellule vierge → Run.
- En local :  python colab/analyze_discussions.py
  (dépannage : ANALYZER_OUT=/tmp/xxx python colab/analyze_discussions.py)

Dépendances : stdlib uniquement (requests/bs4 utilisés si présents, comme main.py).
"""
from __future__ import annotations

import base64
import html as _html
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

SCRIPT_VERSION = 1
REPO = "Snowoo-2z/AI-improves-itself"

# ----------------------------------------------------------------- CONFIG ----
#: URL du site (base de connaissances + push). Vide = 100 % local
#: (base à coller ou vide, rapport local seulement, aucun push).
MAIN_SITE_URL = "https://aiis-core.onrender.com"
MISTRAL_API_BASE = "https://api.mistral.ai/v1"
MISTRAL_MODEL = "ministral-8b-latest"   # le 8B : même pool gratuit que Small 4,
                                        # ~10× moins de tokens par réponse
MAX_CONVERSATIONS = 10   # discussions max par run (sélection utilisateur)
MAX_CLAIMS = 6           # affirmations vérifiables max par discussion
SEARCH_RESULTS = 5       # résultats par recherche web
FETCH_TOP = 1            # pages lues par recherche (0 = titres/extraits seuls)
MIN_CONFIDENCE = 0.55    # confiance min pour qu'une entrée de base soit écrite
PUSH_TO_SITE = True      # False = rapport local seulement
CALL_INTERVAL_S = 1.05   # throttle Mistral (limite ~1 req/s de la clé gratuite)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Colab ? (les fichiers de sortie vont dans /content, downloads automatiques).
IS_COLAB = os.path.isdir("/content") and os.access("/content", os.W_OK)

# ------------------------------------------------------------ optionnels ----
try:  # préinstallés sur Colab ; absents → repli stdlib (urllib + regex)
    import requests as _requests  # type: ignore

    _HAS_REQUESTS = True
except Exception:  # noqa: BLE001
    _requests = None  # type: ignore
    _HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup as _BS  # type: ignore

    _HAS_BS4 = True
except Exception:  # noqa: BLE001
    _BS = None  # type: ignore
    _HAS_BS4 = False


def http_engine() -> str:
    return ("requests" if _HAS_REQUESTS else "urllib") + "+" + ("bs4" if _HAS_BS4 else "regex")


# ------------------------------------------------------------ utilitaires ----
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today_string() -> str:
    """Date du jour pour l'IA (sinon elle ne peut pas dater une info web)."""
    from datetime import datetime

    return datetime.now().astimezone().strftime("%A %d %B %Y (%Z)")


def redact(text: str, secrets) -> str:
    """Expurge les secrets d'un texte (logs, erreurs, rapports, payloads)."""
    out = str(text or "")
    for s in secrets or []:
        if s and len(str(s)) > 6:
            out = out.replace(str(s), "***CLE-MASQUEE***")
    return out


def parse_llm_json(raw: str) -> dict | None:
    """Parse tolérant du JSON renvoyé par un LLM (pur, ```json fencé, ou noyé)."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        js = json.loads(text)
        return js if isinstance(js, dict) else None
    except ValueError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if m:
        try:
            js = json.loads(m.group(1))
            return js if isinstance(js, dict) else None
        except ValueError:
            pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            js = json.loads(m.group(0))
            return js if isinstance(js, dict) else None
        except ValueError:
            return None
    return None


def _norm_title(s: str) -> str:
    return " ".join((s or "").lower().split())


# ------------------------------------------------------------------- HTTP ----
def _http_get(url: str, timeout: int = 30, retries: int = 1) -> tuple[int, str, str]:
    """GET avec réessais. Retourne (status, texte, url_finale). Lève en échec."""
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
    }
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if _HAS_REQUESTS:
                r = _requests.get(url, headers=headers, timeout=timeout)
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code} sur {url[:90]}")
                return r.status_code, r.text or "", str(r.url)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                try:
                    text = raw.decode(charset, errors="replace")
                except LookupError:
                    text = raw.decode("utf-8", errors="replace")
                return resp.status, text, resp.geturl()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"GET impossible après {retries + 1} essai(s) : {last}")


def _http_json(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict | None = None,
    timeout: int = 30,
) -> tuple[int, dict | None]:
    """Appel JSON (API du site). Retourne (status, dict|None) sans lever sur
    les erreurs HTTP (l'appelant décide : 404 = serveur ancien, etc.)."""
    heads = {"User-Agent": UA, "Accept": "application/json"}
    if payload is not None:
        heads["Content-Type"] = "application/json"
    if headers:
        heads.update(headers)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    if _HAS_REQUESTS:
        r = _requests.request(method, url, data=body, headers=heads, timeout=timeout)
        try:
            data = r.json()
        except ValueError:
            data = None
        return r.status_code, data if isinstance(data, dict) else None
    req = urllib.request.Request(url, data=body, headers=heads, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw.strip() else None
            except ValueError:
                data = None
            return resp.status, data if isinstance(data, dict) else None
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            raw = ""
        try:
            data = json.loads(raw) if raw.strip() else None
        except ValueError:
            data = {"_raw": raw[:300]}
        return exc.code, data if isinstance(data, dict) else None


def _post_json_raw(url: str, payload: dict, headers: dict, timeout: int) -> tuple[int, dict | None, dict]:
    """POST JSON → (status, json|None, headers). Lève sur erreur RÉSEAU
    uniquement (coupure/timeout) — les statuts HTTP sont renvoyés."""
    heads = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    heads.update(headers or {})
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if _HAS_REQUESTS:
        r = _requests.post(url, data=body, headers=heads, timeout=timeout)
        try:
            data = r.json()
        except ValueError:
            data = None
        return r.status_code, data, {str(k).lower(): str(v) for k, v in (r.headers or {}).items()}
    req = urllib.request.Request(url, data=body, headers=heads, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw.strip() else None
            except ValueError:
                data = None
            return resp.status, data, {str(k).lower(): str(v) for k, v in (resp.headers or {}).items()}
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            raw = ""
        try:
            data = json.loads(raw) if raw.strip() else None
        except ValueError:
            data = {"_raw": raw[:300]}
        return exc.code, data, {str(k).lower(): str(v) for k, v in (exc.headers or {}).items()}


# ------------------------------------------------------- extraction HTML ----
_STRIP_TAGS_RE = re.compile(r"(?s)<[^>]+>")
_WS_RE = re.compile(r"[ \t\xa0]+")
_BLANK_LINES_RE = re.compile(r"\n\s*\n+")


def _normalize_ws(text: str) -> str:
    text = _WS_RE.sub(" ", text or "")
    text = _BLANK_LINES_RE.sub("\n", text)
    return text.strip()


def extract_title(html_text: str) -> str:
    if _HAS_BS4:
        try:
            t = _BS(html_text, "html.parser").title
            return t.get_text(" ", strip=True)[:300] if t else ""
        except Exception:  # noqa: BLE001
            pass
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text or "")
    if not m:
        return ""
    return _html.unescape(_STRIP_TAGS_RE.sub(" ", m.group(1))).strip()[:300]


def html_to_text(html_text: str, max_chars: int = 12000) -> str:
    """Extraction de texte : priorise <article>/<main>, jette le chrome."""
    if _HAS_BS4:
        try:
            soup = _BS(html_text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
                tag.decompose()
            main = soup.find("article") or soup.find("main") or soup.body or soup
            text = main.get_text("\n")
            return _normalize_ws(text)[:max_chars].strip()
        except Exception:  # noqa: BLE001
            pass
    text = re.sub(
        r"(?is)<(script|style|nav|footer|header|aside|form|noscript)[^>]*>.*?</\1>",
        " ",
        html_text or "",
    )
    m = re.search(r"(?is)<(article|main)[^>]*>(.*?)</\1>", text)
    if m and len(m.group(2)) > 500:
        text = m.group(2)
    text = _STRIP_TAGS_RE.sub(" ", text)
    return _normalize_ws(_html.unescape(text))[:max_chars].strip()


# --------------------------------------------------------------- recherche ---
def _unwrap_ddg(link: str) -> str:
    try:
        if "uddg=" in link:
            return urllib.parse.unquote(re.search(r"uddg=([^&]+)", link).group(1))  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        pass
    return link


def parse_ddg_html(html_text: str, max_results: int = 5) -> list[dict]:
    out: list[dict] = []
    pattern = re.compile(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    matches = list(pattern.finditer(html_text or ""))
    for i, m in enumerate(matches):
        link = _unwrap_ddg(_html.unescape(m.group(1)).strip())
        title = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", m.group(2))))[:300]
        end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 3000
        chunk = (html_text or "")[m.end(): end]
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', chunk, re.S)
        snippet = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", snip.group(1))))[:500] if snip else ""
        if link.startswith("//"):
            link = "https:" + link
        out.append({"title": title or "(sans titre)", "url": link, "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


def parse_ddg_lite(html_text: str, max_results: int = 5) -> list[dict]:
    out: list[dict] = []
    pattern = re.compile(r'<a\s+rel="nofollow"\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
    matches = list(pattern.finditer(html_text or ""))
    for i, m in enumerate(matches):
        link = _unwrap_ddg(_html.unescape(m.group(1)).strip())
        title = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", m.group(2))))[:300]
        end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 1500
        chunk = (html_text or "")[m.end(): end]
        snip = re.search(r"result-snippet['\"]?\s*>(.*?)</td>", chunk, re.S | re.I)
        snippet = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", snip.group(1))))[:500] if snip else ""
        if link.startswith("//"):
            link = "https:" + link
        if "duckduckgo.com/" in link and "uddg=" not in m.group(1):
            continue
        out.append({"title": title or "(sans titre)", "url": link, "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


def wikipedia_search(query: str, lang: str = "fr", max_results: int = 5, timeout: int = 20) -> list[dict]:
    api = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(query)}&format=json&srlimit={max_results}&srprop=snippet"
    )
    _status, text, _final = _http_get(api, timeout=timeout, retries=1)
    data = json.loads(text)
    out = []
    for it in (data.get("query", {}).get("search", []) or [])[:max_results]:
        title = it.get("title", "")
        url = f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        snippet = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", it.get("snippet", ""))))[:500]
        out.append({"title": title, "url": url, "snippet": snippet})
    return out


def web_search(query: str, max_results: int = 5) -> dict:
    """Recherche multi-moteurs avec fallbacks (même cascade que main.py v2) :
    DDG HTML → DDG lite → Wikipédia FR → Wikipédia EN."""
    q = (query or "").strip()
    errors: dict[str, str] = {}
    try:
        _status, text, _final = _http_get(
            "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(q), timeout=25, retries=1
        )
        found = parse_ddg_html(text, max_results)
        if found:
            return {"results": found, "engine": "ddg-html", "query": q}
        errors["ddg-html"] = "0 résultat parsé (page inattendue ou challenge)"
    except Exception as exc:  # noqa: BLE001
        errors["ddg-html"] = str(exc)[:160]
    time.sleep(1.0)
    try:
        _status, text, _final = _http_get(
            "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote_plus(q), timeout=25, retries=1
        )
        found = parse_ddg_lite(text, max_results)
        if found:
            return {"results": found, "engine": "ddg-lite", "query": q}
        errors["ddg-lite"] = "0 résultat parsé"
    except Exception as exc:  # noqa: BLE001
        errors["ddg-lite"] = str(exc)[:160]
    for lang in ("fr", "en"):
        try:
            found = wikipedia_search(q, lang=lang, max_results=max_results)
            if found:
                return {"results": found, "engine": f"wikipedia-{lang}", "query": q}
            errors[f"wikipedia-{lang}"] = "0 résultat"
        except Exception as exc:  # noqa: BLE001
            errors[f"wikipedia-{lang}"] = str(exc)[:160]
    return {
        "results": [],
        "engine": "none",
        "query": q,
        "error": "aucun résultat (" + "; ".join(f"{k}: {v}" for k, v in errors.items()) + ")",
    }


_ROBOTS_CACHE: dict[str, urllib.robotparser.RobotFileParser] = {}


def can_fetch(url: str, _get=None) -> bool:
    """Honore le robots.txt de la cible (best-effort : injoignable → on tente)."""
    try:
        parts = urllib.parse.urlparse(url or "")
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return False
        host = parts.netloc.lower()
        if host not in _ROBOTS_CACHE:
            rp = urllib.robotparser.RobotFileParser()
            try:
                if _get is not None:
                    _s, body, _f = _get(f"{parts.scheme}://{host}/robots.txt", timeout=10)
                else:
                    _s, body, _f = _http_get(f"{parts.scheme}://{host}/robots.txt", timeout=10, retries=0)
                rp.parse((body or "").splitlines())
            except Exception:  # noqa: BLE001
                return True
            _ROBOTS_CACHE[host] = rp
        return _ROBOTS_CACHE[host].can_fetch("*", url)
    except Exception:  # noqa: BLE001
        return True


def fetch_url(url: str, max_chars: int = 12000, timeout: int = 30) -> dict:
    if not can_fetch(url):
        return {"url": url, "title": "", "text": "", "robots_blocked": True,
                "error": "robots.txt : fetch refusé par le site cible"}
    status, text, final = _http_get(url, timeout=timeout, retries=1)
    body = html_to_text(text, max_chars=max_chars)
    return {"url": final or url, "http_status": status,
            "title": extract_title(text), "text": body}


def _enrich_with_pages(results: list[dict], fetch_top: int, text_clip: int = 3000) -> list[dict]:
    for it in (results or [])[: max(0, fetch_top)]:
        u = (it.get("url") or "").strip()
        if not u.startswith(("http://", "https://")):
            continue
        try:
            page = fetch_url(u, max_chars=text_clip + 1500)
            if page.get("text"):
                it["text"] = page["text"][:text_clip]
            if page.get("title") and not it.get("title"):
                it["title"] = page["title"]
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.0)
    return results


# ---------------------------------------------------------------- Mistral ----
#: Throttle global (clé gratuite Mistral ≈ 1 req/s, tous modèles confondus).
_last_mistral_call = [0.0]


def _mistral_throttle(_sleep=time.sleep) -> None:
    wait = CALL_INTERVAL_S - (time.time() - _last_mistral_call[0])
    if wait > 0:
        _sleep(wait)
    _last_mistral_call[0] = time.time()


def _parse_retry_after(value) -> float | None:
    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def mistral_call(
    cfg: dict,
    system: str,
    user: str,
    max_tokens: int = 1000,
    timeout: int = 120,
    _sleep=time.sleep,
) -> tuple[str | None, str | None]:
    """UN appel chat Mistral (OpenAI-compatible). Retourne (content|None, erreur|None).

    Gestion des 429 calée sur le tier gratuit : pause sur `Retry-After`
    (plafonnée à 75 s), 1 relance max, jamais de rafale.
    """
    _mistral_throttle(_sleep)
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    last_err = "échec inconnu"
    for _attempt in (1, 2):
        try:
            status, data, headers = _post_json_raw(
                url, body, {"Authorization": f"Bearer {cfg['api_key']}"}, timeout
            )
        except Exception as exc:  # noqa: BLE001 — panne réseau : 1 relance
            last_err = redact(f"réseau : {exc}", cfg.get("secrets"))
            _sleep(3.0)
            continue
        if status == 200:
            try:
                content = (data["choices"][0]["message"].get("content") or "").strip()  # type: ignore[index]
            except (TypeError, KeyError, IndexError):
                return None, redact(f"réponse inattendue : {json.dumps(data)[:200]}", cfg.get("secrets"))
            return (content or None), (None if content else "réponse vide du modèle")
        if status == 401:
            return None, "clé API refusée (401) — vérifie ta clé Mistral (La Plateforme)."
        if status == 404:
            return None, f"modèle '{cfg['model']}' introuvable (404) — vide MISTRAL_MODEL dans le CONFIG."
        if status == 429:
            ra = _parse_retry_after(headers.get("retry-after"))
            last_err = f"quota Mistral atteint (429) — {'pause ' + str(int(ra)) + 's' if ra else 'fenêtre ~1 min'}"
            _sleep(min(ra + 1.0, 75.0) if ra else 65.0)
            continue
        last_err = redact(f"HTTP {status} : {json.dumps(data)[:200]}", cfg.get("secrets"))
        _sleep(5.0)
    return None, last_err


def mistral_ping(cfg: dict, timeout: int = 45) -> tuple[bool, str]:
    content, err = mistral_call(cfg, "Réponds uniquement : pong", "ping", max_tokens=5, timeout=timeout)
    if content:
        return True, f"{cfg['model']} OK (réponse : {content[:30]})"
    return False, redact(err or "échec du ping", cfg.get("secrets"))


# ---------------------------------------------------------------- prompts ----
EXTRACT_SYSTEM = (
    "Tu es l'étape « extraction » de l'analyseur de discussions du projet "
    "AI-improves-itself. Tu lis une discussion utilisateur/IA et tu extrais les "
    "AFFIRMATIONS FACTUELLES vérifiables qu'elle contient (dates, personnes, "
    "événements, versions, chiffres, lieux). L'IA va ensuite les vérifier sur le web.\n"
    "Réponds UNIQUEMENT en JSON valide (pas de markdown, pas de prose) :\n"
    '{"summary": "résumé de la discussion en 2-3 phrases factuelles",\n'
    ' "topics": ["sujet court 1", "sujet court 2"],\n'
    ' "claims": [{"claim": "affirmation factuelle autonome, concise et datée si possible",\n'
    '             "type": "date|personne|evenement|version|nombre|autre",\n'
    '             "quote": "l\'extrait exact du message qui la contient (≤ 200 car.)",\n'
    '             "search_query": "requête de recherche web optimale (français ou anglais)",\n'
    '             "check": true}]}\n'
    "- check=true seulement pour une info factuelle qui a un intérêt de vérification.\n"
    "- check=false (à NE PAS mettre dans claims) : opinions, questions, blagues, "
    "instructions, contexte non factuel.\n"
    "- Les claims les plus importantes d'abord ; ne dépasse JAMAIS le maximum demandé.\n"
    "- Ne t'invente rien : si aucune affirmation factuelle, claims vaut [] (liste vide)."
)


def _extract_user(convo: dict, text: str, max_claims: int) -> str:
    return (
        f"Aujourd'hui : {_today_string()}\n"
        f"Maximum d'affirmations à extraire : {max_claims}.\n\n"
        f"Discussion « {convo.get('title', '?')} » ({len(convo.get('messages', []))} messages) :\n"
        f"{text}"
    )


VERDICT_SYSTEM = (
    "Tu es l'étape « vérification » de l'analyseur de discussions du projet "
    "AI-improves-itself. Tu reçois une affirmation extraite d'une discussion et "
    "les preuves web récupérées pour elle. Décide, SUR LA BASE DES PREUVES "
    "UNIQUEMENT, si l'affirmation est correcte.\n"
    "Réponds UNIQUEMENT en JSON valide (pas de markdown, pas de prose) :\n"
    '{"verdict": "correcte|incorrecte|inverifiable",\n'
    ' "correction": "si incorrecte : la version correcte, sinon string vide",\n'
    ' "sources": ["url principale", "url secondaire éventuelle"],\n'
    ' "note": "justification en une phrase",\n'
    ' "confidence": 0.0}\n'
    "- confidence : 0 à 1, ta certitude SOUTENUE par les preuves.\n"
    "- N'invente rien : sans preuve suffisante dans les extraits, verdict = "
    "\"inverifiable\" (jamais \"correcte\" par mémoire).\n"
    "- « incorrecte » seulement si une preuve contredit explicitement l'affirmation."
)


def _evidence_lines(evidence: dict) -> str:
    lines = []
    for i, it in enumerate((evidence.get("results") or [])[:SEARCH_RESULTS], 1):
        if not isinstance(it, dict):
            continue
        line = f"{i}. {str(it.get('title', '?'))[:150]} — {str(it.get('url', ''))[:120]}"
        if it.get("snippet"):
            line += f"\n   extrait : {str(it['snippet'])[:300]}"
        if it.get("text"):
            line += f"\n   contenu : {str(it['text'])[:1500]}"
        lines.append(line)
    return "\n".join(lines) if lines else "aucun résultat de recherche"


def _verdict_user(claim: dict, evidence: dict) -> str:
    return (
        f"Aujourd'hui : {_today_string()}\n\n"
        f"Affirmation à vérifier : « {claim.get('claim', '')} »\n"
        f"(type : {claim.get('type', '?')} · extrait de la discussion : « {str(claim.get('quote', ''))[:200]} »)\n\n"
        f"Preuves web (moteur : {evidence.get('engine', 'none')} · requête : « {evidence.get('query', '')} ») :\n"
        + _evidence_lines(evidence)
    )


REFORMULATE_SYSTEM = (
    "Tu es le pilote recherche de l'analyseur de discussions (projet "
    "AI-improves-itself). Une recherche web n'a pas permis de vérifier une "
    "affirmation. Propose UNE nouvelle requête de recherche web (français ou "
    "anglais, 3 à 10 mots) plus précise pour la vérifier.\n"
    "Réponds UNIQUEMENT par la requête, sans guillemets ni point final."
)


def _reformulate_user(claim: dict, evidence: dict) -> str:
    return (
        f"Affirmation : « {claim.get('claim', '')} »\n"
        f"Requête déjà essayée (sans résultat exploitable) : « {evidence.get('query', '')} »\n"
        f"Moteur : {evidence.get('engine', 'none')} · {len(evidence.get('results') or [])} résultat(s)."
    )


KBPATCH_SYSTEM = (
    "Tu es l'étape « mise à jour de la base de connaissances » de l'analyseur de "
    "discussions du projet AI-improves-itself. La base a ce format d'entrée : "
    "{title, category, date (ISO \"AAAA-MM-JJ\" ou vide), summary, source} — "
    "category : thème court en minuscules (ia, jeux-vidéo, infra, web, science…); "
    "summary : 1 à 3 phrases factuelles sourcées ; source : URL de la preuve "
    "principale ou \"colab-analyseur\".\n"
    "À partir de l'analyse de la discussion (affirmations + verdicts + corrections), "
    "propose le patch de la base. Réponds UNIQUEMENT en JSON valide :\n"
    '{"entries": [{"action": "add|update",\n'
    '   "match_title": "si update : le titre EXACT de l\'entrée existante à corriger, sinon vide",\n'
    '   "entry": {"title": "...", "category": "...", "date": "AAAA-MM-JJ ou vide",\n'
    '             "summary": "...", "source": "..."},\n'
    '   "reason": "pourquoi (info corrigée ou ajoutée + preuve)",\n'
    '   "confidence": 0.0}],\n'
    ' "assessment": {"overall_confidence": 0.0,\n'
    '   "issues": ["problème d\'exactitude constaté dans la discussion"],\n'
    '   "positives": ["point d\'exactitude confirmé"]}}\n'
    "Règles strictes :\n"
    "- update : UNIQUEMENT si une entrée existante (listée) contient une info "
    "démontrément fausse par les verdicts → tu corriges (summary/date), garde le titre.\n"
    "- add : info factuelle vérifiée (verdict « correcte ») ou correction sourcée, "
    "ABSENTE de la base existante.\n"
    "- Ne propose RIEN pour un verdict « inverifiable ».\n"
    "- entries = [] si rien à faire (c'est fréquent, ne force rien).\n"
    "- confidence : ta certitude que l'entrée est exacte et bien sourcée."
)


def _kbpatch_user(convo: dict, analysis: dict) -> str:
    kb_view = "\n".join(
        f"- {e.get('title', '?')} — {str(e.get('summary', ''))[:180]}"
        for e in (analysis.get("_kb_view") or [])
    ) or "(base vide)"
    lines = []
    for i, cl in enumerate(analysis.get("claims") or [], 1):
        v = cl.get("verdict") or {}
        lines.append(
            f"[{i}] {v.get('verdict', '?')} : « {cl.get('claim', '')} »"
            + (f" → correction : « {v.get('correction')} »" if v.get("correction") else "")
            + f" (confiance {v.get('confidence', 0)})"
            + (f" · sources : {', '.join(v.get('sources') or [])[:200]}" if v.get("sources") else "")
        )
    return (
        f"Aujourd'hui : {_today_string()}\n\n"
        f"=== Base de connaissances existante (titres — summaries) ===\n{kb_view}\n\n"
        f"=== Discussion analysée : « {convo.get('title', '?')} » ===\n"
        f"Résumé : {analysis.get('summary', '')}\n"
        f"Sujets : {', '.join(analysis.get('topics') or []) or '(aucun)'}\n\n"
        f"Affirmations et verdicts :\n" + "\n".join(lines or "(aucune)")
    )


# ------------------------------------------------------------- discussions ---
def messages_to_text(content, max_chars: int = 2500) -> str:
    """Texte d'un message : string ou blocs [text, image_url…] (images écartées)."""
    if isinstance(content, str):
        return content.strip()[:max_chars]
    if isinstance(content, list):
        parts = [str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)[:max_chars]
    return ""


def _convo_title_from_msgs(msgs: list[dict]) -> str:
    for m in msgs:
        if m.get("role") == "user" and m.get("content"):
            return str(m["content"]).strip().split("\n")[0][:60]
    return ""


def parse_discussions_payload(raw) -> dict | None:
    """Décode le payload exporté du navigateur.

    Accepte : base64 (une ligne, le format copié par l'export), JSON brut
    (str/bytes commençant par { ou [), ou un dict déjà chargé.
    Retourne {"conversations": [...], "source": ...} ou None.
    Chaque conversation est normalisée : {id, title, messages:[{role, content:str}]}.
    """
    data = None
    try:
        if isinstance(raw, dict):
            data = raw
        else:
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            s = str(raw or "").strip()
            if not s:
                return None
            if s[0] in "{[":
                data = json.loads(s)
            else:
                b64 = re.sub(r"\s+", "", s)
                data = json.loads(base64.b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    convos = data.get("conversations") if isinstance(data, dict) else data
    if not isinstance(convos, list) or not convos:
        return None
    out = []
    for c in convos[:50]:
        if not isinstance(c, dict):
            continue
        msgs = c.get("messages")
        if not isinstance(msgs, list):
            continue
        norm_msgs = []
        for m in msgs:
            if not isinstance(m, dict):
                continue
            role = "user" if m.get("role") == "user" else "assistant"
            txt = messages_to_text(m.get("content"))
            if txt:
                norm_msgs.append({"role": role, "content": txt})
        if not norm_msgs:
            continue
        out.append(
            {
                "id": str(c.get("id") or ""),
                "title": str(c.get("title") or _convo_title_from_msgs(norm_msgs) or "Sans titre")[:120],
                "createdAt": c.get("createdAt"),
                "updatedAt": c.get("updatedAt"),
                "messages": norm_msgs,
            }
        )
    if not out:
        return None
    return {"conversations": out, "source": (data.get("export_type") if isinstance(data, dict) else "raw") or "raw"}


def conversation_text(convo: dict, total_cap: int = 14000) -> str:
    """Discussion → texte « Utilisateur : … / IA : … » borné (contexte LLM)."""
    lines: list[str] = []
    total = 0
    for m in convo.get("messages", []):
        role = "Utilisateur" if m.get("role") == "user" else "IA"
        txt = str(m.get("content") or "").strip()
        if not txt:
            continue
        line = f"{role} : {txt}"
        lines.append(line)
        total += len(line)
        if total > total_cap:
            break
    return "\n".join(lines)


# ---------------------------------------------------------------- analyse ----
def _run_search(query: str, search) -> dict:
    found = search(query, max_results=SEARCH_RESULTS)
    results = found.get("results", [])
    if FETCH_TOP and results:
        _enrich_with_pages(results, FETCH_TOP)
    return {
        "query": found.get("query", query),
        "engine": found.get("engine", "none"),
        "results": results,
        "error": found.get("error"),
    }


def _verdict_cfg(cfg, llm, claim: dict, evidence: dict) -> dict:
    content, err = llm(cfg, VERDICT_SYSTEM, _verdict_user(claim, evidence), max_tokens=350)
    js = parse_llm_json(content) if content else None
    if not isinstance(js, dict):
        return {"verdict": "inverifiable", "correction": "", "sources": [],
                "note": f"réponse du modèle illisible ({(err or '')[:120]})", "confidence": 0.0}
    verdict = str(js.get("verdict") or "inverifiable").strip()
    if verdict not in ("correcte", "incorrecte", "inverifiable"):
        verdict = "inverifiable"
    try:
        confidence = float(js.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "verdict": verdict,
        "correction": str(js.get("correction") or "")[:400],
        "sources": [str(u)[:200] for u in (js.get("sources") or [])[:3] if str(u).strip()],
        "note": str(js.get("note") or "")[:300],
        "confidence": round(min(1.0, max(0.0, confidence)), 2),
    }


def _clean_plan(js: dict) -> list[dict]:
    """Normalise le patch de base proposé par le modèle (5 entrées max)."""
    out: list[dict] = []
    for p in (js.get("entries") or [])[:5]:
        if not isinstance(p, dict):
            continue
        action = str(p.get("action") or "").strip()
        if action not in ("add", "update"):
            continue
        entry = p.get("entry")
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        summary = str(entry.get("summary") or "").strip()
        if not title or not summary:
            continue
        date = str(entry.get("date") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            date = ""
        try:
            confidence = float(p.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        out.append(
            {
                "action": action,
                "match_title": str(p.get("match_title") or "")[:200],
                "entry": {
                    "title": title[:200],
                    "category": (str(entry.get("category") or "").strip()[:40] or "divers"),
                    "date": date,
                    "summary": summary[:1500],
                    "source": (str(entry.get("source") or "").strip()[:500] or "colab-analyseur"),
                },
                "reason": str(p.get("reason") or "")[:300],
                "confidence": round(min(1.0, max(0.0, confidence)), 2),
            }
        )
    return out


def analyze_conversation(
    cfg: dict,
    convo: dict,
    kb_entries: list[dict],
    max_claims: int = MAX_CLAIMS,
    min_confidence: float = MIN_CONFIDENCE,
    llm=None,
    search=None,
    log=print,
) -> dict:
    """Analyse COMPLÈTE d'une discussion (pilotage Mistral de bout en bout).

    1. extraction des affirmations (1 appel) → 2. recherche web par affirmation
    (sans clé) → 3. verdict sourcé par affirmation (1 appel, +1 reformulation
    si invérifiable) → 4. patch de la base de connaissances (1 appel).

    `llm`/`search` injectables (tests). Retourne un dict d'analyse complet.
    """
    llm = llm or mistral_call
    search = search or web_search
    errors: list[str] = []

    # --- 1. extraction -------------------------------------------------------
    log(f"   🧠 extraction des affirmations ({cfg['model']})…")
    content, err = llm(cfg, EXTRACT_SYSTEM, _extract_user(convo, conversation_text(convo), max_claims), max_tokens=1400)
    js = parse_llm_json(content) if content else None
    if not isinstance(js, dict):
        errors.append(redact(f"extraction impossible : {err or 'réponse illisible'}", cfg.get("secrets")))
        return {"status": "error", "reason": errors[-1], "claims": [], "plan": [], "summary": "", "topics": [], "errors": errors}
    summary = str(js.get("summary") or "")[:600]
    topics = [str(t)[:60] for t in (js.get("topics") or [])[:6] if str(t).strip()]
    claims: list[dict] = []
    for c in (js.get("claims") or [])[:max_claims]:
        if not isinstance(c, dict):
            continue
        claim = str(c.get("claim") or "").strip()
        query = str(c.get("search_query") or "").strip() or claim
        if not claim:
            continue
        claims.append(
            {
                "claim": claim[:400],
                "type": str(c.get("type") or "autre")[:30],
                "quote": str(c.get("quote") or "")[:300],
                "search_query": query[:200],
                "check": bool(c.get("check", True)),
                "attempts": 0,
            }
        )
    log(f"   📋 {len(claims)} affirmation(s) factuelle(s) — résumé : {summary[:120]}")

    # --- 2 + 3. recherche + verdict par affirmation --------------------------
    for i, cl in enumerate(claims, 1):
        if not cl["check"]:
            cl["verdict"] = {"verdict": "non_verifiee", "correction": "", "sources": [],
                             "note": "non factuelle (opinion/contexte)", "confidence": 1.0}
            cl["evidence"] = None
            log(f"   [{i}/{len(claims)}] « {cl['claim'][:60]}… » → non vérifiée (contexte)")
            continue
        log(f"   [{i}/{len(claims)}] 🔎 « {cl['claim'][:70]} »")
        evidence = _run_search(cl["search_query"], search)
        log(f"      moteur : {evidence['engine']} · {len(evidence['results'])} résultat(s)")
        cl["evidence"] = evidence
        verdict = _verdict_cfg(cfg, llm, cl, evidence)
        # Pilotage : invérifiable + preuves faibles → Mistral reformule, 2e essai.
        if (
            verdict["verdict"] == "inverifiable"
            and cl["attempts"] < 1
            and (not evidence["results"] or verdict["confidence"] < 0.5)
        ):
            rq, _e2 = llm(cfg, REFORMULATE_SYSTEM, _reformulate_user(cl, evidence), max_tokens=80)
            new_q = (rq or "").strip().strip("\"'«» \n")
            if new_q and 3 < len(new_q) < 120 and new_q.lower() != cl["search_query"].lower():
                cl["attempts"] = 1
                log(f"      ↻ reformulation : {new_q[:80]}")
                evidence2 = _run_search(new_q, search)
                if evidence2["results"]:
                    cl["search_query"] = new_q
                    cl["evidence"] = evidence2
                    log(f"      moteur : {evidence2['engine']} · {len(evidence2['results'])} résultat(s)")
                    verdict = _verdict_cfg(cfg, llm, cl, evidence2)
        cl["verdict"] = verdict
        mark = {"correcte": "✔", "incorrecte": "✘", "inverifiable": "?"}.get(verdict["verdict"], "·")
        log(f"      {mark} {verdict['verdict']} (confiance {verdict['confidence']})"
            + (f" → {verdict['correction'][:60]}" if verdict["correction"] else ""))

    # --- 4. patch de la base de connaissances --------------------------------
    analysis = {
        "summary": summary,
        "topics": topics,
        "claims": claims,
        "_kb_view": kb_entries[:40],
    }
    log(f"   🗃  plan de mise à jour de la base ({len(kb_entries)} entrée(s) existante(s))…")
    content, err = llm(cfg, KBPATCH_SYSTEM, _kbpatch_user(convo, analysis), max_tokens=1600)
    js2 = parse_llm_json(content) if content else None
    plan = _clean_plan(js2) if isinstance(js2, dict) else []
    if not isinstance(js2, dict):
        errors.append(redact(f"plan de base impossible : {err or 'réponse illisible'}", cfg.get("secrets")))
    kept = [p for p in plan if p["confidence"] >= min_confidence]
    dropped = len(plan) - len(kept)
    assessment = (js2 or {}).get("assessment") if isinstance(js2, dict) else None
    if not isinstance(assessment, dict):
        assessment = {"overall_confidence": None, "issues": [], "positives": []}
    return {
        "status": "ok",
        "summary": summary,
        "topics": topics,
        "claims": claims,
        "plan": kept,
        "plan_dropped_low_confidence": dropped,
        "assessment": {
            "overall_confidence": assessment.get("overall_confidence"),
            "issues": [str(x)[:200] for x in (assessment.get("issues") or [])[:8] if str(x).strip()],
            "positives": [str(x)[:200] for x in (assessment.get("positives") or [])[:8] if str(x).strip()],
        },
        "errors": errors,
    }


# ----------------------------------------------------------- base (merge) ----
def merge_patch(kb: list[dict], plan: list[dict], min_confidence: float = MIN_CONFIDENCE) -> tuple[list[dict], list[dict]]:
    """Applique le patch (add/update) à la base. Retourne (base, actions).

    - update : l'entrée existante au titre correspondant est CORRIGÉE
      (ses métadonnées id/created_at sont conservées),
    - add : ajout ; si le titre existe déjà → mise à jour (pas de doublon).
    """
    kb = [dict(e) for e in kb if isinstance(e, dict)]
    actions: list[dict] = []
    by_title: dict[str, dict] = {}
    for e in kb:
        t = _norm_title(e.get("title", ""))
        if t:
            by_title.setdefault(t, e)
    def _apply_in_place(target: dict, why: str) -> dict:
        """Corrige l'entrée EN PLACE : l'orthographe CANONIQUE du titre existant
        est conservée (un payload « mistral ai » ne réécrit pas « Mistral AI »),
        les métadonnées (id/created_at) survivent à la correction."""
        canonical = str(target.get("title") or entry["title"])
        patch = {k: v for k, v in entry.items() if k != "title"}
        target.update(patch)
        return {"action": "updated", "title": canonical,
                "entry": {"title": canonical, **patch}, "reason": why}

    for p in plan or []:
        if p.get("action") not in ("add", "update"):
            continue  # action inconnue → ignorée (défense en profondeur)
        entry = p.get("entry") or {}
        reason = str(p.get("reason") or "")[:300]
        if p.get("confidence", 0.0) < min_confidence or not entry.get("title"):
            continue
        match_key = _norm_title(p.get("match_title") or entry.get("title", ""))
        target = by_title.get(match_key)
        if p.get("action") == "update" and target is not None:
            actions.append(_apply_in_place(target, reason))
            continue
        t = _norm_title(entry.get("title", ""))
        if t and t in by_title:
            actions.append(_apply_in_place(by_title[t], (reason + " (titre déjà présent : mise à jour)").strip()))
        else:
            new_entry = dict(entry)
            kb.append(new_entry)
            if t:
                by_title[t] = new_entry
            actions.append({"action": "added", "title": entry["title"], "entry": dict(new_entry),
                            "reason": reason})
    return kb, actions


# ------------------------------------------------------------------- site ----
def wake_server(url: str, tries: int = 4, timeout: int = 20, quiet: bool = False) -> tuple[bool, str]:
    """Réveille le serveur (Render gratuit s'endort après 15 min : ~1 min)."""
    if not url:
        return False, "pas d'URL de site (mode local pur)"
    last: Exception | None = None
    for i in range(tries):
        try:
            status, _text, _final = _http_get(url.rstrip("/") + "/health", timeout=timeout, retries=0)
            if status == 200:
                return True, f"serveur joignable ({url})"
            last = RuntimeError(f"HTTP {status} sur /health")
        except Exception as exc:  # noqa: BLE001
            last = exc
        if not quiet:
            print(f"   ⏳ réveil du serveur… essai {i + 1}/{tries} (plan gratuit : ~1 min)")
        if i < tries - 1:
            time.sleep(10)
    return False, f"serveur injoignable après {tries} essais : {str(last)[:160]}"


def fetch_knowledge_base(url: str = MAIN_SITE_URL, prompt=input) -> tuple[list[dict], str]:
    """Base de connaissances existante : site → repli coller → vide.

    Retourne (entrées, provenance: site|colle|vide|erreur).
    """
    if url:
        print(f"📡 base de connaissances — tentative sur le site ({url})…")
        ok, msg = wake_server(url)
        if ok:
            code, data = _http_json("GET", url.rstrip("/") + "/api/data/entries", timeout=30)
            entries = (data or {}).get("entries") if isinstance(data, dict) else None
            if code == 200 and isinstance(entries, list) and all(isinstance(e, dict) for e in entries):
                print(f"   ✅ {len(entries)} entrée(s) récupérée(s).")
                return entries, "site"
        print(f"   ⚠️ {msg or 'réponse illisible du site'}")
    try:
        choice = prompt("   La base distante est inaccessible. [1] coller le JSON de la base, [2] base vide (défaut) : ").strip() or "2"
    except (EOFError, KeyboardInterrupt):
        return [], "vide"
    if choice == "1":
        try:
            raw = prompt("   Colle le JSON de la base (ou réponds avec la ligne base64) : ")
        except (EOFError, KeyboardInterrupt):
            raw = ""
        data = None
        try:
            s = (raw or "").strip()
            if s and s[0] in "{[":
                data = json.loads(s)
            elif s:
                b64 = re.sub(r"\s+", "", s)
                data = json.loads(base64.b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-8"))
        except (ValueError, TypeError):
            data = None
        entries = data.get("entries") if isinstance(data, dict) else data
        if isinstance(entries, list) and all(isinstance(e, dict) for e in entries):
            print(f"   ✅ {len(entries)} entrée(s) chargée(s) à la main.")
            return entries, "colle"
        print("   ⚠️ JSON illisible — base vide.")
    return [], "vide"


def push_to_site(actions: list[dict], report_md: str, url: str = MAIN_SITE_URL, secrets: tuple = ()) -> dict:
    """Pousse le patch de base au site.

    Mode direct : POST /api/data/entries (endpoint dédié — serveur à jour).
    Repli : POST /api/research/results (kind=note) si le serveur est encore sur
    l'ancienne version (404/405) : le site étudiera la note plus tard.
    """
    if not url:
        return {"mode": "local", "detail": "pas d'URL de site — rapport local uniquement"}
    if not PUSH_TO_SITE:
        return {"mode": "local", "detail": "PUSH_TO_SITE=False — rapport local uniquement"}
    entries = [a["entry"] for a in actions if a["action"] in ("added", "updated")]
    if not entries:
        return {"mode": "aucune-change", "detail": "aucune action sur la base — rien à pousser"}
    ok, msg = wake_server(url)
    if not ok:
        return {"mode": "injoignable", "detail": msg}
    payload = {
        "entries": entries,
        "updated_by": "colab-analyseur",
        "note": "analyseur de discussions Colab (vérifications web sourcées)"[:500],
    }
    safe = json.loads(redact(json.dumps(payload, ensure_ascii=False), secrets))
    try:
        code, data = _http_json("POST", url.rstrip("/") + "/api/data/entries", safe, timeout=45)
    except Exception as exc:  # noqa: BLE001
        return {"mode": "erreur", "detail": redact(str(exc), secrets)[:200]}
    if code == 200 and isinstance(data, dict):
        return {"mode": "direct", "code": 200, **(data or {})}
    if code in (404, 405):
        print(f"   ⚠️ serveur sans /api/data/entries (HTTP {code}) — repli : note de recherche.")
        note_payload = {
            "kind": "note",
            "task_id": None,
            "data": {
                "content": redact(report_md[:8000], secrets),
                "meta": {"origin": "colab-analyseur", "entries": safe["entries"]},
            },
        }
        try:
            code2, _d2 = _http_json("POST", url.rstrip("/") + "/api/research/results", note_payload, timeout=45)
            if code2 == 200:
                return {"mode": "repli-note", "detail": "note poussée — le site l'étudiera quand son moteur est disponible"}
            return {"mode": "erreur", "detail": f"repli refusé (HTTP {code2})"}
        except Exception as exc:  # noqa: BLE001
            return {"mode": "erreur", "detail": redact(str(exc), secrets)[:200]}
    return {"mode": "erreur", "detail": f"POST /api/data/entries refusé (HTTP {code})"}


# ---------------------------------------------------------------- rapports ---
_VERDICT_MARK = {"correcte": "✔", "incorrecte": "✘", "inverifiable": "?", "non_verifiee": "·"}


def build_markdown(report: dict) -> str:
    L: list[str] = []
    L.append("# Rapport d'analyse des discussions — AI-improves-itself")
    L.append("")
    L.append(f"- **Date** : {report['generated_at']}  ")
    L.append(f"- **Modèle** : {report['model']}  ")
    L.append(f"- **Durée** : {report['duration_s']} s  ")
    L.append(f"- **Discussions analysées** : {len(report['discussions'])}  ")
    s = report["stats"]
    L.append(f"- **Affirmations** : {s['claims']} au total — "
             f"✔ {s['correct']} · ✘ {s['incorrect']} · ? {s['unverifiable']} · · {s['unchecked']}  ")
    L.append(f"- **Requêtes web** : {s['searches']} (moteurs : {', '.join(s['engines']) or 'aucun'})  ")
    L.append(f"- **Base de connaissances** : {s['kb_before']} → {s['kb_after']} entrées "
             f"(+{s['added']} ajout(s), {s['updated']} mise(s) à jour)")
    if report["push"]:
        L.append(f"- **Push site** : {report['push'].get('mode')} {str(report['push'].get('detail') or '')[:160]}")
    L.append("")
    for i, d in enumerate(report["discussions"], 1):
        L.append(f"## Discussion {i} : « {d['title']} »")
        L.append("")
        L.append(f"*{d.get('messages', '?')} messages · {d['status']}*")
        if d.get("summary"):
            L.append(f"**Résumé** : {d['summary']}")
        if d.get("errors"):
            for e in d["errors"]:
                L.append(f"> ⚠️ {e}")
        claims = d.get("claims") or []
        if claims:
            L.append("")
            L.append("| # | Affirmation | Verdict | Correction | Conf. | Sources |")
            L.append("|---|---|---|---|---|---|")
            for j, cl in enumerate(claims, 1):
                v = cl.get("verdict") or {}
                src = ", ".join(v.get("sources") or [])[:120]
                L.append(
                    f"| {j} | {str(cl.get('claim', ''))[:140]} "
                    f"| {_VERDICT_MARK.get(v.get('verdict', '?'), '?')} {v.get('verdict', '?')} "
                    f"| {str(v.get('correction', ''))[:100] or '—'} "
                    f"| {v.get('confidence', 0)} | {src or '—'} |"
                )
        acts = d.get("actions") or []
        if acts:
            L.append("")
            L.append("**Impact sur la base de connaissances :**")
            for a in acts:
                mark = "➕" if a["action"] == "added" else "✏️"
                L.append(f"- {mark} {a['action']} : « {a['title']} » — {a['entry'].get('summary', '')[:200]}"
                         + (f" *(raison : {a['reason'][:120]})*" if a.get("reason") else ""))
        a = d.get("assessment") or {}
        if a.get("issues") or a.get("positives"):
            L.append("")
            L.append(f"**Évaluation** : confiance globale {a.get('overall_confidence')}")
            for x in a.get("positives") or []:
                L.append(f"- ✅ {x}")
            for x in a.get("issues") or []:
                L.append(f"- ⚠️ {x}")
        L.append("")
    L.append("---")
    L.append("*Généré par `colab/analyze_discussions.py` v"
             f"{SCRIPT_VERSION} — vérifications web multi-moteurs (sans clé) + pilotage "
             f"{report['model']} · clé API jamais conservée ni transmise.*")
    return "\n".join(L)


def build_console_report(report: dict) -> str:
    s = report["stats"]
    lines = []
    bar = "═" * 64
    lines.append(bar)
    lines.append(" 📊 RAPPORT D'ANALYSE DES DISCUSSIONS")
    lines.append(f" {report['generated_at']} · modèle {report['model']} · {report['duration_s']} s")
    lines.append(bar)
    for i, d in enumerate(report["discussions"], 1):
        lines.append(f"▶ Discussion {i} : « {d['title']} » ({d['status']}, {len(d.get('claims') or [])} affirmation(s))")
        if d.get("summary"):
            lines.append(f"   {d['summary'][:150]}")
        for cl in d.get("claims") or []:
            v = cl.get("verdict") or {}
            lines.append(f"   {_VERDICT_MARK.get(v.get('verdict', '?'), '?')} {str(cl.get('claim', ''))[:90]}"
                         + (f" → {str(v.get('correction'))[:50]}" if v.get("correction") else ""))
        for a in d.get("actions") or []:
            mark = "➕" if a["action"] == "added" else "✏️"
            lines.append(f"   {mark} base : {a['action']} « {a['title']} »")
    lines.append("-" * 64)
    lines.append(f" TOTAL : {s['claims']} affirmation(s) — ✔ {s['correct']} · ✘ {s['incorrect']} "
                 f"· ? {s['unverifiable']} · · {s['unchecked']} · {s['searches']} recherche(s) web")
    lines.append(f" BASE  : {s['kb_before']} → {s['kb_after']} entrée(s) "
                 f"(+{s['added']} ajout(s), {s['updated']} mise(s) à jour)")
    push = report.get("push") or {}
    lines.append(f" SITE  : {push.get('mode', 'local')} {str(push.get('detail') or '')[:100]}")
    lines.append(bar)
    return "\n".join(lines)


def collect_stats(report_discussions: list[dict], kb_before: int, kb_after: int) -> dict:
    correct = incorrect = unverified = unchecked = searches = 0
    engines: set[str] = set()
    added = updated = 0
    for d in report_discussions:
        for cl in d.get("claims") or []:
            v = (cl.get("verdict") or {}).get("verdict")
            if v == "correcte":
                correct += 1
            elif v == "incorrecte":
                incorrect += 1
            elif v == "inverifiable":
                unverified += 1
            elif v == "non_verifiee":
                unchecked += 1
            ev = cl.get("evidence")
            if ev and ev.get("results") is not None:
                searches += 1
                if ev.get("engine"):
                    engines.add(str(ev["engine"]))
        for a in d.get("actions") or []:
            if a["action"] == "added":
                added += 1
            elif a["action"] == "updated":
                updated += 1
    return {
        "claims": correct + incorrect + unverified + unchecked,
        "correct": correct, "incorrect": incorrect, "unverifiable": unverified, "unchecked": unchecked,
        "searches": searches, "engines": sorted(engines),
        "kb_before": kb_before, "kb_after": kb_after, "added": added, "updated": updated,
    }


def save_and_download(name: str, content: str) -> str:
    """Écrit le fichier (dans /content sur Colab, /tmp ailleurs) et le propose
    en téléchargement automatique sur Colab. Retourne le chemin."""
    out_dir = "/content/aiis_analyzer" if IS_COLAB else (
        os.environ.get("ANALYZER_OUT") or os.path.join(tempfile.gettempdir(), "aiis_analyzer")
    )
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    if IS_COLAB:
        try:
            from google.colab import files as _files  # type: ignore

            _files.download(path)
        except Exception:  # noqa: BLE001
            pass
    return path


# --------------------------------------------------- export navigateur (JS) ---
#: Snippet à coller dans la console du navigateur (page du site, DevTools) :
#: liste les conversations du localStorage, demande la sélection, et copie
#: une ligne base64 UNIQUE (collable dans la cellule Colab sans ligne brisée).
EXPORT_SNIPPET_JS = r"""(function () {
  const KEY = "aiis.convos.v1";
  let convos = [];
  try { convos = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) {}
  if (!Array.isArray(convos) || !convos.length) {
    console.log("❌ Aucune conversation trouvée dans localStorage (" + KEY + ").");
    return;
  }
  const titleOf = (c) => c.title
    || (c.messages || []).map((m) => typeof m.content === "string" ? m.content
        : (Array.isArray(m.content) ? ((m.content.find((b) => b && b.type === "text") || {}).text || ""))
        : "").find(Boolean)
    || "Sans titre";
  console.log("📋 Conversations disponibles :\n" + convos
    .map((c, i) => (i + 1) + ". [" + (c.messages || []).length + " msg] "
      + new Date(c.updatedAt || c.createdAt || Date.now()).toLocaleString() + " — " + titleOf(c))
    .join("\n"));
  const answer = prompt("Numéros à exporter (espaces entre), ou « toutes » :", "toutes");
  if (answer === null) { console.log("Annulé."); return; }
  const a = answer.trim().toLowerCase();
  const sel = (a === "toutes" || a === "")
    ? convos.slice()
    : a.split(/[\s,;]+/).filter(Boolean).map((n) => convos[parseInt(n, 10) - 1]).filter(Boolean);
  if (!sel.length) { console.log("❌ Aucune conversation sélectionnée."); return; }
  const payload = { app: "aiis", export_type: "discussions", exported_at: new Date().toISOString(), conversations: sel };
  const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
  const done = (ok) => console.log((ok ? "✅ " : "⚠️ ") + sel.length + " conversation(s) : "
    + (ok ? "ligne base64 copiée dans le presse-papier → colle-la dans Colab (Entrée)."
          : "copie refusée — la ligne est affichée ci-dessous (sélectionne-la et copie-la)."));
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(b64).then(() => done(true)).catch(() => { console.log(b64); done(false); });
  } else { console.log(b64); done(false); }
})();"""


def print_export_instructions() -> None:
    print("─" * 64)
    print(" ÉTAPE 1 — exporter TES discussions depuis le navigateur")
    print("─" * 64)
    print(" Option A (bouton) : sur le site, bouton 📤 dans la barre du haut →")
    print("   « Export vers l'analyseur Colab » → sélection → « Copier la ligne base64 ».")
    print(" Option B (console) : sur le site, ouvre les DevTools (F12) → Console,")
    print("   colle le snippet ci-dessous, Entrée, choisis les numéros → copié.")
    print("")
    print("```js")
    print(EXPORT_SNIPPET_JS)
    print("```")
    print("")
    if IS_COLAB:
        try:
            path = save_and_download("aiis_export_discussions.js", EXPORT_SNIPPET_JS)
            print(f" (le snippet est aussi téléchargé : {path})")
        except Exception:  # noqa: BLE001
            pass


def prompt_discussions(prompt=input) -> dict | None:
    print_export_instructions()
    try:
        raw = prompt("ÉTAPE 2 — colle ici la ligne base64 exportée (ou 'f' pour téléverser un fichier) : ")
    except (EOFError, KeyboardInterrupt):
        print("\nInterrompu.")
        return None
    raw = (raw or "").strip()
    if raw.lower() in ("f", "file", "fichier", "upload"):
        if not IS_COLAB:
            print("Téléversement indisponible hors Colab — colle la ligne base64 ou le JSON.")
        else:
            try:
                from google.colab import files as _files  # type: ignore

                uploaded = _files.upload()
                if uploaded:
                    name = next(iter(uploaded))
                    data = uploaded[name].read()
                    payload = parse_discussions_payload(data)
                    if payload:
                        return payload
                print("Aucun fichier reçu.")
            except Exception as exc:  # noqa: BLE001
                print(f"Téléversement impossible : {exc}")
    payload = parse_discussions_payload(raw)
    if payload is None and raw:
        print("⚠️ je n'ai pas réussi à décoder cela (attendu : la ligne base64, ou le JSON).")
    return payload


def prompt_mistral_key(prompt=input, secret_prompt=None) -> str | None:
    print("─" * 64)
    print(" ÉTAPE 3 — clé API Mistral (La Plateforme — mistral.ai)")
    print("─" * 64)
    print(" Saisie masquée, conservée EN RAM uniquement : jamais affichée, jamais")
    print(" sauvegardée, jamais poussée au site (expurgée de tous les rapports).")
    if secret_prompt is not None:
        getter = secret_prompt
    else:
        try:
            from getpass import getpass as _getpass

            getter = _getpass
        except Exception:  # noqa: BLE001
            getter = prompt
    try:
        key = getter("Clé API Mistral : ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not key:
        print("Aucune clé fournie — l'analyseur a besoin d'une clé Mistral (seul fournisseur).")
        return None
    return key


# ------------------------------------------------------------------- main ----
def banner() -> None:
    print("═" * 64)
    print(" 📡 ANALYSEUR AUTOMATIQUE DE DISCUSSIONS — AI-improves-itself v" + str(SCRIPT_VERSION))
    print(" Pilotage : " + MISTRAL_MODEL + " · recherche web multi-moteurs (sans clé) · " + http_engine())
    print(" Site : " + (MAIN_SITE_URL or "(mode local pur)") + " · push : " + ("oui" if PUSH_TO_SITE else "non"))
    print("═" * 64)
    print("")


def main(prompt=input, secret_prompt=None) -> int:
    t0 = time.time()
    banner()

    # 1. discussions (localStorage → export base64/JSON/fichier)
    payload = prompt_discussions(prompt=prompt)
    if not payload:
        print("Aucune discussion analysable — sortie.")
        return 1
    convos = payload["conversations"]
    if len(convos) > MAX_CONVERSATIONS:
        print(f"⚠️ {len(convos)} discussions chargées — analyse des {MAX_CONVERSATIONS} premières (MAX_CONVERSATIONS).")
        convos = convos[:MAX_CONVERSATIONS]
    print(f"✅ {len(convos)} discussion(s) chargée(s) :")
    for c in convos:
        print(f"   • {c['title']} ({len(c['messages'])} messages)")
    print("")

    # 2. clé Mistral + ping
    key = prompt_mistral_key(prompt=prompt, secret_prompt=secret_prompt)
    if not key:
        return 2
    cfg = {"api_key": key, "model": MISTRAL_MODEL, "base_url": MISTRAL_API_BASE, "secrets": [key]}
    print("🧠 test de la clé (1 micro-appel)…")
    ok, msg = mistral_ping(cfg)
    if not ok:
        print(f"❌ {msg}")
        return 2
    print(f"✅ {msg}")
    print("")

    # 3. base de connaissances existante
    kb, kb_origin = fetch_knowledge_base(MAIN_SITE_URL, prompt=prompt)
    kb_before = len(kb)
    print(f"🗃  base de connaissances : {kb_before} entrée(s) (provenance : {kb_origin})")
    print("")

    # 4. analyse discussion par discussion (la base travaille sur une copie
    #    croissante : la conversation 2 voit les corrections de la conversation 1)
    working_kb = list(kb)
    report_discussions: list[dict] = []
    all_actions: list[dict] = []
    for i, convo in enumerate(convos, 1):
        print(f"┌─── Discussion {i}/{len(convos)} : « {convo['title']} » " + "─" * max(0, 40 - len(convo["title"])))
        analysis = analyze_conversation(cfg, convo, working_kb)
        merged, actions = merge_patch(working_kb, analysis.get("plan") or [])
        working_kb = merged
        for a in actions:
            a["conversation"] = convo["title"]
        all_actions.extend(actions)
        print(f"└─── → {len(actions)} action(s) sur la base "
              f"({sum(1 for a in actions if a['action'] == 'added')} ajout(s), "
              f"{sum(1 for a in actions if a['action'] == 'updated')} mise(s) à jour)")
        print("")
        report_discussions.append(
            {
                "title": convo["title"],
                "messages": len(convo["messages"]),
                "status": analysis.get("status", "error"),
                "summary": analysis.get("summary", ""),
                "topics": analysis.get("topics", []),
                "claims": analysis.get("claims", []),
                "actions": actions,
                "assessment": analysis.get("assessment", {}),
                "errors": analysis.get("errors", []),
                "plan_dropped_low_confidence": analysis.get("plan_dropped_low_confidence", 0),
            }
        )

    # 5. push au site
    secrets = (key,)
    stats = collect_stats(report_discussions, kb_before, len(working_kb))
    report_md = build_markdown(
        {
            "generated_at": _now_iso(), "model": MISTRAL_MODEL, "duration_s": int(time.time() - t0),
            "discussions": report_discussions, "stats": stats, "push": None,
        }
    )
    print("📤 push de la base de connaissances vers le site…")
    push = push_to_site(all_actions, report_md, MAIN_SITE_URL, secrets=secrets)
    print(f"   {push.get('mode')} {str(push.get('detail') or '')[:160]}")
    if push.get("mode") == "direct":
        print(f"   → {push.get('counts', {}).get('added', 0)} ajout(s), "
              f"{push.get('counts', {}).get('updated', 0)} mise(s) à jour, "
              f"{push.get('counts', {}).get('skipped', 0)} doublon(s) côté serveur.")

    # 6. rendu structuré (console + 3 fichiers)
    report = {
        "generated_at": _now_iso(), "model": MISTRAL_MODEL, "duration_s": int(time.time() - t0),
        "script_version": SCRIPT_VERSION, "site": MAIN_SITE_URL or None,
        "knowledge_base_origin": kb_origin, "discussions": report_discussions,
        "stats": stats, "push": push,
    }
    report_md = build_markdown(report)
    safe_md = redact(report_md, secrets)
    print()
    print(build_console_report(report))
    print()
    ts = time.strftime("%Y%m%d-%H%M%S")
    files = {
        f"rapport_analyse_discussions_{ts}.md": safe_md,
        f"analyse_discussions_{ts}.json": redact(json.dumps(report, ensure_ascii=False, indent=2), secrets),
        "knowledge_base_maj.json": redact(json.dumps(working_kb, ensure_ascii=False, indent=2), secrets),
    }
    for name, content in files.items():
        try:
            path = save_and_download(name, content)
            print(f"💾 {name} → {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ écriture impossible pour {name} : {exc}")
    print()
    print("🏁 Terminé. Sur le site : la base est visible sur /data.html ;"
          " le rapport complet est dans le .md ci-dessus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
