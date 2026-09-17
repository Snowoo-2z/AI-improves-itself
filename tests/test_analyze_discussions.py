"""Tests de l'analyseur automatique de discussions (colab/analyze_discussions.py).

Sans aucun appel réseau : LLM mocké (dispatch sur le prompt système), recherche
web mockée (ou cascade HTTP mockée), HTTP site mocké. On vérifie :
- parse_discussions_payload : base64 UTF-8 (accents), JSON brut, liste brute,
  blocs [text, image] → texte seul, payloads invalides → None,
- parse_llm_json tolérant + redact() de la clé API,
- cascade web_search (fixtures DDG, HTTP mocké),
- mistral_call : 401 (config), 429 (Retry-After + relance), réponse 200,
- merge_patch : ajout / correction par titre / pas de doublon / confiance basse,
- analyze_conversation (LLM + recherche mockés) : extraction → recherche →
  verdict sourcé → reformulation → 2e recherche → plan de base propre,
- rapports (markdown/console/stats) : compteurs + AUCUNE clé dans le rendu,
- push_to_site : mode direct (200) et repli note de recherche (404),
- fetch_knowledge_base : repli « base vide » et collage manuel.

Lancer :  python tests/test_analyze_discussions.py
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import re
import sys
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_spec = importlib.util.spec_from_file_location(
    "aiis_analyzer", os.path.join(REPO_ROOT, "colab", "analyze_discussions.py")
)
assert _spec and _spec.loader
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)

FAILED: list[str] = []
PASSED: list[str] = []

SECRET = "sk-test-SECRET-1234567890"
CFG = {"api_key": SECRET, "model": "ministral-8b-latest", "base_url": "https://api.mistral.ai/v1",
       "secrets": [SECRET]}


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


def b64(obj) -> str:
    return base64.b64encode(json.dumps(obj, ensure_ascii=False).encode("utf-8")).decode("ascii")


def quiet(*args, **kwargs):
    pass


# ---------------------------------------------------------------- fixtures ----
CONVO = {
    "id": "c-1",
    "title": "Question sur Zelda",
    "messages": [
        {"role": "user", "content": "Quand est sorti Tears of the Kingdom ?"},
        {"role": "assistant", "content": "Tears of the Kingdom est sorti le 12 mai 2023."},
        {"role": "user", "content": [{"type": "text", "text": "Et le prochain ?"},
                                     {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]},
    ],
}
CONVO_TEXT = "Utilisateur : Quand est sorti Tears of the Kingdom ?\nIA : Tears of the Kingdom est sorti le 12 mai 2023.\nUtilisateur : Et le prochain ?"

EXTRACT_JSON = {
    "summary": "Discussion sur la date de sortie de Tears of the Kingdom.",
    "topics": ["jeux-vidéo", "zelda"],
    "claims": [
        {"claim": "Tears of the Kingdom est sorti le 12 mai 2023", "type": "date",
         "quote": "Tears of the Kingdom est sorti le 12 mai 2023.",
         "search_query": "Tears of the Kingdom date de sortie", "check": True},
        {"claim": "C'est un excellent jeu", "type": "autre", "quote": "excellent jeu",
         "search_query": "", "check": False},
    ],
}

KBPATCH_JSON = {
    "entries": [
        {"action": "add", "match_title": "",
         "entry": {"title": "Tears of the Kingdom", "category": "jeux-vidéo", "date": "2023-05-12",
                   "summary": "Suite de Breath of the Wild, sortie le 12 mai 2023 sur Switch.",
                   "source": "https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Tears_of_the_Kingdom"},
         "reason": "date vérifiée sur Wikipédia", "confidence": 0.95},
        {"action": "update", "match_title": "Mistral AI",
         "entry": {"title": "Mistral AI", "category": "ia", "date": "2023-09-01",
                   "summary": "Lab d'IA français — info corrigée par l'analyseur.",
                   "source": "https://mistral.ai"},
         "reason": "correction vérifiée", "confidence": 0.8},
        {"action": "add", "match_title": "",
         "entry": {"title": "Info douteuse", "category": "divers", "date": "",
                   "summary": "Basée sur une source faible.", "source": "colab-analyseur"},
         "reason": "faible", "confidence": 0.2},
    ],
    "assessment": {"overall_confidence": 0.9, "issues": ["date initiale fausse"], "positives": ["correction sourcée"]},
}

KB_EXISTING = [
    {"id": "k-1", "title": "Mistral AI", "category": "ia", "date": "2023-09-01",
     "summary": "Lab d'IA français (Paris).", "source": "seed", "created_at": 1700000000},
]

SEARCH_RESULTS = {
    "query": "Tears of the Kingdom date de sortie",
    "engine": "ddg-html",
    "results": [
        {"title": "The Legend of Zelda: Tears of the Kingdom", "url": "https://en.wikipedia.org/wiki/TotK",
         "snippet": "sortie le 12 mai 2023"},
        {"title": "Nintendo - Tears of the Kingdom", "url": "https://www.nintendo.com/totk",
         "snippet": "12 May 2023"},
    ],
}


# ================================================================ 1. payload ===
print("== 1. parse_discussions_payload ==")
payload = {"app": "aiis", "export_type": "discussions", "conversations": [CONVO]}
out = an.parse_discussions_payload(b64(payload))
check("base64 UTF-8 → conversations", out is not None and len(out["conversations"]) == 1)
check("source = export_type", out and out.get("source") == "discussions")
c = out["conversations"][0] if out else {}
check("3 messages normalisés (blocs image écartés)", len(c.get("messages", [])) == 3, str(len(c.get("messages", []))))
check("blocs [text,image] → texte seul",
      c.get("messages", [{}])[-1].get("content") == "Et le prochain ?",
      json.dumps(c.get("messages", [{}])[-1]))
check("rôles préservés", [m["role"] for m in c.get("messages", [])] == ["user", "assistant", "user"])

out = an.parse_discussions_payload(json.dumps(payload, ensure_ascii=False))
check("JSON brut (str) accepté", out is not None and len(out["conversations"]) == 1)
out = an.parse_discussions_payload(json.dumps([CONVO]).encode("utf-8"))
check("liste brute (bytes) acceptée", out is not None and out["conversations"][0]["title"] == "Question sur Zelda")
check("titre manant → déduit du 1er message user",
      an.parse_discussions_payload(json.dumps([{"messages": CONVO["messages"]}]))["conversations"][0]["title"]
      .startswith("Quand est sorti"))
out = an.parse_discussions_payload("ceci n'est ni base64 ni json")
check("payload illisible → None", out is None)
out = an.parse_discussions_payload(b64({"hello": "world"}))
check("JSON sans conversations → None", out is None)
out = an.parse_discussions_payload(b64({"conversations": [{"no": "messages"}]}))
check("conversation sans messages → None", out is None)
out = an.parse_discussions_payload("")
check("vide → None", out is None)

check("messages_to_text (string)", an.messages_to_text("  bonjour  ") == "bonjour")
check("messages_to_text (blocs)", an.messages_to_text([{"type": "text", "text": "a"}, {"type": "image_url"}]) == "a")
check("messages_to_text (liste malformée) → ''", an.messages_to_text(42) == "")
check("conversation_text borné + rôles", CONVO_TEXT[:20] in an.conversation_text(CONVO))

# ================================================================ 2. LLM JSON ===
print("== 2. parse_llm_json + redact ==")
check("JSON pur", an.parse_llm_json('{"a": 1}') == {"a": 1})
check("JSON fencé", an.parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1})
check("JSON noyé", an.parse_llm_json("voici {\"a\": 1} ok") == {"a": 1})
check("liste → None (dict attendu)", an.parse_llm_json("[1,2]") is None)
check("illisible → None", an.parse_llm_json("nawak") is None)
check("redact masque la clé",
      SECRET not in an.redact(f"erreur {SECRET} fin", [SECRET]),
      an.redact(f"erreur {SECRET} fin", [SECRET]))
check("redact ignore les secrets courts", an.redact("abc", ["abc"]) == "abc")

# ================================================================ 3. recherche ===
print("== 3. Cascade web_search (HTTP mocké) ==")
DDG_HTML = """
<div class="result">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwikipedia.org%2FTotK">TotK <b>Wikipedia</b></a>
<a class="result__snippet" href="//x">Sorti le 12 mai 2023.</a>
</div>
"""


def _fake_ddg(url, timeout=30, retries=1):
    if "html.duckduckgo.com" in url:
        return (200, DDG_HTML, url)
    if "lite.duckduckgo.com" in url:
        raise AssertionError("ne devrait pas aller plus loin")
    raise AssertionError(f"attendu DDG HTML, reçu : {url}")


with mock.patch.object(an, "_http_get", side_effect=_fake_ddg):
    out = an.web_search("zelda totk", max_results=5)
check("ddg-html sert en premier", out.get("engine") == "ddg-html" and len(out["results"]) == 1, json.dumps(out)[:200])
check("url uddg décodée", out["results"][0]["url"] == "https://wikipedia.org/TotK")


def _fake_wiki_only(url, timeout=30, retries=1):
    if "duckduckgo" in url:
        return (200, "<html>rien</html>", url)
    if "fr.wikipedia.org" in url:
        return (200, json.dumps({"query": {"search": [{"title": "Zelda", "snippet": "série de jeux <b>Nintendo</b>"}]}}), url)
    raise AssertionError(f"ne devrait pas aller plus loin : {url}")


with mock.patch.object(an, "_http_get", side_effect=_fake_wiki_only):
    out = an.web_search("zelda", max_results=5)
check("DDG vide → wikipedia-fr sert", out.get("engine") == "wikipedia-fr", json.dumps(out)[:160])
check("snippet wikipédia débalisé", "série de jeux Nintendo" in out["results"][0]["snippet"])

# ================================================================ 4. mistral ===
print("== 4. mistral_call (HTTP mocké) ==")
an._last_mistral_call[0] = 0.0


def _post_401(url, payload, headers, timeout):
    return (401, {"message": "unauthorized"}, {})


with mock.patch.object(an, "_post_json_raw", side_effect=_post_401):
    content, err = an.mistral_call(CFG, "s", "u")
check("401 → erreur de config (clé)", content is None and "401" in (err or "") and "clé" in (err or ""), str(err))

calls = {"n": 0}


def _post_429_then_ok(url, payload, headers, timeout):
    calls["n"] += 1
    if calls["n"] == 1:
        return (429, {"message": "rate limit"}, {"retry-after": "1"})
    return (200, {"choices": [{"message": {"content": "pong"}}]}, {})


an._last_mistral_call[0] = 0.0
slept429: list[float] = []
with mock.patch.object(an, "_post_json_raw", side_effect=_post_429_then_ok):
    content, err = an.mistral_call(CFG, "s", "u", _sleep=slept429.append)
check("429 (Retry-After) → relance → 200", content == "pong" and err is None, str(err))
check("une pause appliquée sur le 429 (Retry-After=1 → ~2s)",
      len(slept429) >= 1 and 1.5 <= (slept429[0] if slept429 else 0) <= 2.5, str(slept429))


def _post_200(url, payload, headers, timeout):
    return (200, {"choices": [{"message": {"content": ""}}]}, {})


an._last_mistral_call[0] = 0.0
with mock.patch.object(an, "_post_json_raw", side_effect=_post_200):
    content, err = an.mistral_call(CFG, "s", "u")
check("200 réponse vide → erreur propre", content is None and err is not None, str(err))

# throttle : le marquage horodaté est mis à jour à chaque appel
an._last_mistral_call[0] = 0.0
slept = []
with mock.patch.object(an, "_post_json_raw", side_effect=_post_200):
    an.mistral_call(CFG, "s", "u", _sleep=slept.append)
check("horodatage mis à jour après l'appel", an._last_mistral_call[0] > 0.0)

# ================================================================ 5. merge ====
print("== 5. merge_patch (base de connaissances) ==")
plan = [
    {"action": "add", "match_title": "", "confidence": 0.9,
     "entry": {"title": "Nouvelle info", "category": "test", "date": "2024-01-01",
               "summary": "Ajout.", "source": "https://ex.com"}},
    {"action": "update", "match_title": "Mistral AI", "confidence": 0.8,
     "entry": {"title": "Mistral AI", "category": "ia", "date": "2023-09-01",
               "summary": "Corrigé.", "source": "https://mistral.ai"}},
    {"action": "add", "match_title": "", "confidence": 0.9,
     "entry": {"title": "mistral ai", "category": "ia", "date": "2023-09-01",
               "summary": "Doublon de titre → mise à jour.", "source": "x"}},
    {"action": "add", "match_title": "", "confidence": 0.1,
     "entry": {"title": "Trop douteux", "category": "divers", "date": "",
               "summary": "Confiance basse.", "source": "x"}},
    {"action": "bogus", "match_title": "", "confidence": 0.9,
     "entry": {"title": "Bogus", "category": "divers", "date": "", "summary": "s", "source": "x"}},
]
merged, actions = an.merge_patch(KB_EXISTING, plan)
titles = [e["title"] for e in merged]
check("2 entrées (1 initiale + 1 ajout — doublon corrigé, basse conf et bogus écartés)",
      len(merged) == 2 and titles == ["Mistral AI", "Nouvelle info"], str(titles))
kinds = [a["action"] for a in actions]
check("actions : added, updated, updated", kinds == ["added", "updated", "updated"], str(kinds))
mistral = next(e for e in merged if e["title"] == "Mistral AI")
check("id/created_at conservés à la correction", mistral.get("id") == "k-1" and mistral.get("created_at") == 1700000000)
check("summary corrigé (dernière correction gagne)", mistral["summary"] == "Doublon de titre → mise à jour.")
check("titre CANONIQUE préservé (« mistral ai » n'a pas réécrit « Mistral AI »)",
      mistral["title"] == "Mistral AI" and all(a["title"] == "Mistral AI" for a in actions if a["action"] == "updated"))
merged2, actions2 = an.merge_patch(KB_EXISTING, [])
check("plan vide → base inchangée", merged2 == KB_EXISTING and actions2 == [])

# ========================================================== 6. analyse compl. ===
print("== 6. analyze_conversation (LLM + recherche mockés) ==")


class FakeLLM:
    """Mock de mistral_call : dispatch sur le prompt système (constantes du script)."""

    def __init__(self, verdicts=None, kbpatch=None, extract=None, reformulate="date exacte de sortie Tears of the Kingdom"):
        self.verdicts = list(verdicts or [])
        self.kbpatch = kbpatch
        self.extract = extract
        self.reformulate = reformulate
        self.calls = []
        self.searches = 0

    def __call__(self, cfg, system, user, max_tokens=1000, timeout=120, _sleep=None):
        self.calls.append((system, user))
        if system is an.EXTRACT_SYSTEM:
            return json.dumps(self.extract if self.extract is not None else EXTRACT_JSON), None
        if system is an.VERDICT_SYSTEM:
            if self.verdicts:
                return json.dumps(self.verdicts.pop(0)), None
            return json.dumps({"verdict": "inverifiable", "correction": "", "sources": [],
                               "note": "aucune preuve", "confidence": 0.1}), None
        if system is an.REFORMULATE_SYSTEM:
            return self.reformulate, None
        if system is an.KBPATCH_SYSTEM:
            return json.dumps(self.kbpatch if self.kbpatch is not None else KBPATCH_JSON), None
        return "inconnu", "système inattendu"


class FakeSearch:
    def __init__(self, responses):
        self.responses = list(responses)
        self.queries = []

    def __call__(self, query, max_results=5):
        self.queries.append(query)
        if len(self.queries) <= len(self.responses):
            r = self.responses[len(self.queries) - 1]
            return {"query": query, "engine": r.get("engine", "ddg-html"),
                    "results": r.get("results", []), "error": r.get("error")}
        return {"query": query, "engine": "none", "results": [], "error": "épuisé"}


def claim_of(user: str) -> str:
    m = re.search(r"Affirmation à vérifier : « (.+?) »", user or "")
    return m.group(1) if m else ""


# 6a. parcours complet : 1 claim vérifiée (correcte) + 1 non factuelle
# (FETCH_TOP=0 : aucun fetch de page réel — la cascade HTTP est mockée ailleurs)
llm = FakeLLM(verdicts=[{"verdict": "correcte", "correction": "", "sources": ["https://en.wikipedia.org/wiki/TotK"],
                         "note": "confirmation", "confidence": 0.95}])
fs = FakeSearch([SEARCH_RESULTS])
an._ROBOTS_CACHE.clear()
with mock.patch.object(an, "FETCH_TOP", 0):
    res = an.analyze_conversation(CFG, CONVO, KB_EXISTING, llm=llm, search=fs, log=quiet)
check("status ok", res.get("status") == "ok", json.dumps(res.get("errors")))
check("2 claims (1 factuelle + 1 contexte)", len(res.get("claims", [])) == 2)
cl0, cl1 = res["claims"]
check("claim 1 : verdict correcte + source", cl0["verdict"]["verdict"] == "correcte"
      and cl0["verdict"]["sources"] == ["https://en.wikipedia.org/wiki/TotK"])
check("claim 2 : non vérifiée (check=false → pas de recherche)", cl1["verdict"]["verdict"] == "non_verifiee")
check("1 recherche effectuée (seule la claim factuelle)", fs.queries == ["Tears of the Kingdom date de sortie"])
check("plan propre : 2 entrées (la basse confiance écartée)", len(res.get("plan", [])) == 2,
      str([p["entry"]["title"] for p in res.get("plan", [])]))
check("plan_dropped_low_confidence = 1", res.get("plan_dropped_low_confidence") == 1)
check("assessment transmis", res.get("assessment", {}).get("positives") == ["correction sourcée"])
merged, actions = an.merge_patch(KB_EXISTING, res["plan"])
check("merge : 1 ajout + 1 correction de « Mistral AI »",
      [a["action"] for a in actions] == ["added", "updated"] and len(merged) == 2, str(actions))
check("le KB existe dans le prompt du patch (vues base)",
      any("Mistral AI" in u for s, u in llm.calls if s is an.KBPATCH_SYSTEM))

# 6b. reformulation : 1re recherche vide + verdict invérifiable → requête 2 + verdict 2
llm = FakeLLM(
    verdicts=[{"verdict": "inverifiable", "correction": "", "sources": [], "note": "rien", "confidence": 0.1},
              {"verdict": "correcte", "correction": "", "sources": ["https://w.org/a"], "note": "trouvé", "confidence": 0.9}],
    reformulate="Tears of the Kingdom release date",
)
fs = FakeSearch([{"results": []}, SEARCH_RESULTS])
with mock.patch.object(an, "FETCH_TOP", 0):
    res = an.analyze_conversation(CFG, CONVO, KB_EXISTING, llm=llm, search=fs, log=quiet)
cl0 = res["claims"][0]
check("reformulation déclenchée (attempts=1)", cl0.get("attempts") == 1)
check("2 recherches : originale + reformulée",
      fs.queries == ["Tears of the Kingdom date de sortie", "Tears of the Kingdom release date"], str(fs.queries))
check("verdict final après 2e recherche : correcte", cl0["verdict"]["verdict"] == "correcte")

# 6c. extraction impossible → statut error (rien d'autre ne se passe)
llm = FakeLLM()
llm.extract = "désolé, je ne sais pas répondre"  # pas de JSON
llm.calls = []
res = an.analyze_conversation(CFG, CONVO, KB_EXISTING, llm=llm, search=FakeSearch([]), log=quiet)
check("extraction illisible → status error", res.get("status") == "error" and res.get("claims") == [])
check("1 seul appel LLM (la chaîne s'arrête proprement)", len(llm.calls) == 1, str(len(llm.calls)))

# 6d. la clé n'apparaît jamais dans les prompts (le secret ne part qu'en header)
llm = FakeLLM()
fs = FakeSearch([SEARCH_RESULTS])
with mock.patch.object(an, "FETCH_TOP", 0):
    an.analyze_conversation(CFG, CONVO, KB_EXISTING, llm=llm, search=fs, log=quiet)
check("aucun prompt ne contient la clé",
      all(SECRET not in (s or "") + (u or "") for s, u in llm.calls))

# ================================================================ 7. rapports ===
print("== 7. Rapports (markdown / console / stats) ==")
kb_before = KB_EXISTING
report_discussions = [
    {
        "title": "Question sur Zelda", "messages": 3, "status": "ok",
        "summary": "Discussion sur la date de sortie de Tears of the Kingdom.",
        "topics": ["zelda"],
        "claims": [
            {"claim": "Tears of the Kingdom est sorti le 12 mai 2023", "check": True,
             "evidence": {"engine": "ddg-html", "results": [SEARCH_RESULTS["results"][0]]},
             "verdict": {"verdict": "correcte", "correction": "", "sources": ["https://w.org"], "confidence": 0.95}},
            {"claim": "C'est un excellent jeu", "check": False, "evidence": None,
             "verdict": {"verdict": "non_verifiee", "correction": "", "sources": [], "confidence": 1.0}},
        ],
        "actions": [{"action": "added", "title": "Tears of the Kingdom",
                     "entry": {"summary": "Suite de BotW."}, "reason": "vérifiée"}],
        "assessment": {"overall_confidence": 0.9, "issues": [], "positives": ["date confirmée"]},
        "errors": [],
    }
]
stats = an.collect_stats(report_discussions, 1, 2)
check("stats : 2 claims (1 correcte, 1 non vérifiée)",
      stats["claims"] == 2 and stats["correct"] == 1 and stats["unchecked"] == 1, json.dumps(stats))
check("stats : 1 recherche + moteur tracé", stats["searches"] == 1 and stats["engines"] == ["ddg-html"])
check("stats : base 1 → 2 (+1)", stats["kb_before"] == 1 and stats["kb_after"] == 2 and stats["added"] == 1)
report = {"generated_at": "2026-09-17T00:00:00Z", "model": "ministral-8b-latest", "duration_s": 42,
          "discussions": report_discussions, "stats": stats,
          "push": {"mode": "direct", "detail": "", "counts": {"added": 1, "updated": 0, "skipped": 0}}}
md = an.build_markdown(report)
check("markdown : titre + tableau affirmations",
      "# Rapport d'analyse des discussions" in md and "| # | Affirmation | Verdict |" in md)
check("markdown : verdicts + sources + action base",
      "✔ correcte" in md and "https://w.org" in md and "➕" in md)
check("markdown : push direct + stats", "direct" in md and "+1 ajout" in md.replace("+1 ajout(s)", "+1 ajout"))
console = an.build_console_report(report)
check("console : total + base + site", "TOTAL" in console and "1 → 2" in console and "direct" in console)
full = md + "\n" + console + "\n" + json.dumps(report, ensure_ascii=False)
check("rendu : AUCUNE clé API", SECRET not in full)

# ================================================================ 8. push ====
print("== 8. push_to_site (HTTP mocké) ==")
an._ROBOTS_CACHE.clear()
actions = [{"action": "added", "title": "Tears of the Kingdom",
            "entry": {"title": "Tears of the Kingdom", "category": "jeux-vidéo", "date": "2023-05-12",
                      "summary": "Sortie le 12 mai 2023.", "source": "https://w.org"}, "reason": "vérifiée"}]


def _push_http_direct(method, url, payload, timeout=30):
    assert url.endswith("/api/data/entries"), url
    if isinstance(payload, dict) and payload.get("entries"):
        assert payload["entries"][0]["title"] == "Tears of the Kingdom"
        assert SECRET not in json.dumps(payload, ensure_ascii=False)
        return (200, {"ok": True, "counts": {"added": 1, "updated": 0, "skipped": 0}})
    return (404, {})


with mock.patch.object(an, "wake_server", return_value=(True, "ok")), \
     mock.patch.object(an, "_http_json", side_effect=_push_http_direct):
    out = an.push_to_site(actions, "rapport md", "https://site.test", secrets=(SECRET,))
check("mode direct (200)", out.get("mode") == "direct" and out.get("counts", {}).get("added") == 1, str(out))


def _push_http_404(method, url, payload, timeout=30):
    if url.endswith("/api/data/entries"):
        return (404, {})
    if url.endswith("/api/research/results"):
        assert payload["kind"] == "note"
        assert SECRET not in json.dumps(payload, ensure_ascii=False)
        assert payload["data"]["meta"]["origin"] == "colab-analyseur"
        return (200, {"ok": True})
    raise AssertionError(url)


with mock.patch.object(an, "wake_server", return_value=(True, "ok")), \
     mock.patch.object(an, "_http_json", side_effect=_push_http_404):
    out = an.push_to_site(actions, "rapport md avec la " + "clé", "https://site.test", secrets=(SECRET,))
check("404 → repli note de recherche (200)", out.get("mode") == "repli-note", str(out))

with mock.patch.object(an, "wake_server", return_value=(False, "injoignable")), \
     mock.patch.object(an, "_http_json") as http:
    out = an.push_to_site(actions, "md", "https://site.test", secrets=(SECRET,))
check("serveur injoignable → mode injoignable (aucun HTTP)",
      out.get("mode") == "injoignable" and http.call_count == 0, str(out))

out = an.push_to_site([], "md", "https://site.test")
check("aucune action → rien à pousser", out.get("mode") == "aucune-change", str(out))

# ============================================================ 9. KB replis ====
print("== 9. fetch_knowledge_base (replis) ==")
kb, origin = an.fetch_knowledge_base("", prompt=lambda p="": "2")
check("pas de site + choix 2 → base vide", kb == [] and origin == "vide")
kb_json = json.dumps({"entries": [{"title": "X", "summary": "y"}]})
kb, origin = an.fetch_knowledge_base("", prompt=lambda p="": "1" if "inaccessible" in p else kb_json)
check("pas de site + collage JSON → base chargée", len(kb) == 1 and origin == "colle", json.dumps(kb))
kb_b64 = b64({"entries": [{"title": "Y", "summary": "z"}]})
kb, origin = an.fetch_knowledge_base("", prompt=lambda p="": "1" if "inaccessible" in p else kb_b64)
check("collage base64 → base chargée", len(kb) == 1 and origin == "colle")
kb, origin = an.fetch_knowledge_base("", prompt=lambda p="": "1" if "inaccessible" in p else "illisible")
check("collage illisible → base vide", kb == [] and origin == "vide")


# ------------------------------------------------------------------- fin ----
print()
print(f"RÉSULTAT : {len(PASSED)} ✅ / {len(FAILED)} ❌")
if FAILED:
    print("ÉCHECS :")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
