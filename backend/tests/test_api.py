"""Tests for the FastAPI endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
