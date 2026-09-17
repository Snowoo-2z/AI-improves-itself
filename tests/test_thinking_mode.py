"""Tests unitaires et d'intégration pour le Mode Pensée (Thinking Mode).

Vérifie :
1. L'extraction du bloc <think>...</think> et de la réponse propre (_extract_thinking).
2. L'injection de la directive de pensée dans le prompt système quand thinking=True.
3. Le comportement de handle_chat et handle_chat_stream avec thinking activé/désactivé.
4. La présence du champ thinking dans le résultat final.
5. Les endpoints API /api/chat et /api/chat/stream avec le paramètre thinking.
6. Le comportement déterministe du LocalDemoProvider en mode pensée.
7. Les efforts de réflexion (off / low / medium / high) : normalisation,
   directives distinctes, longueur de pensée calibrée en mode démo, compat API.
"""
import json
import os
import sys

# Racine du dépôt dans le sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from core.ai.chat import _build_state, _extract_thinking, handle_chat, handle_chat_stream
from core.ai.providers import LocalDemoProvider
from core.server import app

client = TestClient(app)


def check(label: str, cond: bool) -> None:
    if cond:
        print(f"  ✅ {label}")
    else:
        print(f"  ❌ {label}")
        raise AssertionError(label)


def test_extract_thinking():
    print("\n== 1. _extract_thinking (séparation pensée / réponse) ==")

    raw1 = "<think>1. Analyse de la question\n2. Formulation</think>Voici la réponse finale."
    reply1, think1 = _extract_thinking(raw1)
    check("Extrait la pensée complète", think1 == "1. Analyse de la question\n2. Formulation")
    check("Extrait la réponse propre sans balises", reply1 == "Voici la réponse finale.")

    raw2 = "Texte normal sans pensée"
    reply2, think2 = _extract_thinking(raw2)
    check("Pas de pensée si pas de balise", think2 is None)
    check("Conserve la réponse brute", reply2 == "Texte normal sans pensée")

    raw3 = "<think>Pensée sans fermeture"
    reply3, think3 = _extract_thinking(raw3)
    check("Gère la balise <think> non fermée", think3 == "Pensée sans fermeture")


def test_build_state_thinking():
    print("\n== 2. _build_state (injection du prompt thinking) ==")

    state_off = _build_state([{"role": "user", "content": "Bonjour"}], thinking=False)
    check("Thinking désactivé dans le state", state_off["thinking"] is False)
    check("Pas de directive thinking dans le prompt", "MODE PENSÉE / THINKING (ACTIVÉ)" not in state_off["system"])

    state_on = _build_state([{"role": "user", "content": "Bonjour"}], thinking=True)
    check("Thinking activé dans le state", state_on["thinking"] is True)
    check("Directive thinking présente dans le prompt", "MODE PENSÉE / THINKING (ACTIVÉ)" in state_on["system"])


def test_local_demo_thinking():
    print("\n== 3. LocalDemoProvider en mode pensée ==")

    demo = LocalDemoProvider()
    messages_off = [
        {"role": "system", "content": "Prompt standard"},
        {"role": "user", "content": "Quelles sont tes compétences ?"},
    ]
    res_off = demo.chat(messages_off)
    check("Sans directive : pas de <think>", "<think>" not in res_off.content)

    messages_on = [
        {"role": "system", "content": "Prompt avec MODE PENSÉE / THINKING (ACTIVÉ)"},
        {"role": "user", "content": "Quelles sont tes compétences ?"},
    ]
    res_on = demo.chat(messages_on)
    check("Avec directive : présence de <think>", "<think>" in res_on.content and "</think>" in res_on.content)


