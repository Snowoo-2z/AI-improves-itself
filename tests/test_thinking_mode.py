"""Tests unitaires et d'intégration pour le Mode Pensée (Thinking Mode).

Vérifie :
1. L'extraction du bloc <think>...</think> et de la réponse propre (_extract_thinking).
2. L'injection de la directive de pensée dans le prompt système quand thinking=True.
3. Le comportement de handle_chat et handle_chat_stream avec thinking activé/désactivé.
4. La présence du champ thinking dans le résultat final.
5. Les endpoints API /api/chat et /api/chat/stream avec le paramètre thinking.
6. Le comportement déterministe du LocalDemoProvider en mode pensée.
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


def run_all():
    print("=== Tests Mode Pensée (Thinking Mode) ===")
    test_extract_thinking()
    test_build_state_thinking()
    test_local_demo_thinking()
    test_handle_chat_thinking()
    test_api_endpoints_thinking()
    print("\n====================================================================")
    print("RÉSULTAT : Tous les tests Mode Pensée sont au vert ✅")


if __name__ == "__main__":
    run_all()
