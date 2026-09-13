"""Tests for the FastAPI endpoints."""

from fastapi.testclient import TestClient

import app.agent as agent_mod
from app.main import app

client = TestClient(app)


class _BoomLLM:
    name = "openai"

    def decide(self, *args, **kwargs):
        raise RuntimeError("Error code: 401 - invalid_api_key: Incorrect API key provided")


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "calculator" in body["tools"]


def test_chat_math():
    resp = client.post("/api/chat", json={"message": "what is 6 * 7"})
    assert resp.status_code == 200
    body = resp.json()
    assert "42" in body["reply"]
    assert body["tool_calls"][0]["name"] == "calculator"


def test_chat_requires_message():
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422


def test_index_served():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_chat_falls_back_gracefully_when_llm_fails(monkeypatch):
    """A broken LLM (e.g. invalid key) must not surface a 500 to the UI."""
    monkeypatch.setattr(agent_mod, "get_llm", lambda: _BoomLLM())
    resp = client.post("/api/chat", json={"message": "what is 2+2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "rule-based (fallback)"
    assert "offline mode" in body["reply"].lower()
    assert "api key" in body["reply"].lower()  # explains the likely cause
    assert "4" in body["reply"]  # offline brain still answered


def test_chat_fallback_in_sdr_mode(monkeypatch):
    monkeypatch.setattr(agent_mod, "get_llm", lambda: _BoomLLM())
    resp = client.post(
        "/api/chat", json={"message": "hello", "mode": "sdr", "lead_id": "l1"}
    )
    assert resp.status_code == 200
    assert resp.json()["provider"] == "rule-based (fallback)"
