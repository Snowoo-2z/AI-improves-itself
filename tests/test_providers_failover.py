"""Tests du repli multi-fournisseurs et de la classification des limites.

Aucun appel réseau : chaque provider reçoit un `httpx.MockTransport` qui joue
les vraies réponses des tiers gratuits (429 de fenêtre, 429 de quota journalier,
modèle retiré, erreur upstream dans un corps 200, timeout).

Lancer :  python tests/test_providers_failover.py     (aucune dépendance de test)
"""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import httpx  # noqa: E402

from core.ai import providers as P  # noqa: E402
from core.ai.limits import GROQ, MISTRAL, OPENROUTER  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✅ {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  ❌ {label} {detail}")


# ---------------------------------------------------------------------------
# Usine de providers bouchonnés
# ---------------------------------------------------------------------------
def _json_response(request: httpx.Request, status: int, payload: dict, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=payload, headers=headers or {}, request=request)


def install_transport(monkey: dict, provider: P.OpenAICompatProvider, handler) -> None:
    """Redirige les appels httpx.post du provider vers le bouchon."""
    def patched(url, **kwargs):  # noqa: ANN001, ANN003
        request = httpx.Request("POST", url, json=kwargs.get("json"), headers=kwargs.get("headers"))
        response = handler(request)
        response.request = request
        return response

    monkey[provider.name] = httpx.post
    httpx.post = patched  # type: ignore[assignment]
    provider._patched = patched  # type: ignore[attr-defined]


def restore_transport(monkey: dict) -> None:
    for name, original in monkey.items():
        httpx.post = original  # type: ignore[assignment]
    monkey.clear()


def ok_body(text: str = "bonjour", model: str = "model-a") -> dict:
    return {"model": model, "choices": [{"message": {"role": "assistant", "content": text}}]}


def reset_state() -> None:
    """Remettre à zéro disjoncteur, chaîne en cache ET moteur préféré."""
    P.HEALTH.force_ready()
    P.HEALTH._health.clear()  # noqa: SLF001 — test
    P._cached_chain = None  # noqa: SLF001
    P._cached_chain_signature = None  # noqa: SLF001
    P._preferred = None  # noqa: SLF001 — sinon le dernier moteur gagnant est rejoué
    P.invalidate_provider_cache()


# ---------------------------------------------------------------------------
print("\n[1] 429 « fenêtre glissante » → repli sur le moteur suivant")
monkey: dict = {}
reset_state()
calls = {"mistral": 0, "groq": 0}


def mistral_429(request: httpx.Request) -> httpx.Response:
    """429 sur TOUS les modèles Mistral : la rotation interne ne peut pas sauver
    le provider → c'est Groq (moteur suivant de la chaîne) qui doit répondre."""
    calls["mistral"] += 1
    calls.setdefault("mistral_models", [])
    body = json.loads(request.content or b"{}")
    calls["mistral_models"].append(body.get("model"))
    return _json_response(
        request,
        429,
        {"error": {"message": "Rate limit exceeded, please retry after 1 second", "type": "rate_limit"}},
        headers={"retry-after": "1"},
    )


def groq_ok(request: httpx.Request) -> httpx.Response:
    calls["groq"] += 1
    return _json_response(request, 200, ok_body("réponse groq", "openai/gpt-oss-120b"))


mistral = P.OpenAICompatProvider("mistral", "https://mistral.invalid/v1", "k", MISTRAL.models)
groq = P.OpenAICompatProvider("groq", "https://groq.invalid/v1", "k", GROQ.models)
demo = P.LocalDemoProvider()
chain = [mistral, groq, demo]


def handler_router(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content or b"{}")
    return mistral_429(request) if request.url.host == "mistral.invalid" else groq_ok(request)


# Chaque provider a son propre hôte pour pouvoir router le bouchon.
mistral.base_url = "https://mistral.invalid/v1"
groq.base_url = "https://groq.invalid/v1"
install_transport(monkey, mistral, handler_router)

outcome = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=chain)
restore_transport(monkey)

