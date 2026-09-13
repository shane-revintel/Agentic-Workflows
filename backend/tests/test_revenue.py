"""Tests for the inbound-revenue tools and their offline routing."""

from app.agent import Agent
from app.llm import RuleBasedLLM
from app.revenue import draft_email, forecast_revenue, qualify_lead, score_lead


def agent() -> Agent:
    return Agent(llm=RuleBasedLLM())


# --- unit tests on the tool functions --------------------------------------

def test_score_lead_hot_for_senior_high_intent():
    out = score_lead("VP Marketing", company_size="800", source="demo_request", signal="viewed pricing")
    assert "Hot" in out
    assert "Next action" in out


def test_score_lead_cold_for_junior_low_intent():
    out = score_lead("Student", company_size="3", source="newsletter")
    assert "Cold" in out


def test_qualify_lead_counts_bant():
    out = qualify_lead(budget="yes", authority="yes", need="yes", timeline="yes")
    assert "4/4" in out
    assert "Sales-ready" in out


def test_forecast_revenue_math():
    out = forecast_revenue(leads="200", meeting_rate="30%", close_rate="25%", acv="12000")
    # 200 * 0.30 = 60 meetings; 60 * 0.25 = 15 deals; 15 * 12000 = 180000
    assert "60" in out
    assert "$180,000" in out


def test_forecast_revenue_reports_missing():
    out = forecast_revenue(leads="200", meeting_rate="", close_rate="25%", acv="12000")
    assert "meeting_rate" in out


def test_draft_email_personalizes():
    out = draft_email("Sam", company="Acme", purpose="meeting_request", context="faster onboarding")
    assert "Subject:" in out
    assert "Acme" in out
    assert "Sam" in out


# --- routing through the offline agent --------------------------------------

def test_agent_routes_score_lead():
    result = agent().run(
        "score lead: title=VP Sales; company_size=1200; source=pricing; signal=demo"
    )
    assert result.tool_calls[0]["name"] == "score_lead"
    assert "Hot" in result.reply


def test_agent_routes_forecast():
    result = agent().run("forecast: leads=100 meeting_rate=0.4 close_rate=0.5 acv=10000")
    assert result.tool_calls[0]["name"] == "forecast_revenue"
    # 100 * 0.4 = 40 meetings; 40 * 0.5 = 20 deals; 20 * 10000 = 200000
    assert "$200,000" in result.reply


def test_agent_routes_qualify():
    result = agent().run("qualify: budget=yes; authority=no; need=yes; timeline=no")
    assert result.tool_calls[0]["name"] == "qualify_lead"
    assert "2/4" in result.reply


def test_agent_routes_draft_email():
    result = agent().run("draft email: name=Jordan; company=Globex; purpose=follow_up")
    assert result.tool_calls[0]["name"] == "draft_email"
    assert "Globex" in result.reply
