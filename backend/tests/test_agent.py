"""Tests for the rule-based agent and tools (no API keys required)."""

from app.agent import Agent
from app.llm import RuleBasedLLM
from app.tools import calculator, current_time, reverse_text, text_stats


def make_agent() -> Agent:
    return Agent(llm=RuleBasedLLM())


def test_calculator_tool():
    assert calculator("23 * 19") == "23 * 19 = 437"
    assert calculator("2 + 2 * 3") == "2 + 2 * 3 = 8"
    assert "couldn't" in calculator("import os").lower()


def test_reverse_and_stats_tools():
    assert reverse_text("hello") == "olleh"
    assert "words=2" in text_stats("hello world")


def test_current_time_tool():
    assert "Unknown timezone" in current_time("Not/AZone")
    assert current_time("UTC")  # does not raise


def test_agent_routes_math_to_calculator():
    result = make_agent().run("What is 23 * 19?")
    assert result.tool_calls, "expected a tool call"
    assert result.tool_calls[0]["name"] == "calculator"
    assert "437" in result.reply
    assert result.provider == "rule-based"


def test_agent_routes_reverse():
    result = make_agent().run("reverse text: hello world")
    assert result.tool_calls[0]["name"] == "reverse_text"
    assert result.reply == "dlrow olleh"


def test_agent_greeting_has_no_tool_calls():
    result = make_agent().run("hello")
    assert result.tool_calls == []
    assert "inbound-revenue agent" in result.reply.lower()


def test_agent_handles_conversation_history():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello!"},
    ]
    result = make_agent().run("what is 10 / 2", history=history)
    assert "10 / 2 = 5" in result.reply
