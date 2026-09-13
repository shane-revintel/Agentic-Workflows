"""Tool registry for the agent.

Tools are plain Python callables described by a JSON schema so they can be
exposed to an LLM for function-calling, and also invoked directly by the
built-in rule-based agent that runs without any API keys.
"""

from __future__ import annotations

import ast
import datetime as _dt
import operator
from dataclasses import dataclass
from typing import Any, Callable, Dict, List
from zoneinfo import ZoneInfo


@dataclass
class Tool:
    """A single capability the agent can call."""

    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., str]

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# --- Safe calculator -------------------------------------------------------

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    """Evaluate a numeric expression AST without using eval()."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric literals are allowed.")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported expression.")


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '23 * 19 + 4'."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
    except (ValueError, SyntaxError, ZeroDivisionError) as exc:
        return f"I couldn't evaluate '{expression}': {exc}"
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"{expression} = {result}"


# --- Clock -----------------------------------------------------------------

def current_time(timezone: str = "UTC") -> str:
    """Return the current date and time for an IANA timezone (default UTC)."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        return f"Unknown timezone '{timezone}'. Try something like 'UTC' or 'America/New_York'."
    now = _dt.datetime.now(tz)
    return now.strftime("%A, %d %B %Y, %H:%M:%S %Z")


# --- Text utilities --------------------------------------------------------

def text_stats(text: str) -> str:
    """Return simple statistics about a piece of text."""
    words = len(text.split())
    chars = len(text)
    sentences = max(1, text.count(".") + text.count("!") + text.count("?"))
    return f"words={words}, characters={chars}, sentences≈{sentences}"


def reverse_text(text: str) -> str:
    """Reverse the characters of the given text."""
    return text[::-1]


# --- Registry --------------------------------------------------------------

def build_registry() -> Dict[str, Tool]:
    tools: List[Tool] = [
        Tool(
            name="calculator",
            description="Evaluate a basic arithmetic expression such as '2 + 2' or '23 * 19'.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The arithmetic expression to evaluate.",
                    }
                },
                "required": ["expression"],
            },
            func=lambda expression: calculator(expression),
        ),
        Tool(
            name="current_time",
            description="Get the current date and time for an optional IANA timezone.",
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name, e.g. 'UTC' or 'America/New_York'.",
                    }
                },
                "required": [],
            },
            func=lambda timezone="UTC": current_time(timezone),
        ),
        Tool(
            name="text_stats",
            description="Count words, characters and sentences in a piece of text.",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to analyze."}
                },
                "required": ["text"],
            },
            func=lambda text: text_stats(text),
        ),
        Tool(
            name="reverse_text",
            description="Reverse the characters in a piece of text.",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to reverse."}
                },
                "required": ["text"],
            },
            func=lambda text: reverse_text(text),
        ),
    ]
    return {tool.name: tool for tool in tools}


REGISTRY: Dict[str, Tool] = build_registry()
