"""Script Colab v2 — recherche web + synchro robuste + résumé IA optionnel.

Mécanique (v2) :
1. L'IA (ou un humain) ajoute des tâches via l'API du site :
   kind = search (requête) | fetch (URL) | deep (recherche + lecture auto
   des meilleures pages) | note (texte brut).
2. Vous ouvrez le notebook dans Google Colab (ou lancez en local) :
   - le serveur est réveillé (le plan gratuit Render s'endort après 15 min),
   - les tâches sont rapatriées depuis l'API (GET /api/research/tasks) : le
     serveur, avec sa base de données, est la SEULE source de vérité. Elles
     sont fusionnées avec le cache local (tasks_cache.json) ; le statut le
     plus avancé gagne, donc une tâche `done` ne ressuscite jamais (bug v1 corrigé),
   - chaque tâche pending est exécutée (multi-moteurs : DuckDuckGo HTML →
     DuckDuckGo lite → Wikipédia ; fetch avec titre + robots.txt),
   - OPTIONNEL : avec une clé API fournie à la main (jamais sauvegardée ni
     poussée au site), chaque résultat est résumé localement (1 appel/tâche).
3. Statuts (PATCH) + résultats (POST /api/research/results) sont poussés au
   site, avec réessais. Les résultats non poussés sont REPOUSSÉS au run
   suivant (plus aucune perte comme en v1) et dédupliqués côté serveur.
4. Le site étudie chaque résultat (structuration + vérification, 2 appels
   Mistral) ; le script attend le bilan et l'affiche.

Exécution en local (hors Colab) :
    python colab/main.py --help
    python colab/main.py --preflight-only          # diagnostic sans exécuter
    RESEARCH_TASKS_PATH=/tmp/t.json COLAB_RESULTS_PATH=/tmp/r.json MAIN_SITE_URL= \\
        python colab/main.py --max-tasks 2         # 100 % local, sans réseau serveur

Variables d'environnement (le notebook les positionne pour vous) :
    MAIN_SITE_URL       URL du site (défaut : https://aiis-core.onrender.com).
                        Vide = mode local pur (ni pull ni push).
    COLAB_BRANCH        branche GitHub du seed de démo (cache initial hors-ligne, défaut main).
    RESEARCH_TASKS_PATH fichier de cache partagé avec le serveur (avancé, hors-ligne uniquement).
    COLAB_RESULTS_PATH  fichier des résultats (défaut : colab/results.json).
    MAX_TASKS / FETCH_TOP / SUMMARIZE / COLAB_LLM_PROVIDER / COLAB_LLM_MODEL /
    COLAB_LLM_API_KEY / COLAB_LLM_BASE_URL : voir run_all() et llm_config_from_env().

Dépendances : stdlib uniquement. Si `requests` / `beautifulsoup4` sont
disponibles (préinstallés sur Colab), ils sont utilisés automatiquement
(meilleure gestion HTTP/encodage et extraction HTML plus propre).
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

#: Version du script — le notebook refuse toute version < 2 (l'ancienne
#: synchro v1 ré-exécutait les tâches done à chaque run).
COLAB_SCRIPT_VERSION = 2

REPO = "Snowoo-2z/AI-improves-itself"
DEFAULT_BRANCH = "main"

HERE = os.path.dirname(os.path.abspath(__file__))


def _resolve_json_path(env_value: str, default_name: str) -> str:
    """Chemin optionnel : absolu tel quel, sinon relatif à la racine du repo."""
    v = (env_value or "").strip()
    if v:
        if os.path.isabs(v):
            return v if v.endswith(".json") else os.path.join(v, default_name)
        base = os.path.join(os.path.dirname(HERE), v)
        return base if v.endswith(".json") else os.path.join(base, default_name)
    return os.path.join(HERE, default_name)


# Cache local des tâches. Principe : les tâches vivent sur le SERVEUR, avec la
# base de données (le serveur est la seule source de vérité) ; ce fichier
# (tasks_cache.json) ne sert que de cache — fusionné à chaque run, initialisé
# depuis le seed de démo du repo. RESEARCH_TASKS_PATH (optionnel) permet de
# partager un autre fichier avec le serveur en exécution locale hors-ligne
# (même valeur des deux côtés).
TASKS_PATH = _resolve_json_path(os.environ.get("RESEARCH_TASKS_PATH", ""), "tasks_cache.json")
#: COLAB_RESULTS_PATH (optionnel, tests/CI) : déplace results.json ailleurs.
RESULTS_PATH = _resolve_json_path(os.environ.get("COLAB_RESULTS_PATH", ""), "results.json")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

#: URL publique du site principal (fallback). Surchargeable par la variable
#: d'environnement MAIN_SITE_URL (définie par le notebook) ou par un fichier
#: local `colab/main_site_url.txt` (gitignoré). Vide = mode local pur.
DEFAULT_MAIN_SITE_URL = "https://aiis-core.onrender.com"
_LOCAL_URL_FILE = os.path.join(HERE, "main_site_url.txt")


def _detect_main_site_url() -> str:
    """Résout l'URL du site : environnement → fichier local → défaut versionné."""
    env_url = os.environ.get("MAIN_SITE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    if os.path.exists(_LOCAL_URL_FILE):
        try:
            with open(_LOCAL_URL_FILE, "r", encoding="utf-8") as fh:
                local = fh.read().strip()
        except OSError:
            local = ""
        if local:
            return local.rstrip("/")
    return DEFAULT_MAIN_SITE_URL


MAIN_SITE_URL = _detect_main_site_url()

#: Ordre d'avancement des statuts — utilisé par merge_tasks() : le statut le
#: plus avancé gagne TOUJOURS (monotone). Une tâche `done`/`failed` ne peut
#: donc jamais repasser `pending`/`processing`, ni par le seed GitHub ni par
#: un pull distant en retard (le bug v1 qui ré-exécutait tout à chaque run).
_STATUS_RANK = {"pending": 0, "processing": 1, "done": 2, "failed": 2}

#: Tâches enrichies : nombre de pages lues pour kind=deep.
DEEP_FETCH_N = 3
#: Texte conservé par page lue lors d'un enrichissement (search/deep).
ENRICH_TEXT_CLIP = 3000
#: Texte envoyé au LLM pour un résumé local (1 appel/tâche max).
SUMMARY_INPUT_CLIP = 4000


# ------------------------------------------------------------- optionnels ----
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
    """Moteur HTTP/HTML réellement utilisé (affiché dans les rapports)."""
    return ("requests" if _HAS_REQUESTS else "urllib") + "+" + ("bs4" if _HAS_BS4 else "regex")


HTTP_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}