check("le moteur suivant a répondu", outcome.result.provider == "groq", f"→ {outcome.result.provider}")
check("la réponse vient bien de Groq", outcome.result.content == "réponse groq")
check("pas de bascule en mode démo", outcome.fell_back_to_demo is False)
check("Mistral est mis au repos", P.HEALTH.ready_in("mistral") > 0.0)
check("le repos suit le Retry-After annoncé (1 s)", 0.5 < P.HEALTH.ready_in("mistral") <= 5,
      f"→ {P.HEALTH.ready_in('mistral'):.1f}s")
check("Groq marqué sain", P.HEALTH.ready_in("groq") == 0.0)
check("une erreur lisible est remontée", any("429" in e for e in outcome.errors), str(outcome.errors))
# Un 429 ne se mitraille pas : 1 seule requête puis repli (les requêtes refusées
# comptent dans le quota sur plusieurs tiers gratuits).
mistral_calls_first_round = calls["mistral"]
check("un seul essai PAR MODÈLE avant le repli (pas de mitraillage en 429)",
      mistral_calls_first_round == len(MISTRAL.models),
      f"→ {mistral_calls_first_round} appels pour {len(MISTRAL.models)} modèles : {calls['mistral_models']}")
check("les modèles du catalogue sont essayés dans l'ordre (8B d'abord)",
      calls["mistral_models"][0] == "ministral-8b-latest", str(calls["mistral_models"]))

print("\n[1b] Sans Retry-After, le repos par défaut = fenêtre glissante ~1 min")
reset_state()
mistral.base_url = "https://mistral.invalid/v1"
def mistral_429_no_header(request: httpx.Request) -> httpx.Response:
    """429 SANS Retry-After (cas Mistral fréquent) — uniquement pour Mistral."""
    if request.url.host != "mistral.invalid":
        return groq_ok(request)
    calls["mistral"] += 1
    return _json_response(request, 429, {"error": {"message": "Rate limit exceeded"}})


install_transport(monkey, mistral, mistral_429_no_header)
calls["mistral"] = 0  # on ne compte que ce tour-ci
out1b = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=chain)
restore_transport(monkey)
default_wait = P.HEALTH.ready_in("mistral")
check("repos par défaut ≈ 65 s", 60 <= default_wait <= 70, f"→ {default_wait:.0f}s")
check("toujours un seul essai par modèle (429 sans Retry-After non plus)",
      calls["mistral"] == len(MISTRAL.models), f"→ {calls['mistral']} appels")

print("\n[2] Le provider au repos est ignoré (pas d'appel réseau inutile)")
monkey.clear()
install_transport(monkey, mistral, handler_router)  # même routeur qu'en [1]
calls_before = calls["mistral"]
outcome2 = P.chat_with_failover([{"role": "user", "content": "re"}], None, chain=chain)
restore_transport(monkey)
health2 = P.HEALTH.snapshot()
check("réponse obtenue sans rappeler Mistral", outcome2.result.provider == "groq")
check("aucun appel supplémentaire vers Mistral", calls["mistral"] == calls_before,
      f"→ {calls['mistral']} vs {calls_before}")
check("Mistral reste au repos (disjoncteur)", health2["mistral"]["ready"] is False, str(health2["mistral"]))
check("le repos restant est exposé", health2["mistral"]["retry_in_s"] > 30, str(health2["mistral"]["retry_in_s"]))
check("aucune erreur affichée (le moteur de secours suffit)", outcome2.errors == [], str(outcome2.errors))
check("Mistral n'apparaît même pas dans les tentatives",
      all(a["provider"] != "mistral" for a in outcome2.attempts), str(outcome2.attempts))


print("\n[3] Modèle retiré (Groq, 16/08/2026) → erreur de CONFIG, repos long")
monkey.clear()
reset_state()
dead_calls = {"n": 0}


def groq_dead_model(request: httpx.Request) -> httpx.Response:
    dead_calls["n"] += 1
    return _json_response(
        request,
        404,
        {"error": {"message": "The model 'llama-3.3-70b-versatile' has been shut down. "
                              "Please migrate to openai/gpt-oss-120b", "type": "invalid_request_error"}},
    )