def test_handle_chat_thinking():
    print("\n== 4. handle_chat et handle_chat_stream ==")

    # Non-stream
    out_off = handle_chat([{"role": "user", "content": "Quelles sont tes compétences ?"}], thinking=False)
    check("handle_chat thinking=False : thinking est None", out_off.get("thinking") is None)
    check("handle_chat thinking=False : réponse présente", bool(out_off.get("reply")))

    out_on = handle_chat([{"role": "user", "content": "Quelles sont tes compétences ?"}], thinking=True)
    check("handle_chat thinking=True : thinking est peuplé", bool(out_on.get("thinking")))
    check("handle_chat thinking=True : reply ne contient pas <think>", "<think>" not in out_on.get("reply", ""))

    # Stream
    events_on = list(handle_chat_stream([{"role": "user", "content": "Quelles sont tes compétences ?"}], thinking=True))
    done_ev = next((ev for ev in events_on if ev.get("type") == "done"), None)
    check("Stream produit un événement done", done_ev is not None)
    check("Stream done contient thinking", bool(done_ev.get("thinking")))
    check("Stream done reply propre", "<think>" not in done_ev.get("reply", ""))


def test_api_endpoints_thinking():
    print("\n== 5. Endpoints API (/api/chat et /api/chat/stream) ==")

    # POST /api/chat
    res_post = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Quelles sont tes compétences ?"}],
        "thinking": True,
    })
    check("/api/chat répond 200", res_post.status_code == 200)
    data = res_post.json()
    check("/api/chat thinking renvoyé", bool(data.get("thinking")))
    check("/api/chat reply propre", "<think>" not in data.get("reply", ""))

    # POST /api/chat/stream
    res_stream = client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": "Quelles sont tes compétences ?"}],
        "thinking": True,
    })
    check("/api/chat/stream répond 200", res_stream.status_code == 200)
    lines = res_stream.text.split("\n")
    done_payload = None
    for line in lines:
        if line.startswith("data:"):
            payload_str = line[5:].strip()
            if payload_str and payload_str != "[DONE]":
                try:
                    payload = json.loads(payload_str)
                    if payload.get("type") == "done":
                        done_payload = payload
                except Exception:
                    pass
    check("/api/chat/stream SSE contient done", done_payload is not None)
    check("/api/chat/stream SSE done contient thinking", bool(done_payload and done_payload.get("thinking")))


def test_thinking_efforts():
    print("\n== 7. Efforts de réflexion (off / low / medium / high) ==")
    from core.ai.chat import THINKING_EFFORTS, _thinking_directive, normalize_thinking

    check("Efforts exposés", THINKING_EFFORTS == ("low", "medium", "high"))
    check("Normalize True → medium (compat)", normalize_thinking(True) == "medium")
    check("Normalize False → off (compat)", normalize_thinking(False) == "off")
    check("Normalize None → off", normalize_thinking(None) == "off")
    check("Normalize 'high' → high", normalize_thinking("high") == "high")
    check("Normalize ' Off ' → off", normalize_thinking(" Off ") == "off")
    check("Normalize 'on' → medium", normalize_thinking("on") == "medium")
    check("Normalize inconnu → off", normalize_thinking("très haut") == "off")

    low = _thinking_directive("low")
    med = _thinking_directive("medium")
    high = _thinking_directive("high")
    check("Off → aucune directive", _thinking_directive("off") is None)
    check(
        "Chaque effort porte le marqueur THINKING",
        all(d and "MODE PENSÉE / THINKING (ACTIVÉ)" in d for d in (low, med, high)),
    )
    check("Les 3 directives sont distinctes", len({low, med, high}) == 3)
    check("L'effort est indiqué dans la directive", "FAIBLE" in low and "ÉLEVÉ" in high and "MOYEN" in med)

    state_low = _build_state([{"role": "user", "content": "Bonjour"}], thinking="low")
    check("State 'low' : effort normalisé", state_low["thinking_effort"] == "low")
    check("State 'low' : directive faible dans le prompt", "FAIBLE" in state_low["system"])
    state_high = _build_state([{"role": "user", "content": "Bonjour"}], thinking="high")
    check("State 'high' : effort normalisé", state_high["thinking_effort"] == "high")
    check("State 'high' : directive élevée dans le prompt", "ÉLEVÉ" in state_high["system"])
    state_off = _build_state([{"role": "user", "content": "Bonjour"}], thinking="off")
    check("State 'off' : pas de directive", "MODE PENSÉE / THINKING (ACTIVÉ)" not in state_off["system"])

    out_high = handle_chat([{"role": "user", "content": "Quelles sont tes compétences ?"}], thinking="high")
    check("handle_chat 'high' : thinking peuplé", bool(out_high.get("thinking")))
    check("handle_chat 'high' : effort renvoyé", out_high.get("thinking_effort") == "high")
    check("handle_chat 'high' : reply propre", "<think>" not in out_high.get("reply", ""))

    # Stream : l'événement done porte l'effort.
    events_high = list(handle_chat_stream([{"role": "user", "content": "Quelles sont tes compétences ?"}], thinking="high"))
    done_high = next((ev for ev in events_high if ev.get("type") == "done"), None)
    check("Stream 'high' done : effort renvoyé", bool(done_high and done_high.get("thinking_effort") == "high"))


