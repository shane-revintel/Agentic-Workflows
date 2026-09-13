"""Tests for leads, booking tools, SDR routing, and SDR endpoints."""

from fastapi.testclient import TestClient

from app.agent import Agent
from app.booking import book_meeting, clear_bookings, list_bookings, propose_meeting_times
from app.leads import get_lead, list_leads
from app.llm import RuleBasedLLM
from app.main import app
from app.sdr import build_sdr_system_prompt

client = TestClient(app)


def agent() -> Agent:
    return Agent(llm=RuleBasedLLM())


# --- leads -----------------------------------------------------------------

def test_leads_available():
    leads = list_leads()
    assert len(leads) >= 1
    assert get_lead(None).id == leads[0].id
    assert get_lead("l2").id == "l2"
    assert get_lead("nope").id == leads[0].id  # falls back to first


def test_lead_context_block():
    block = get_lead("l1").context_block()
    assert "Jordan Lee" in block
    assert "Why they fit" in block


# --- booking tools ---------------------------------------------------------

def test_propose_meeting_times_returns_slots():
    out = propose_meeting_times("America/New_York")
    assert out.count("\n") >= 3  # header + 3 slots


def test_book_meeting_records():
    clear_bookings()
    out = book_meeting("Jordan", "Tuesday 10:00", email="j@x.example", topic="intro")
    assert "booked" in out.lower()
    assert len(list_bookings()) == 1
    assert list_bookings()[0]["name"] == "Jordan"


def test_book_meeting_requires_time():
    out = book_meeting("Jordan", "")
    assert "specific time" in out.lower()


# --- SDR prompt ------------------------------------------------------------

def test_sdr_system_prompt_has_lead_and_goal():
    prompt = build_sdr_system_prompt(get_lead("l1"))
    assert "Jordan Lee" in prompt
    assert "meeting" in prompt.lower()
    assert "book_meeting" in prompt


# --- offline routing for booking -------------------------------------------

def test_agent_routes_book_meeting():
    clear_bookings()
    result = agent().run("book meeting: name=Priya; when=Wed 14:00; topic=demo")
    assert result.tool_calls[0]["name"] == "book_meeting"
    assert len(list_bookings()) == 1


def test_agent_routes_propose_times():
    result = agent().run("propose times")
    assert result.tool_calls[0]["name"] == "propose_meeting_times"


# --- API -------------------------------------------------------------------

def test_leads_endpoint():
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    assert any(l["name"] == "Jordan Lee" for l in resp.json())


def test_sdr_chat_mode_offline():
    resp = client.post(
        "/api/chat",
        json={"message": "book meeting: name=Sam; when=Mon 09:00", "mode": "sdr", "lead_id": "l1"},
    )
    assert resp.status_code == 200
    assert resp.json()["tool_calls"][0]["name"] == "book_meeting"


def test_bookings_endpoint():
    clear_bookings()
    client.post("/api/chat", json={"message": "book meeting: name=Ann; when=Fri 15:00"})
    resp = client.get("/api/bookings")
    assert resp.status_code == 200
    assert any(b["name"] == "Ann" for b in resp.json())