dead = P.OpenAICompatProvider("groq", "https://groq-dead.invalid/v1", "k", ("llama-3.3-70b-versatile",))
install_transport(monkey, dead, groq_dead_model)
outcome3 = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=[dead, P.LocalDemoProvider()])
restore_transport(monkey)
failure = P.HEALTH.snapshot()["groq"]["failure"]
check("classé en erreur de configuration", failure["kind"] == "config", f"→ {failure['kind']}")
check("repos long (pas un repos de 1 min)", P.HEALTH.ready_in("groq") > 1800,
      f"→ {P.HEALTH.ready_in('groq'):.0f}s")
check("le message cite le modèle coupé", "llama-3.3-70b-versatile" in failure["message"], failure["message"])
check("une piste de correction est donnée", "docs/FREE-TIERS.md" in failure["hint"], failure["hint"])
check("repli sur la démo locale", outcome3.fell_back_to_demo is True)
check("un seul essai (pas de retry inutile)", dead_calls["n"] == 1, f"→ {dead_calls['n']}")

print("\n[3b] Le catalogue connaît les IDs retirés")
from core.ai.limits import RETIRED_MODELS  # noqa: E402

for dead_id in (
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mistral-medium-2508",
    "magistral-small-latest",
    "devstral-2512",
):
    check(f"`{dead_id}` est référencé comme retiré", dead_id in RETIRED_MODELS)


print("\n[4] Quota MENSUEL épuisé (Mistral) → repos jusqu'au 1er du mois")
monkey.clear()
reset_state()


def mistral_monthly(request: httpx.Request) -> httpx.Response:
    return _json_response(
        request,
        429,
        {"error": {"message": "Monthly tokens quota exceeded: 4000000 tokens/month reached for this workspace"}},
    )


monthly = P.OpenAICompatProvider("mistral", "https://m.invalid/v1", "k", ("mistral-small-latest",))
install_transport(monkey, monthly, mistral_monthly)
outcome4 = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=[monthly, P.LocalDemoProvider()])
restore_transport(monkey)
failure4 = P.HEALTH.snapshot()["mistral"]["failure"]
wait4 = P.HEALTH.ready_in("mistral")
check("classé quota mensuel", failure4["kind"] == "monthly_quota", f"→ {failure4['kind']}")
check("repos > 1 jour (le mois n'est pas fini)", wait4 > 86_400, f"→ {wait4:.0f}s")
check("annonce un délai humain en jours", "j" in P.human_delay(wait4), P.human_delay(wait4))
check("repli démo", outcome4.fell_back_to_demo is True)


print("\n[5] Quota JOURNALIER (Gemini) → repos jusqu'à minuit heure du Pacifique")
monkey.clear()
reset_state()


def gemini_daily(request: httpx.Request) -> httpx.Response:
    return _json_response(
        request,
        429,
        {"error": {"message": "You exceeded your current requests list per day. "
                              "quota_id: GenerateRequestsPerDayPerProjectPerModel-FreeTier"}},
    )


gemini = P.OpenAICompatProvider("gemini", "https://g.invalid/v1", "k", ("gemini-2.5-flash",), daily_tz="us_pacific")
install_transport(monkey, gemini, gemini_daily)
outcome5 = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=[gemini, P.LocalDemoProvider()])
restore_transport(monkey)
failure5 = P.HEALTH.snapshot()["gemini"]["failure"]
wait5 = P.HEALTH.ready_in("gemini")
check("classé quota journalier", failure5["kind"] == "daily_quota", f"→ {failure5['kind']}")
check("repos ≤ 24 h", 0 < wait5 <= 86_400, f"→ {wait5:.0f}s")
check("délai humain en heures", "h" in P.human_delay(wait5), P.human_delay(wait5))
utc_wait = P.daily_reset_seconds("utc")
pacific_wait = P.daily_reset_seconds("us_pacific")
check("la fenêtre Pacifique diffère de l'UTC", abs(utc_wait - pacific_wait) > 3600,
      f"utc={utc_wait:.0f}s pacific={pacific_wait:.0f}s")


print("\n[6] OpenRouter : erreur 429 dans le corps + quota journalier des :free")
monkey.clear()
reset_state()