def test_local_demo_thinking_efforts():
    print("\n== 8. Mode démo : longueur de la pensée calibrée sur l'effort ==")
    demo = LocalDemoProvider()

    def think_len(effort):
        state = _build_state([{"role": "user", "content": "Quelles sont tes compétences ?"}], thinking=effort)
        res = demo.chat(state["messages"])
        _, think = _extract_thinking(res.content)
        return len(think or "")

    lengths = {e: think_len(e) for e in ("low", "medium", "high")}
    check("Pensée présente à chaque effort", all(v > 0 for v in lengths.values()))
    check(f"low < medium < high (mesuré : {lengths})", lengths["low"] < lengths["medium"] < lengths["high"])


def test_api_endpoints_thinking_efforts():
    print("\n== 9. Endpoints API : effort en paramètre (string) + compat booléen ==")

    res = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Quelles sont tes compétences ?"}],
        "thinking": "low",
    })
    check("API thinking='low' : 200", res.status_code == 200)
    check("API thinking='low' : effort renvoyé", res.json().get("thinking_effort") == "low")
    check("API thinking='low' : thinking renvoyé", bool(res.json().get("thinking")))

    res2 = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Quelles sont tes compétences ?"}],
        "thinking": "off",
    })
    check("API thinking='off' : 200", res2.status_code == 200)
    check("API thinking='off' : pas de thinking", res2.json().get("thinking") is None)

    res3 = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Quelles sont tes compétences ?"}],
        "thinking": True,  # compat historique (booléen)
    })
    check("API thinking=true (compat) : 200", res3.status_code == 200)
    check("API thinking=true (compat) : effort medium", res3.json().get("thinking_effort") == "medium")

    # Stream : effort accepté côté SSE aussi.
    res_stream = client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": "Quelles sont tes compétences ?"}],
        "thinking": "high",
    })
    check("API stream thinking='high' : 200", res_stream.status_code == 200)
    done_payload = None
    for line in res_stream.text.split("\n"):
        if line.startswith("data:"):
            payload_str = line[5:].strip()
            if payload_str and payload_str != "[DONE]":
                try:
                    payload = json.loads(payload_str)
                    if payload.get("type") == "done":
                        done_payload = payload
                except Exception:
                    pass
    check("API stream 'high' : done avec effort", bool(done_payload and done_payload.get("thinking_effort") == "high"))


def run_all():
    print("=== Tests Mode Pensée (Thinking Mode) ===")
    test_extract_thinking()
    test_build_state_thinking()
    test_local_demo_thinking()
    test_handle_chat_thinking()
    test_api_endpoints_thinking()
    test_thinking_efforts()
    test_local_demo_thinking_efforts()
    test_api_endpoints_thinking_efforts()
    print("\n====================================================================")
    print("RÉSULTAT : Tous les tests Mode Pensée sont au vert ✅")


if __name__ == "__main__":
    run_all()