# ------------------------------------------------------------ utilitaires ----
def _read(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return default


def _write(path: str, data) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------------- HTTP ----
def _http_get(url: str, timeout: int = 30, retries: int = 1) -> tuple[int, str, str]:
    """GET avec réessais. Retourne (status, texte, url_finale). Lève en échec."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if _HAS_REQUESTS:
                r = _requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code} sur {url[:90]}")
                return r.status_code, r.text or "", str(r.url)
            req = urllib.request.Request(url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                try:
                    text = raw.decode(charset, errors="replace")
                except LookupError:
                    text = raw.decode("utf-8", errors="replace")
                return resp.status, text, resp.geturl()
        except Exception as exc:  # noqa: BLE001 — réessai puis levée explicite
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
    """Appel JSON (API du site, LLM). Retourne (status, dict|None), sans lever
    sur les erreurs HTTP (le code appelant décide : 401/404/429 = messages)."""
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


# ------------------------------------------------------ extraction HTML ------
_STRIP_TAGS_RE = re.compile(r"(?s)<[^>]+>")
_WS_RE = re.compile(r"[ \t\xa0]+")
_BLANK_LINES_RE = re.compile(r"\n\s*\n+")


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


def extract_meta_description(html_text: str) -> str:
    if _HAS_BS4:
        try:
            soup = _BS(html_text, "html.parser")
            for attrs in ({"name": "description"}, {"property": "og:description"}):
                tag = soup.find("meta", attrs=attrs)
                if tag and tag.get("content"):
                    return str(tag["content"]).strip()[:500]
            return ""
        except Exception:  # noqa: BLE001
            pass
    m = re.search(
        r'(?is)<meta[^>]+(?:name="description"|property="og:description")[^>]+content="([^"]+)"',
        html_text or "",
    )
    if not m:  # attributs dans l'autre ordre
        m = re.search(
            r'(?is)<meta[^>]+content="([^"]+)"[^>]+(?:name="description"|property="og:description")',
            html_text or "",
        )
    return _html.unescape(m.group(1)).strip()[:500] if m else ""


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
        except Exception:  # noqa: BLE001 — repli regex ci-dessous
            pass
    text = re.sub(
        r"(?is)<(script|style|nav|footer|header|aside|form|noscript)[^>]*>.*?</\1>",
        " ",
        html_text or "",
    )
    # Préférer le contenu de <article>/<main> quand il existe (regex simple).
    m = re.search(r"(?is)<(article|main)[^>]*>(.*?)</\1>", text)
    if m and len(m.group(2)) > 500:
        text = m.group(2)
    text = _STRIP_TAGS_RE.sub(" ", text)
    return _normalize_ws(_html.unescape(text))[:max_chars].strip()


def _normalize_ws(text: str) -> str:
    text = _WS_RE.sub(" ", text or "")
    text = _BLANK_LINES_RE.sub("\n", text)
    return text.strip()


# --------------------------------------------------------------- recherche ---
def _unwrap_ddg(link: str) -> str:
    """Les liens DDG sont des redirections //duckduckgo.com/l/?uddg=<url>."""
    try:
        if "uddg=" in link:
            return urllib.parse.unquote(re.search(r"uddg=([^&]+)", link).group(1))  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        pass
    return link


def parse_ddg_html(html_text: str, max_results: int = 5) -> list[dict]:
    """Parseur pur (testable sans réseau) du endpoint html.duckduckgo.com/html/."""
    out: list[dict] = []
    pattern = re.compile(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    matches = list(pattern.finditer(html_text or ""))
    for i, m in enumerate(matches):
        link = _unwrap_ddg(_html.unescape(m.group(1)).strip())
        title = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", m.group(2))))[:300]
        end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 3000
        chunk = (html_text or "")[m.end() : end]
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', chunk, re.S)
        snippet = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", snip.group(1))))[:500] if snip else ""
        if link.startswith("//"):
            link = "https:" + link
        out.append({"title": title or "(sans titre)", "url": link, "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


def parse_ddg_lite(html_text: str, max_results: int = 5) -> list[dict]:
    """Parseur pur (testable sans réseau) du endpoint lite.duckduckgo.com/lite/."""
    out: list[dict] = []
    pattern = re.compile(r'<a\s+rel="nofollow"\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
    matches = list(pattern.finditer(html_text or ""))
    for i, m in enumerate(matches):
        link = _unwrap_ddg(_html.unescape(m.group(1)).strip())
        title = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", m.group(2))))[:300]
        end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 1500
        chunk = (html_text or "")[m.end() : end]
        snip = re.search(r"result-snippet['\"]?\s*>(.*?)</td>", chunk, re.S | re.I)
        snippet = _normalize_ws(_html.unescape(_STRIP_TAGS_RE.sub(" ", snip.group(1))))[:500] if snip else ""
        if link.startswith("//"):
            link = "https:" + link
        if "duckduckgo.com/" in link and "uddg=" not in m.group(1):
            continue  # lien interne (pagination, aide…) — pas un résultat
        out.append({"title": title or "(sans titre)", "url": link, "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


def wikipedia_search(query: str, lang: str = "fr", max_results: int = 5, timeout: int = 20) -> list[dict]:
    """Recherche via l'API publique Wikipédia (sans clé, fiable, avec extraits)."""
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
    """Recherche multi-moteurs avec fallbacks : DDG HTML → DDG lite → Wikipédia
    FR → Wikipédia EN. Retourne {results, engine, query, error?} — `engine`
    dit quel moteur a servi (visible dans les rapports et les tests)."""
    q = (query or "").strip()
    errors: dict[str, str] = {}
    # 1) DuckDuckGo HTML (le plus complet : titres + snippets + vraies URLs)
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
    # 2) DuckDuckGo lite (page ultra-simple, rarement bloquée)
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
    # 3-4) Wikipédia FR puis EN (moins général, mais quasi injoignable en panne
    # et parfait pour les sujets encyclopédiques — mieux que « aucun résultat »)
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


# ------------------------------------------------------------------ fetch ----
_ROBOTS_CACHE: dict[str, urllib.robotparser.RobotFileParser] = {}


def can_fetch(url: str, _get=None) -> bool:
    """Honore le robots.txt de la cible (le footer /colab le promet depuis la
    v1 — ici c'est réel). Best-effort : robots injoignable → on tente quand même.
    `_get` injectable pour les tests (faux robots.txt, sans réseau)."""
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
            except Exception:  # noqa: BLE001 — robots illisible : on tente
                return True
            _ROBOTS_CACHE[host] = rp
        return _ROBOTS_CACHE[host].can_fetch("*", url)
    except Exception:  # noqa: BLE001
        return True


def fetch_url(url: str, max_chars: int = 12000, timeout: int = 30) -> dict:
    """Récupère une page : titre + description + texte (article/main priorisés)."""
    if not can_fetch(url):
        return {
            "url": url,
            "http_status": None,
            "title": "",
            "description": "",
            "text": "",
            "robots_blocked": True,
            "error": "robots.txt : fetch refusé par le site cible",
        }
    status, text, final = _http_get(url, timeout=timeout, retries=1)
    title = extract_title(text)
    desc = extract_meta_description(text)
    body = html_to_text(text, max_chars=max_chars)
    out = {
        "url": final or url,
        "requested_url": url,
        "http_status": status,
        "title": title,
        "description": desc,
        "text": body,
        "engine": http_engine(),
    }
    if not body.strip():
        out["error"] = "page vide après extraction (JS lourd ? contenu non-HTML ?)"
    return out


# ---------------------------------------------------------------- runners ----
def _enrich_with_pages(results: list[dict], fetch_top: int, text_clip: int = ENRICH_TEXT_CLIP) -> list[dict]:
    """Lit le texte des N premiers résultats (poliment : 1 s entre deux)."""
    for it in (results or [])[: max(0, fetch_top)]:
        u = (it.get("url") or "").strip()
        if not u.startswith(("http://", "https://")):
            it["fetch_error"] = "URL non fetchable"
            continue
        try:
            page = fetch_url(u, max_chars=text_clip + 1500)
            if page.get("text"):
                it["text"] = page["text"][:text_clip]
            if page.get("title") and not it.get("title"):
                it["title"] = page["title"]
            if page.get("error"):
                it["fetch_error"] = str(page["error"])[:200]
        except Exception as exc:  # noqa: BLE001 — un fetch KO n'annule pas la recherche
            it["fetch_error"] = str(exc)[:200]
        time.sleep(1.0)
    return results


def run_search(task: dict, fetch_top: int = 1) -> dict:
    found = web_search(task["target"], max_results=5)
    results = found.get("results", [])
    if fetch_top and results:
        _enrich_with_pages(results, fetch_top)
    return {
        "kind": "search",
        "query": task["target"],
        "engine": found.get("engine", "none"),
        "results": results,
        "search_error": found.get("error"),
        "error": None if results else (found.get("error") or "aucun résultat"),
    }


def run_fetch(task: dict) -> dict:
    page = fetch_url(task["target"])
    return {"kind": "fetch", **page}


def run_note(task: dict) -> dict:
    return {"kind": "note", "content": task["target"]}


def run_deep(task: dict, fetch_n: int = DEEP_FETCH_N) -> dict:
    """Recherche approfondie : titres + snippets + lecture des N meilleures pages."""
    found = web_search(task["target"], max_results=5)
    results = found.get("results", [])
    if results:
        _enrich_with_pages(results, fetch_n, text_clip=2500)
    fetched = sum(1 for it in results if it.get("text"))
    return {
        "kind": "deep",
        "query": task["target"],
        "engine": found.get("engine", "none"),
        "results": results,
        "fetched": fetched,
        "error": None if results else (found.get("error") or "aucun résultat"),
    }


def _describe_data(kind: str, data: dict) -> str:
    if kind == "search":
        return f"{len(data.get('results', []))} résultat(s) via {data.get('engine', '?')}"
    if kind == "deep":
        return f"{data.get('fetched', 0)}/{len(data.get('results', []))} page(s) lue(s) via {data.get('engine', '?')}"
    if kind == "fetch":
        title = (data.get("title") or "").strip()
        return f"{len(data.get('text', ''))} car." + (f" « {title[:60]} »" if title else "")
    return f"{len(str(data.get('content', '')))} car."


# ------------------------------------------------- résumé IA optionnel --------
#: Mêmes endpoints OpenAI-compatibles que le cœur (core/ai/limits.py), avec le
#: modèle le plus économe de chaque provider par défaut (1 appel/tâche).
LLM_PRESETS = {
    "mistral": {"base_url": "https://api.mistral.ai/v1", "model": "ministral-8b-latest", "headers": {}},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash-lite",
        "headers": {},
    },
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-20b", "headers": {}},
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/free",
        "headers": {
            "HTTP-Referer": "https://github.com/Snowoo-2z/AI-improves-itself",
            "X-Title": "AI-improves-itself (Colab)",
        },
    },
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1", "model": "openai/gpt-oss-20b", "headers": {}},
}


def llm_config_from_env() -> dict | None:
    """Config LLM depuis l'environnement (le notebook met la clé via getpass).
    Retourne None si pas de clé. La clé ne vit qu'en RAM : jamais écrite sur
    disque, jamais poussée au site (les payloads sont expurgés par redact())."""
    key = (os.environ.get("COLAB_LLM_API_KEY") or "").strip()
    if not key:
        return None
    provider = (os.environ.get("COLAB_LLM_PROVIDER") or "mistral").strip().lower()
    preset = LLM_PRESETS.get(provider)
    if not preset:
        raise ValueError(f"provider LLM inconnu : {provider} (choix : {', '.join(sorted(LLM_PRESETS))})")
    model = (os.environ.get("COLAB_LLM_MODEL") or "").strip() or preset["model"]
    base = (os.environ.get("COLAB_LLM_BASE_URL") or "").strip() or preset["base_url"]
    return {"provider": provider, "api_key": key, "model": model, "base_url": base, "headers": preset["headers"]}


def llm_complete(cfg: dict, system: str, user: str, timeout: int = 60, max_tokens: int = 600) -> str:
    """Un appel chat OpenAI-compatible (stdlib : urllib, pas de dépendance)."""
    # gpt-oss exige max_completion_tokens (cf. core/ai/limits.py) — max_tokens vaut 400.
    tok_key = "max_completion_tokens" if cfg["model"].startswith("openai/gpt-oss") else "max_tokens"
    body = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.3,
        tok_key: max_tokens,
    }
    status, data = _http_json(
        "POST",
        cfg["base_url"].rstrip("/") + "/chat/completions",
        body,
        headers={"Authorization": f"Bearer {cfg['api_key']}", **cfg.get("headers", {})},
        timeout=timeout,
    )
    name = cfg["provider"]
    if status == 401:
        raise RuntimeError(f"{name} : clé API refusée (401) — vérifie COLAB_LLM_API_KEY.")
    if status == 429:
        raise RuntimeError(f"{name} : quota atteint (429) — résumés en pause, le brut reste disponible.")
    if status == 404:
        raise RuntimeError(f"{name} : modèle '{cfg['model']}' introuvable (404) — vide LLM_MODEL pour le défaut.")
    if status >= 400 or not isinstance(data, dict):
        raise RuntimeError(f"{name} : HTTP {status} — {json.dumps(data)[:200]}")
    if data.get("error"):  # OpenRouter renvoie l'échec upstream dans un 200
        raise RuntimeError(f"{name} : {str(data['error'])[:200]}")
    try:
        content = (data["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"{name} : réponse inattendue — {json.dumps(data)[:200]}")
    if not content:
        raise RuntimeError(f"{name} : réponse vide du modèle {cfg['model']}.")
    return content


def llm_ping(cfg: dict, timeout: int = 30) -> tuple[bool, str]:
    """Teste clé + modèle (1 micro-appel). Retourne (ok, message)."""
    try:
        llm_complete(cfg, "Réponds uniquement : pong", "ping", timeout=timeout, max_tokens=5)
        return True, f"{cfg['provider']}/{cfg['model']} OK"
    except Exception as exc:  # noqa: BLE001
        return False, redact(str(exc), [cfg.get("api_key", "")])[:220]


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


_SUMMARY_SYSTEM = (
    "Tu es l'assistant de résumé du projet AI-improves-itself. Résume le contenu fourni.\n"
    "Réponds UNIQUEMENT en JSON valide (pas de markdown, pas de prose) :\n"
    '{"title": "titre court", "summary": "2-3 phrases factuelles en français", '
    '"key_points": ["puce 1", "puce 2"], "confidence": 0.0}\n'
    "- confidence : 0 à 1, ta certitude que le résumé est fidèle au contenu.\n"
    "- N'invente rien : si le contenu est vide ou incohérent, summary l'explique et confidence vaut 0."
)


def summarize_entry(kind: str, data: dict, cfg: dict, timeout: int = 60) -> dict:
    """Résume UN résultat (1 appel LLM). Best-effort : échec → dict avec `error`."""
    if kind == "search":
        lines = []
        for it in (data.get("results") or [])[:5]:
            if not isinstance(it, dict):
                continue
            line = f"- {it.get('title', '?')} ({it.get('url', '')})"
            if it.get("snippet"):
                line += f"\n  extrait : {it['snippet']}"
            if it.get("text"):
                line += f"\n  contenu : {str(it['text'])[:800]}"
            lines.append(line)
        material = f"Requête : {data.get('query', '')}\n" + "\n".join(lines)
        source = f"recherche ({data.get('engine', '?')})"
    elif kind == "deep":
        lines = []
        for it in (data.get("results") or [])[:5]:
            if not isinstance(it, dict):
                continue
            line = f"- {it.get('title', '?')} ({it.get('url', '')})"
            if it.get("snippet"):
                line += f"\n  extrait : {it['snippet']}"
            if it.get("text"):
                line += f"\n  contenu : {str(it['text'])[:800]}"
            lines.append(line)
        material = f"Sujet : {data.get('query', '')}\n" + "\n".join(lines)
        source = f"recherche approfondie ({data.get('engine', '?')})"
    elif kind == "fetch":
        material = f"URL : {data.get('url', '')}\nTitre : {data.get('title', '')}\n\n{data.get('text', '')}"
        source = str(data.get("url", ""))
    else:
        material = str(data.get("content", ""))
        source = "note"
    material = material.strip()[:SUMMARY_INPUT_CLIP]
    if not material:
        return {"title": "", "summary": "", "key_points": [], "confidence": 0.0,
                "error": "contenu vide, rien à résumer",
                "provider": cfg["provider"], "model": cfg["model"]}
    try:
        raw = llm_complete(cfg, _SUMMARY_SYSTEM, f"Source : {source}\n\nContenu :\n{material}", timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {"title": "", "summary": "", "key_points": [], "confidence": 0.0,
                "error": redact(str(exc), [cfg.get("api_key", "")])[:220],
                "provider": cfg["provider"], "model": cfg["model"]}
    js = parse_llm_json(raw)
    if not isinstance(js, dict):
        return {"title": "", "summary": "", "key_points": [], "confidence": 0.0,
                "error": "réponse LLM non structurée", "raw_excerpt": raw[:300],
                "provider": cfg["provider"], "model": cfg["model"]}
    try:
        confidence = float(js.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "title": str(js.get("title") or "")[:200],
        "summary": str(js.get("summary") or "")[:1500],
        "key_points": [str(p)[:300] for p in (js.get("key_points") or [])[:8] if str(p).strip()],
        "confidence": round(min(1.0, max(0.0, confidence)), 2),
        "provider": cfg["provider"],
        "model": cfg["model"],
    }


def redact(text: str, secrets) -> str:
    """Expurge les secrets d'un texte (logs, erreurs, payloads poussés)."""
    out = str(text or "")
    for s in secrets or []:
        if s and len(str(s)) > 6:
            out = out.replace(str(s), "***CLE-MASQUEE***")
    return out


# ------------------------------------------------------------ site (API) ----
def _site(path: str) -> str:
    return MAIN_SITE_URL.rstrip("/") + path


def wake_server(tries: int = 6, timeout: int = 20, quiet: bool = False) -> tuple[bool, str]:
    """Réveille le serveur (le plan gratuit Render dort après 15 min : ~1 min
    au réveil, que les 20 s de timeout v1 ne couvraient jamais)."""
    if not MAIN_SITE_URL:
        return False, "pas d'URL de site (mode local pur)"
    last: Exception | None = None
    for i in range(tries):
        try:
            status, _text, _final = _http_get(_site("/health"), timeout=timeout, retries=0)
            if status == 200:
                return True, f"serveur joignable ({MAIN_SITE_URL})"
            last = RuntimeError(f"HTTP {status} sur /health")
        except Exception as exc:  # noqa: BLE001
            last = exc
        if not quiet:
            print(f"  ⏳ réveil du serveur… essai {i + 1}/{tries} (plan gratuit : ~1 min)")
        if i < tries - 1:
            time.sleep(10)
    return False, f"serveur injoignable après {tries} essais : {str(last)[:160]}"


def get_server_status(timeout: int = 30) -> dict | None:
    """GET /api/status : backend, compteurs, provider (diagnostic de synchro)."""
    if not MAIN_SITE_URL:
        return None
    try:
        status, data = _http_json("GET", _site("/api/status"), timeout=timeout)
        return data if status == 200 and isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def pull_tasks(timeout: int = 30) -> list[dict]:
    """Rapatrie les tâches depuis l'API (source de vérité à distance)."""
    if not MAIN_SITE_URL:
        return []
    try:
        status, data = _http_json("GET", _site("/api/research/tasks"), timeout=timeout)
        if status == 200 and isinstance(data, dict):
            items = data.get("tasks", [])
            return items if isinstance(items, list) else []
        print(f"! tâches API inaccessibles (HTTP {status}) — fichier local seul.")
    except Exception as exc:  # noqa: BLE001
        print(f"! tâches API inaccessibles ({str(exc)[:160]}) — fichier local seul.")
    return []


def pull_results(task_id: str | None = None, timeout: int = 30) -> list[dict] | None:
    """Résultats distants (None = serveur injoignable). `task_id` filtre côté
    serveur (nouveau) ; un vieux serveur ignore le filtre et renvoie tout —
    les deux cas restent corrects pour nos vérifications d'appartenance."""
    if not MAIN_SITE_URL:
        return None
    try:
        url = _site("/api/research/results")
        if task_id:
            url += f"?task_id={urllib.parse.quote(str(task_id))}"
        status, data = _http_json("GET", url, timeout=timeout)
        if status == 200 and isinstance(data, dict):
            items = data.get("results", [])
            return items if isinstance(items, list) else []
        return None
    except Exception:  # noqa: BLE001
        return None


def remote_result_task_ids() -> set[str] | None:
    """IDs de tâches déjà pourvues côté serveur (None = injoignable)."""
    items = pull_results()
    if items is None:
        return None
    return {str(r.get("task_id")) for r in items if r.get("task_id")}


def merge_tasks(local_tasks: list[dict], remote_tasks: list[dict]) -> list[dict]:
    """Fusionne tâches locales + distantes (par id). Règles :
    - union par id (les locales sans id sont conservées telles quelles),
    - à égalité ou si le distant est plus avancé : le DISTANT gagne
      (statut, erreur, dates + champs descriptifs),
    - si le local est plus avancé (ex. `done` local contre `pending` distant
      parce qu'un push de statut a échoué) : le LOCAL gagne, et sera repoussé.
    Le statut est donc monotone : `done`/`failed` ne ressuscitent jamais."""
    merged: dict[str, dict] = {}
    order: list[str] = []
    extras: list[dict] = []
    for t in local_tasks or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if not tid:
            extras.append(t)
            continue
        merged[str(tid)] = dict(t)
        order.append(str(tid))
    for r in remote_tasks or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        rid = str(r["id"])
        if rid not in merged:
            merged[rid] = dict(r)
            order.append(rid)
            continue
        local = merged[rid]
        rank_local = _STATUS_RANK.get(str(local.get("status")), 0)
        rank_remote = _STATUS_RANK.get(str(r.get("status")), 0)
        if rank_remote >= rank_local:
            for k in ("status", "error", "updated_at", "by", "kind", "target", "reason", "created_at"):
                if k in r:
                    local[k] = r[k]
        else:  # le local est plus avancé : il gagne, le distant complète
            for k in ("kind", "target", "reason", "created_at", "by"):
                if k in r and not local.get(k):
                    local[k] = r[k]
    return [merged[i] for i in order] + extras


def select_unpushed(results: list[dict]) -> list[dict]:
    """Résultats à (re)pousser : ceux marqués pushed=false. Les entrées v1
    (sans champ `pushed`) sont considérées comme déjà poussées — pas de
    doublons massifs au premier run v2 sur une session existante."""
    return [e for e in (results or []) if isinstance(e, dict) and e.get("pushed") is False]


def push_task_status(task_id: str | None, status: str, retries: int = 3) -> bool:
    """Repousse le statut d'une tâche (PATCH, avec réessais)."""
    if not MAIN_SITE_URL or not task_id:
        return False
    last: Exception | str | None = None
    for attempt in range(retries):
        try:
            code, _data = _http_json("PATCH", _site(f"/api/research/tasks/{task_id}"),
                                     {"status": status}, timeout=20)
            if code == 200:
                return True
            if code == 404:
                print(f"  ! tâche {task_id} inconnue du serveur (404) — statut local seul.")
                return False
            last = f"HTTP {code}"
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(2 * (attempt + 1))
    print(f"  ! statut {status} non poussé (tâche {task_id}) : {str(last)[:140]}")
    return False


def push_pending_results(results: list[dict] | None = None, secrets=()) -> tuple[int, int, int]:
    """Pousse les résultats non poussés (nouveaux + échecs précédents), en
    sautant ceux déjà présents côté serveur (idempotent). Persiste le fichier.
    Retourne (poussés, en_échec, total_en_attente)."""
    own = results is None
    results = _read(RESULTS_PATH, []) if own else results
    assert isinstance(results, list)
    todo = select_unpushed(results)
    if not MAIN_SITE_URL or not todo:
        return 0, 0, len(todo)
    known = remote_result_task_ids()  # None → serveur injoignable : on pousse quand même
    ok = ko = 0
    for res in todo:
        tid = res.get("task_id")
        if known is not None and tid and str(tid) in known:
            res.update(pushed=True, pushed_at=_now_iso(), push_note="déjà présent côté serveur (dédupliqué)")
            res.pop("push_error", None)
            ok += 1
            continue
        payload = {"kind": res.get("kind", "note"), "data": res.get("data", {}), "task_id": tid}
        safe = json.loads(redact(json.dumps(payload, ensure_ascii=False), secrets))
        try:
            code, _data = _http_json("POST", _site("/api/research/results"), safe, timeout=30)
            if code == 200:
                res.update(pushed=True, pushed_at=_now_iso())
                res.pop("push_error", None)
                ok += 1
                print(f"  → résultat poussé (tâche {tid})")
            else:
                res.update(pushed=False, push_error=f"HTTP {code}")
                ko += 1
                print(f"  ! push refusé (tâche {tid}) : HTTP {code}")
        except Exception as exc:  # noqa: BLE001
            res.update(pushed=False, push_error=redact(str(exc), secrets)[:200])
            ko += 1
            print(f"  ! push impossible (tâche {tid}) : {redact(str(exc), secrets)[:140]}")
    _write(RESULTS_PATH, results)
    return ok, ko, len(todo)


def poll_studies(task_ids: list, wait_s: int = 45, tries: int = 3, quiet: bool = False) -> dict[str, dict]:
    """Attend le bilan de l'étude serveur (structuration + vérification) pour
    les tâches données. Retourne {task_id: study} pour les bilans prêts."""
    tids = [str(t) for t in (task_ids or []) if t]
    found: dict[str, dict] = {}
    if not tids or not MAIN_SITE_URL:
        return found
    per = max(5, wait_s // max(1, tries))
    # 1er essai : un seul gros pull ; suivants : pulls ciblés par tâche manquante.
    items = pull_results() or []
    for r in items:
        if r.get("task_id") and r.get("study"):
            found[str(r["task_id"])] = r["study"]
    for i in range(1, tries):
        missing = [t for t in tids if t not in found]
        if not missing:
            break
        if not quiet:
            print(f"  🧠 étude serveur : {len(found)}/{len(tids)} prête(s), nouvelle vérif dans ~{per}s…")
        time.sleep(per)
        for t in missing:
            for r in pull_results(task_id=t) or []:
                if str(r.get("task_id")) == t and r.get("study"):
                    found[t] = r["study"]
                    break
    return found


def server_colab_url() -> str:
    return (MAIN_SITE_URL.rstrip("/") + "/colab.html") if MAIN_SITE_URL else ""


# ------------------------------------------------------------ seed initial ---
def _seed_tasks_from_github(branch: str | None = None) -> bool:
    """Cache initial : télécharge le seed de démo (colab/tasks.json du repo)
    UNIQUEMENT si aucun cache local n'existe (v1 écrasait à chaque run)."""
    if os.path.exists(TASKS_PATH):
        return False
    branch = branch or os.environ.get("COLAB_BRANCH", "") or DEFAULT_BRANCH
    url = f"https://raw.githubusercontent.com/{REPO}/{branch}/colab/tasks.json"
    try:
        _status, text, _final = _http_get(url, timeout=25, retries=1)
        tasks = json.loads(text)
        if not isinstance(tasks, list):
            print("! seed tasks.json : contenu inattendu — cache vide.")
            return False
        _write(TASKS_PATH, tasks)
        print(f"↓ cache initialisé depuis le seed GitHub ({branch}, {len(tasks)} tâche(s) de démo)")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"! seed GitHub impossible ({str(exc)[:140]}) — cache vide.")
        return False


# ------------------------------------------------------------ orchestration --
def preflight(llm_cfg: dict | None = None, branch: str | None = None, quiet: bool = False) -> dict:
    """Diagnostic SANS exécution : versions, serveur, backend, file fusionnée, LLM."""
    report: dict = {
        "version": COLAB_SCRIPT_VERSION,
        "http_engine": http_engine(),
        "site": MAIN_SITE_URL,
        "server_ok": False,
        "status": None,
        "tasks_local": 0,
        "tasks_remote": 0,
        "pending": [],
        "unpushed_results": 0,
        "llm": None,
    }
    if not quiet:
        print(f"🔍 pré-vol — main.py v{COLAB_SCRIPT_VERSION} (HTTP : {http_engine()})")
        print(f"   site : {MAIN_SITE_URL or '(mode local pur)'}")
    if not os.path.exists(TASKS_PATH):
        _seed_tasks_from_github(branch)
    local = _read(TASKS_PATH, [])
    report["tasks_local"] = len(local)
    remote: list[dict] = []
    if MAIN_SITE_URL:
        ok, msg = wake_server(quiet=quiet)
        report["server_ok"] = ok
        if not quiet:
            print(("✅ " if ok else "⚠️ ") + msg)
        st = get_server_status()
        report["status"] = st
        if st and not quiet:
            counts = st.get("counts", {})
            print(f"   backend : {st.get('store_backend', '?')}"
                  + (f" ({st.get('store_repo')})" if st.get("store_repo") else "")
                  + f" · moteur : {st.get('primary_provider', '?')}"
                  + (" (démo)" if st.get("demo_mode") else ""))
            print(f"   distant : {counts.get('research_tasks', '?')} tâche(s), "
                  f"{counts.get('research_results', '?')} résultat(s), "
                  f"{counts.get('knowledge', '?')} entrée(s) en base")
        remote = pull_tasks()
        report["tasks_remote"] = len(remote)
    elif not quiet:
        print("   mode local pur : ni pull ni push (définis MAIN_SITE_URL pour synchroniser).")
    merged = merge_tasks(local, remote)
    pending = [t for t in merged if t.get("status") in ("pending", "processing")]
    report["pending"] = [{"id": t.get("id"), "kind": t.get("kind"),
                          "target": str(t.get("target", ""))[:90],
                          "by": t.get("by"), "status": t.get("status")} for t in pending]
    report["unpushed_results"] = len(select_unpushed(_read(RESULTS_PATH, [])))
    if not quiet:
        print(f"📥 {len(local)} en cache local, {len(remote)} distante(s) → "
              f"{len(pending)} pending après fusion")
        for t in report["pending"][:10]:
            print(f"   • [{t['kind']}] {t['target']} (par {t['by']}, {t['status']})")
        if len(pending) > 10:
            print(f"   … et {len(pending) - 10} autre(s)")
        if report["unpushed_results"]:
            print(f"📤 {report['unpushed_results']} résultat(s) en attente de push (échecs précédents).")
    if llm_cfg is not None:
        ok, msg = llm_ping(llm_cfg)
        report["llm"] = {"ok": ok, "message": msg}
        if not quiet:
            print(("🧠 LLM local : ✅ " if ok else "🧠 LLM local : ⚠️ ") + msg)
    return report


def run_all(
    max_tasks: int | None = None,
    fetch_top: int = 1,
    summarize: bool = False,
    llm: dict | None = None,
    push: bool = True,
    poll_study: bool = True,
    study_wait_s: int = 45,
    branch: str | None = None,
) -> list[dict]:
    """Exécute la file fusionnée (local + distant). Retourne les NOUVEAUX
    résultats du run (même contrat que la v1).

    - max_tasks : borne le run (sessions Colab limitées).
    - fetch_top : pour kind=search, lit aussi le texte des N premiers résultats.
    - summarize + llm (ou env COLAB_LLM_*) : résumé local par LLM (1 appel/tâche).
    - push : repousse statuts + résultats (avec retry + déduplication).
    - poll_study : attend le bilan de l'étude serveur et l'affiche.
    """
    t0 = time.time()
    llm_cfg: dict | None = None
    secrets: list[str] = []
    if summarize:
        try:
            llm_cfg = llm if isinstance(llm, dict) else llm_config_from_env()
        except ValueError as exc:
            print(f"! {exc} — résumés désactivés.")
            llm_cfg = None
        if llm_cfg is None:
            print("! SUMMARIZE demandé mais aucune clé (COLAB_LLM_API_KEY) — brut seul.")
        else:
            secrets = [llm_cfg["api_key"]]
            print(f"🧠 résumés locaux activés ({llm_cfg['provider']}/{llm_cfg['model']}, ~1 appel/tâche)")

    if not os.path.exists(TASKS_PATH):
        _seed_tasks_from_github(branch)
    tasks = _read(TASKS_PATH, [])
    remote: list[dict] = []
    if MAIN_SITE_URL:
        ok, msg = wake_server()
        print(("✅ " if ok else "⚠️ ") + msg)
        remote = pull_tasks()
        print(f"📥 {len(tasks)} en cache local, {len(remote)} distante(s) (source de vérité : serveur)")
    tasks = merge_tasks(tasks, remote)
    _write(TASKS_PATH, tasks)
    results = _read(RESULTS_PATH, [])
    pending = [t for t in tasks if t.get("status") in ("pending", "processing")]
    if max_tasks:
        pending = pending[:max_tasks]
    print(f"▶ {len(pending)} tâche(s) à exécuter (HTTP : {http_engine()})")
    if not pending:
        if push and MAIN_SITE_URL and select_unpushed(results):
            okc, koc, total = push_pending_results(results, secrets=secrets)
            print(f"📤 push : {okc} poussé(s), {koc} en échec sur {total} en attente.")
        else:
            print("Rien à faire ✅ (ni tâche pending, ni résultat à pousser).")
        return []

    done: list[dict] = []
    for i, task in enumerate(pending, 1):
        kind = task.get("kind")
        target = str(task.get("target", ""))
        print(f"\n[{i}/{len(pending)}] {kind} : {target[:90]}")
        task["status"] = "processing"
        _write(TASKS_PATH, tasks)  # sauvegarde incrémentale : pas de perte en cas de coupure
        if MAIN_SITE_URL:
            push_task_status(task.get("id"), "processing")
        try:
            if kind == "search":
                data = run_search(task, fetch_top=fetch_top)
            elif kind == "fetch":
                data = run_fetch(task)
            elif kind == "note":
                data = run_note(task)
            elif kind == "deep":
                data = run_deep(task)
            else:
                raise ValueError(f"kind inconnu : {kind} (attendu : search|fetch|note|deep)")
            if data.get("error"):
                print(f"  ⚠️ {str(data['error'])[:200]}")
            if llm_cfg is not None and kind in ("search", "fetch", "deep"):
                summary = summarize_entry(kind, data, llm_cfg)
                if summary.get("summary"):
                    data["summary"] = summary
                    print(f"  🧠 résumé : {summary['summary'][:140]}")
                else:
                    data["summary_error"] = summary.get("error", "?")[:220]
                    print(f"  ! résumé impossible : {data['summary_error'][:160]}")
            task.update(status="done", error=None)
            entry = {"task_id": task.get("id"), "kind": kind, "data": data,
                     "pushed": False, "created_at": _now_iso()}
            results.append(entry)
            done.append(entry)
            if MAIN_SITE_URL:
                push_task_status(task.get("id"), "done")
            print(f"  ✅ done ({_describe_data(kind, data)})")
        except Exception as exc:  # noqa: BLE001 — une tâche KO n'arrête pas le run
            task.update(status="failed", error=redact(str(exc), secrets)[:300])
            if MAIN_SITE_URL:
                push_task_status(task.get("id"), "failed")
            print(f"  ❌ failed : {redact(str(exc), secrets)[:200]}")
        _write(TASKS_PATH, tasks)
    _write(RESULTS_PATH, results)

    if push and MAIN_SITE_URL:
        okc, koc, total = push_pending_results(results, secrets=secrets)
        print(f"\n📤 push : {okc} poussé(s), {koc} en échec sur {total} en attente.")
    elif not MAIN_SITE_URL:
        print("\n📤 push désactivé (pas d'URL de site) — résultats dans results.json uniquement.")

    if poll_study and MAIN_SITE_URL and done:
        print("\n🧠 attente de l'étude serveur (structuration + vérification)…")
        studies = poll_studies([e.get("task_id") for e in done], wait_s=study_wait_s)
        for e in done:
            st = studies.get(str(e.get("task_id")))
            if st:
                e["study"] = st
                entry = st.get("entry") or {}
                if entry.get("title"):
                    print(f"  • {str(e.get('task_id'))[:12]} → {st.get('status')} « {entry['title'][:70]} »"
                          + (f" (confiance {st.get('confidence')})" if st.get("confidence") else ""))
                else:
                    print(f"  • {str(e.get('task_id'))[:12]} → {st.get('status')} ({str(st.get('reason', ''))[:90]})")
        if studies:
            _write(RESULTS_PATH, results)
        missing = [e for e in done if str(e.get("task_id")) not in studies]
        if missing:
            print(f"  ⏳ {len(missing)} étude(s) pas encore prête(s) — "
                  f"recharge {server_colab_url()} dans 1 min.")
    dt = time.time() - t0
    print(f"\n🏁 {len(done)} tâche(s) exécutée(s) en {dt:.0f}s. Résultats : {RESULTS_PATH}")
    return done


def show_results(limit: int = 8, poll: bool = False, study_wait_s: int = 20) -> list[dict]:
    """Affiche les derniers résultats (cartes lisibles). `poll=True` rafraîchit
    les bilans d'étude serveur manquants. Retourne les entrées affichées."""
    results = _read(RESULTS_PATH, [])
    print(f"{len(results)} résultat(s) au total.")
    if poll and MAIN_SITE_URL and results:
        ids = [r.get("task_id") for r in results[-limit:] if r.get("task_id") and not r.get("study")]
        studies = poll_studies(ids, wait_s=study_wait_s, tries=2, quiet=True)
        if studies:
            for r in results:
                if str(r.get("task_id")) in studies:
                    r["study"] = studies[str(r["task_id"])]
            _write(RESULTS_PATH, results)
    icons = {"search": "🔎", "fetch": "📄", "note": "📝", "deep": "🧭"}
    for r in results[-limit:]:
        kind = r.get("kind", "?")
        d = r.get("data", {}) or {}
        pushed = "poussé ✅" if r.get("pushed") else ("push ❌" if r.get("push_error") else "non poussé ⏳")
        print(f"\n{'─' * 60}\n{icons.get(kind, '•')} {str(kind).upper()} · "
              f"tâche {str(r.get('task_id'))[:12]} · {r.get('created_at', '?')} · {pushed}")
        if kind in ("search", "deep"):
            print(f"   requête : {d.get('query', '?')[:100]} (moteur : {d.get('engine', '?')})")
            for j, it in enumerate((d.get("results") or [])[:4], 1):
                if not isinstance(it, dict):
                    continue
                extra = " 📖" if it.get("text") else ""
                print(f"   {j}. {str(it.get('title', '?'))[:75]}{extra}\n      {str(it.get('url', ''))[:90]}")
                if it.get("snippet"):
                    print(f"      « {str(it['snippet'])[:130]} »")
            if d.get("error"):
                print(f"   ⚠️ {str(d['error'])[:160]}")
        elif kind == "fetch":
            print(f"   URL : {str(d.get('url', '?'))[:100]}")
            if d.get("title"):
                print(f"   titre : {str(d['title'])[:100]}")
            print(f"   texte : {len(d.get('text', ''))} car." + (f" — {str(d['text'])[:150]}…" if d.get("text") else ""))
            if d.get("error"):
                print(f"   ⚠️ {str(d['error'])[:160]}")
        else:
            print(f"   {str(d.get('content', ''))[:300]}")
        summ = d.get("summary") if isinstance(d.get("summary"), dict) else None
        if summ and summ.get("summary"):
            print(f"   🧠 résumé local ({summ.get('provider', '?')}) : {summ['summary'][:200]}")
        elif d.get("summary_error"):
            print(f"   🧠 résumé local : ⚠️ {str(d['summary_error'])[:140]}")
        st = r.get("study") if isinstance(r.get("study"), dict) else None
        if st:
            entry = st.get("entry") or {}
            if entry.get("title"):
                print(f"   🏫 étude serveur : {st.get('status')} « {entry['title'][:70]} »"
                      + (f" (confiance {st.get('confidence')})" if st.get("confidence") else ""))
            else:
                print(f"   🏫 étude serveur : {st.get('status')} ({str(st.get('reason', ''))[:120]})")
    if server_colab_url():
        print(f"\n🔗 Détail + étude sur le site : {server_colab_url()}")
    return results[-limit:]


# ------------------------------------------------------------------ CLI -----
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recherche web Colab v2 (synchro robuste, résumé optionnel).")
    ap.add_argument("--max-tasks", type=int, default=int(os.environ.get("MAX_TASKS", "0") or 0) or None)
    ap.add_argument("--fetch-top", type=int, default=int(os.environ.get("FETCH_TOP", "1") or 1))
    ap.add_argument("--summarize", action="store_true", default=os.environ.get("SUMMARIZE", "") == "1")
    ap.add_argument("--no-push", action="store_true", help="n'envoie rien au site (local seul)")
    ap.add_argument("--no-poll", action="store_true", help="n'attend pas l'étude serveur")
    ap.add_argument("--preflight-only", action="store_true", help="diagnostic seul, sans exécuter")
    ap.add_argument("--show", action="store_true", help="affiche les derniers résultats et quitte")
    ap.add_argument("--study-wait", type=int, default=45)
    args = ap.parse_args(argv)

    if args.show:
        show_results(poll=not args.no_poll)
        return 0
    llm_cfg: dict | None = None
    if args.summarize:
        try:
            llm_cfg = llm_config_from_env()
        except ValueError as exc:
            print(f"! {exc}")
            return 2
        if llm_cfg is None:
            print("! --summarize sans COLAB_LLM_API_KEY — résumés désactivés.")
            args.summarize = False
    if args.preflight_only:
        preflight(llm_cfg=llm_cfg)
        return 0
    done = run_all(
        max_tasks=args.max_tasks,
        fetch_top=args.fetch_top,
        summarize=args.summarize,
        llm=llm_cfg,
        push=not args.no_push,
        poll_study=not args.no_poll,
        study_wait_s=args.study_wait,
    )
    print(f"\n{len(done)} tâche(s) exécutée(s). Résultats : {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
