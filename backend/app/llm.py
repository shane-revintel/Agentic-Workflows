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

    def decide(
        self,
        messages: List[Dict[str, str]],
        tools: Dict[str, Tool],
        system_prompt: Optional[str] = None,
    ) -> Decision:
        raise NotImplementedError


# --------------------------------------------------------------------------
# Rule-based, offline brain
# --------------------------------------------------------------------------

_MATH_RE = re.compile(r"^[\d\s().+\-*/%^]+$")


class RuleBasedLLM(LLMClient):
    """A tiny deterministic agent brain that needs no external services."""

    name = "rule-based"

    def decide(
        self,
        messages: List[Dict[str, str]],
        tools: Dict[str, Tool],
        system_prompt: Optional[str] = None,
    ) -> Decision:
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

        # Inbound-revenue intents (offline mode uses key=value arguments).
        revenue_decision = self._route_revenue(text, lowered)
        if revenue_decision is not None:
            return revenue_decision

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

    def _parse_kv(self, text: str) -> Dict[str, str]:
        """Parse 'key=value' pairs; values run until the next 'key=' or ';'."""
        pairs: Dict[str, str] = {}
        for m in re.finditer(r"(\w+)\s*=\s*([^;]+?)(?=\s+\w+\s*=|;|$)", text):
            pairs[m.group(1).strip().lower()] = m.group(2).strip()
        return pairs

    def _route_revenue(self, text: str, lowered: str) -> Optional[Decision]:
        kv = self._parse_kv(text)

        if lowered.startswith("score") and ("lead" in lowered or "title" in kv):
            return Decision(
                tool_calls=[{"name": "score_lead", "arguments": {
                    "title": kv.get("title", ""),
                    "company_size": kv.get("company_size", kv.get("size", "")),
                    "source": kv.get("source", ""),
                    "signal": kv.get("signal", ""),
                }}]
            )

        if lowered.startswith("qualify") or (kv and "budget" in kv):
            return Decision(
                tool_calls=[{"name": "qualify_lead", "arguments": {
                    "budget": kv.get("budget", ""),
                    "authority": kv.get("authority", ""),
                    "need": kv.get("need", ""),
                    "timeline": kv.get("timeline", ""),
                }}]
            )

        if lowered.startswith("forecast") or "revenue" in lowered or "leads" in kv:
            return Decision(
                tool_calls=[{"name": "forecast_revenue", "arguments": {
                    "leads": kv.get("leads", ""),
                    "meeting_rate": kv.get("meeting_rate", kv.get("meeting", "")),
                    "close_rate": kv.get("close_rate", kv.get("close", "")),
                    "acv": kv.get("acv", kv.get("deal", "")),
                }}]
            )

        if ("draft" in lowered and "email" in lowered) or lowered.startswith(("email", "outreach")):
            return Decision(
                tool_calls=[{"name": "draft_email", "arguments": {
                    "name": kv.get("name", ""),
                    "company": kv.get("company", "your team"),
                    "purpose": kv.get("purpose", "meeting_request"),
                    "context": kv.get("context", "your goals"),
                }}]
            )

        if "when" in kv or lowered.startswith(("book meeting", "book:")):
            return Decision(
                tool_calls=[{"name": "book_meeting", "arguments": {
                    "name": kv.get("name", ""),
                    "when": kv.get("when", ""),
                    "email": kv.get("email", ""),
                    "topic": kv.get("topic", "intro call"),
                }}]
            )

        if lowered.startswith("propose") or "meeting times" in lowered or "propose times" in lowered:
            return Decision(
                tool_calls=[{"name": "propose_meeting_times", "arguments": {
                    "timezone": kv.get("timezone", "UTC"),
                }}]
            )

        return None

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
            "Hi! I'm your inbound-revenue agent. I'm running in offline demo mode "
            "(no LLM API key set), but I can already use real tools to move a lead "
            "from inbound → booked meeting → revenue.\n\n"
            f"Available tools: {names}.\n\n"
            "Try these (offline mode uses key=value):\n"
            "  • score lead: title=VP Marketing; company_size=800; source=demo_request; signal=viewed pricing 3x\n"
            "  • qualify: budget=yes; authority=yes; need=yes; timeline=no\n"
            "  • forecast: leads=200 meeting_rate=30% close_rate=25% acv=12000\n"
            "  • draft email: name=Sam; company=Acme; purpose=meeting_request; context=faster onboarding\n\n"
            "Set OPENAI_API_KEY to just type naturally — the LLM fills these in for you."
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


_OPENAI_MAX_STEPS = 5


class OpenAILLM(LLMClient):
    """Uses OpenAI chat completions with function-calling over the tools.

    This backend runs the full reason → call tools → answer loop internally so
    the provider-native message protocol (assistant tool_calls + matching tool
    results by id) stays correct, then returns the final answer plus the tool
    calls it executed for reporting.
    """

    name = "openai"

    def __init__(self, model: Optional[str] = None) -> None:
        from openai import OpenAI  # imported lazily so the dep is optional

        self._client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def decide(
        self,
        messages: List[Dict[str, str]],
        tools: Dict[str, Tool],
        system_prompt: Optional[str] = None,
    ) -> Decision:
        convo: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT}
        ]
        for m in messages:
            # Only user/assistant turns reach here; this backend owns tool turns.
            if m["role"] in ("user", "assistant"):
                convo.append({"role": m["role"], "content": m["content"]})

        executed: List[Dict[str, Any]] = []
        schemas = [t.to_openai_schema() for t in tools.values()]

        for _ in range(_OPENAI_MAX_STEPS):
            response = self._client.chat.completions.create(
                model=self.model,
                messages=convo,
                tools=schemas,
                temperature=0.2,
            )
            choice = response.choices[0].message

            if not choice.tool_calls:
                return Decision(final_text=choice.content or "", tool_calls=executed)

            convo.append(
                {
                    "role": "assistant",
                    "content": choice.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in choice.tool_calls
                    ],
                }
            )

            for tc in choice.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._run_tool(tools, tc.function.name, args)
                executed.append({"name": tc.function.name, "arguments": args, "result": result})
                convo.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        return Decision(
            final_text="I wasn't able to finish that within the step limit.",
            tool_calls=executed,
        )

    @staticmethod
    def _run_tool(tools: Dict[str, Tool], name: str, args: Dict[str, Any]) -> str:
        tool = tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            return tool.func(**args)
        except Exception as exc:  # noqa: BLE001 - surface tool errors back to the model
            return f"Tool {name} failed: {exc}"


def get_llm() -> LLMClient:
    """Select the LLM backend based on environment configuration."""
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAILLM()
        except Exception:
            # Fall back gracefully if the SDK is missing or misconfigured.
            return RuleBasedLLM()
    return RuleBasedLLM()
