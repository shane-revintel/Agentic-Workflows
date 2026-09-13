"""LLM client abstraction.

Two implementations are provided:

* ``RuleBasedLLM`` — a dependency-free, deterministic "brain" that can route
  simple requests to tools. It lets the whole app run end-to-end with no API
  keys, which is ideal for local development and demos.
* ``OpenAILLM`` — a real LLM backend that uses OpenAI function-calling over the
  same tool registry. It is activated automatically when ``OPENAI_API_KEY`` is
  set.

Both return a :class:`Decision` so the agent loop can treat them identically.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .tools import Tool


@dataclass
class Decision:
    """One step of reasoning: either call tools, or answer directly."""

    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    final_text: Optional[str] = None


class LLMClient:
    name: str = "base"

    def decide(self, messages: List[Dict[str, str]], tools: Dict[str, Tool]) -> Decision:
        raise NotImplementedError


# --------------------------------------------------------------------------
# Rule-based, offline brain
# --------------------------------------------------------------------------

_MATH_RE = re.compile(r"^[\d\s().+\-*/%^]+$")


class RuleBasedLLM(LLMClient):
    """A tiny deterministic agent brain that needs no external services."""

    name = "rule-based"

    def decide(self, messages: List[Dict[str, str]], tools: Dict[str, Tool]) -> Decision:
        last = messages[-1] if messages else {"role": "user", "content": ""}

        # If we just ran a tool, summarize its result as the final answer.
        if last["role"] == "tool":
            return Decision(final_text=last["content"])

        text = last["content"].strip()
        lowered = text.lower()

        # Greetings / help.
        if lowered in {"hi", "hello", "hey"} or lowered.startswith(("hi ", "hello ", "hey ")):
            return Decision(final_text=self._greeting(tools))
        if "help" in lowered or "what can you do" in lowered:
            return Decision(final_text=self._greeting(tools))

        # Arithmetic: either a bare expression or "what is 2 + 2".
        expr = self._extract_math(text)
        if expr:
            return Decision(tool_calls=[{"name": "calculator", "arguments": {"expression": expr}}])

        # Time / date.
        if any(k in lowered for k in ("time", "date", "day is it", "what day")):
            tz = self._extract_timezone(text)
            args = {"timezone": tz} if tz else {}
            return Decision(tool_calls=[{"name": "current_time", "arguments": args}])

        # Reverse text.
        m = re.search(r"reverse(?:\s+(?:the\s+)?(?:text|string|word[s]?))?[:\s]+(.+)", text, re.I)
        if m:
            return Decision(
                tool_calls=[{"name": "reverse_text", "arguments": {"text": m.group(1).strip()}}]
            )

        # Text stats.
        m = re.search(r"(?:count|stats|how many words)[^:]*[:\s]+(.+)", text, re.I)
        if m:
            return Decision(
                tool_calls=[{"name": "text_stats", "arguments": {"text": m.group(1).strip()}}]
            )

        # Fallback: explain that this is the offline brain.
        return Decision(final_text=self._fallback(text, tools))

    def _extract_math(self, text: str) -> Optional[str]:
        candidate = text
        m = re.search(r"(?:what\s+is|calculate|compute|evaluate|=)\s*(.+)", text, re.I)
        if m:
            candidate = m.group(1)
        candidate = candidate.strip().rstrip("?.! ")
        candidate = candidate.replace("^", "**") if "^" in candidate else candidate
        check = candidate.replace("**", "")
        if check and _MATH_RE.match(check) and any(op in candidate for op in "+-*/%") :
            return candidate
        return None

    def _extract_timezone(self, text: str) -> Optional[str]:
        m = re.search(r"\bin\s+([A-Za-z]+/[A-Za-z_]+)", text)
        return m.group(1) if m else None

    def _greeting(self, tools: Dict[str, Tool]) -> str:
        names = ", ".join(sorted(tools))
        return (
            "Hi! I'm your agentic assistant. I'm running in offline demo mode "
            "(no LLM API key set), but I can already use real tools.\n\n"
            f"Available tools: {names}.\n\n"
            "Try: 'What is 23 * 19?', 'What time is it in America/New_York?', "
            "or 'reverse text: hello world'. Set OPENAI_API_KEY to unlock full "
            "natural-language reasoning with the same tools."
        )

    def _fallback(self, text: str, tools: Dict[str, Tool]) -> str:
        return (
            "I'm running in offline demo mode, so I handle a focused set of "
            "requests via built-in tools (math, time, text utilities). "
            "I didn't recognize a tool for that request. "
            "Set OPENAI_API_KEY to enable full LLM reasoning over the same tools. "
            "Type 'help' to see what I can do right now."
        )


# --------------------------------------------------------------------------
# OpenAI-backed brain
# --------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a helpful, concise agentic assistant for an AI startup. "
    "Use the provided tools when they help answer accurately. "
    "Prefer tools for arithmetic, current time, and text utilities."
)


class OpenAILLM(LLMClient):
    """Uses OpenAI chat completions with function-calling over the tools."""

    name = "openai"

    def __init__(self, model: Optional[str] = None) -> None:
        from openai import OpenAI  # imported lazily so the dep is optional

        self._client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def decide(self, messages: List[Dict[str, str]], tools: Dict[str, Tool]) -> Decision:
        payload = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages:
            if m["role"] == "tool":
                payload.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.get("tool_call_id", "call_0"),
                        "content": m["content"],
                    }
                )
            else:
                payload.append({"role": m["role"], "content": m["content"]})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=payload,
            tools=[t.to_openai_schema() for t in tools.values()],
            temperature=0.2,
        )
        choice = response.choices[0].message
        if choice.tool_calls:
            calls = []
            for tc in choice.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                calls.append({"name": tc.function.name, "arguments": args})
            return Decision(tool_calls=calls)
        return Decision(final_text=choice.content or "")


def get_llm() -> LLMClient:
    """Select the LLM backend based on environment configuration."""
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAILLM()
        except Exception:
            # Fall back gracefully if the SDK is missing or misconfigured.
            return RuleBasedLLM()
    return RuleBasedLLM()