def openrouter_daily(request: httpx.Request) -> httpx.Response:
    # OpenRouter renvoie ses erreurs upstream dans un corps HTTP 200 ou en 429
    # avec un code explicite « free-models-per-day ».
    return _json_response(
        request,
        429,
        {"error": {"message": "Rate limit exceeded: free-models-per-day", "code": 429}},
    )


orr = P.OpenAICompatProvider("openrouter", "https://or.invalid/v1", "k", ("openrouter/free",))
install_transport(monkey, orr, openrouter_daily)
outcome6 = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=[orr, P.LocalDemoProvider()])
restore_transport(monkey)
failure6 = P.HEALTH.snapshot()["openrouter"]["failure"]
check("classé quota journalier (pas une simple fenêtre)", failure6["kind"] == "daily_quota",
      f"→ {failure6['kind']}")
check("le message cite la limite des modèles gratuits", "free-models-per-day" in failure6["message"],
      failure6["message"][:120])

print("\n[6b] Corps 200 contenant une erreur upstream → traité comme un échec")
monkey.clear()
reset_state()


def openrouter_200_with_error(request: httpx.Request) -> httpx.Response:
    return _json_response(
        request,
        200,
        {"error": {"message": "No endpoints found that meet your requirements for this model",
                   "metadata": {"provider_name": "upstream"}}},
    )


orr2 = P.OpenAICompatProvider("openrouter", "https://or2.invalid/v1", "k", ("openrouter/free",))
install_transport(monkey, orr2, openrouter_200_with_error)
outcome6b = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=[orr2, P.LocalDemoProvider()])
restore_transport(monkey)
check("l'erreur du corps 200 est détectée", outcome6b.fell_back_to_demo is True)
check("le provider upstream est nommé", any("upstream" in e for e in outcome6b.errors), str(outcome6b.errors)[:200])


print("\n[7] Rotation de modèles dans le MÊME provider (pools de quota séparés)")
monkey.clear()
reset_state()
seen_models: list[str] = []


def mistral_rotate(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content or b"{}")
    seen_models.append(body.get("model", ""))
    if body.get("model") == "mistral-small-latest":
        return _json_response(request, 429, {"error": {"message": "Rate limit exceeded"}}, headers={"retry-after": "1"})
    return _json_response(request, 200, ok_body("réponse large-2411", "mistral-large-2411"))


rotating = P.OpenAICompatProvider(
    "mistral", "https://rot.invalid/v1", "k", ("mistral-small-latest", "mistral-large-2411"), min_interval=0.0
)
install_transport(monkey, rotating, mistral_rotate)
outcome7 = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=[rotating, P.LocalDemoProvider()])
restore_transport(monkey)
check("le second modèle du provider a été essayé", "mistral-large-2411" in seen_models, str(seen_models))
check("la réponse vient du provider (pas de la démo)", outcome7.result.provider == "mistral")
check("le modèle courant a été mis à jour", rotating.model == "mistral-large-2411", rotating.model)


print("\n[8] Timeout / réseau → repos court puis repli")
monkey.clear()
reset_state()


def timeout_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectTimeout("connexion impossible", request=request)


offline = P.OpenAICompatProvider("mistral", "https://offline.invalid/v1", "k", ("mistral-small-latest",))
install_transport(monkey, offline, timeout_handler)
try:
    outcome8 = P.chat_with_failover([{"role": "user", "content": "salut"}], None, chain=[offline, P.LocalDemoProvider()])
finally:
    restore_transport(monkey)
failure8 = P.HEALTH.snapshot()["mistral"]["failure"]
check("classé réseau", failure8["kind"] == "network", f"→ {failure8['kind']}")
check("repos court (≤ 60 s)", 0 < P.HEALTH.ready_in("mistral") <= 60, f"→ {P.HEALTH.ready_in('mistral'):.0f}s")
check("repli démo sans exception", outcome8.fell_back_to_demo is True)


print("\n[9] Aucune clé configurée → démo locale pure (aucun appel réseau)")
reset_state()
for key in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)
chain9 = P.build_chain()
check("la chaîne ne contient que la démo", [p.name for p in chain9] == ["demo-local"], str([p.name for p in chain9]))
outcome9 = P.chat_with_failover([{"role": "user", "content": "bonjour"}], None)
check("réponse de la démo", outcome9.result.provider == "demo-local")
check("aucune erreur annoncée (pas de clé = pas de panne)", outcome9.errors == [], str(outcome9.errors))
check("le message explique comment activer un vrai moteur", "MISTRAL_API_KEY" in outcome9.result.content)


print("\n[10] Lecture de .env : liste de modèles + valeur par défaut du catalogue")
os.environ["MISTRAL_API_KEY"] = "cle-test"
os.environ["GROQ_API_KEY"] = "cle-test-groq"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-20b, openai/gpt-oss-120b"
reset_state()
chain10 = P.build_chain()
by_name = {p.name: p for p in chain10}
check("Mistral essaie d'abord le petit modèle (le plus fiable en gratuit)",
      by_name["mistral"].models[0] == "ministral-8b-latest", str(by_name["mistral"].models))
check("puis Small 4, puis le pool isolé large-2411",
      by_name["mistral"].models[1:3] == ["mistral-small-latest", "mistral-large-2411"],
      str(by_name["mistral"].models))
check("Groq respecte la liste du .env", by_name["groq"].models[:2] == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"],
      str(by_name["groq"].models))
check("throttle Mistral ≈ 1 req/s", abs(by_name["mistral"].min_interval - 1.05) < 0.01,
      str(by_name["mistral"].min_interval))
check("throttle Groq ≈ 30 req/min", 2.0 <= by_name["groq"].min_interval <= 2.5, str(by_name["groq"].min_interval))
check("OpenRouter absent sans clé", "openrouter" not in by_name)
check("en-têtes d'attribution OpenRouter prévus", OPENROUTER.extra_headers.get("X-Title") == "AI-improves-itself")

print("\n[11] Rapport de santé (servi par /api/status)")
report = P.health_report()
check("providers configurés listés", set(report["configured"]) == {"mistral", "groq"}, str(report["configured"]))
check("limites exposées par provider", "30 req/min" in report["limits"]["groq"]["limits"], report["limits"]["groq"]["limits"])
check("modèles exposés", report["limits"]["mistral"]["models"][0] == "ministral-8b-latest")

print("\n[12] Boucle de chat complète en démo : l'auto-amélioration fonctionne toujours")
reset_state()
for key in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)
from core.ai.chat import handle_chat  # noqa: E402
from core.prompt_system import registry  # noqa: E402

registry_file = os.path.join(REPO_ROOT, "core", "prompt_system", "prompts", "main.json")
requests_file = os.path.join(REPO_ROOT, "core", "data", "dev_requests.json")
backup = open(registry_file, "r", encoding="utf-8").read()
backup_requests = (
    open(requests_file, "r", encoding="utf-8").read() if os.path.exists(requests_file) else None
)
try:
    version_before = registry.get_current("main")["version"]
    first = handle_chat([{"role": "user", "content": "Quel est le dernier jeu Zelda ?"}])
    check("1re réponse : le défaut historique (Zelda 1986)", "1986" in first["reply"], first["reply"][:120])
    check("l'IA a modifié son propre prompt", any(e["type"] == "prompt_update" for e in first["events"]),
          str([e["type"] for e in first["events"]]))
    check("version du prompt incrémentée", registry.get_current("main")["version"] == version_before + 1)
    second = handle_chat([{"role": "user", "content": "Quel est le dernier jeu Zelda ?"}])
    check("2e réponse : corrigée (plus le 1986)", "1986" not in second["reply"], second["reply"][:140])
    check("provider = demo-local", second["provider"] == "demo-local")
finally:
    # Remettre les fichiers dans l'état d'origine (la démo écrit vraiment sur disque).
    open(registry_file, "w", encoding="utf-8").write(backup)
    if backup_requests is not None:
        open(requests_file, "w", encoding="utf-8").write(backup_requests)
    elif os.path.exists(requests_file):
        os.remove(requests_file)

reset_state()
print("\n" + "=" * 68)
print(f"RÉSULTAT : {len(PASSED)} vérifications OK, {len(FAILED)} en échec")
if FAILED:
    for item in FAILED:
        print("  ✗ " + item)
    sys.exit(1)
print("Tout est vert ✅")
