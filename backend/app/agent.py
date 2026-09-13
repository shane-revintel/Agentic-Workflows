"""The agent loop.

An agent takes a conversation, asks the LLM what to do, executes any requested
tools, feeds the results back, and repeats until the LLM produces a final
answer (or a safety limit is reached).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .llm import Decision, LLMClient, get_llm
from .tools import REGISTRY, Tool

MAX_STEPS = 5


@dataclass
class AgentResult:
    reply: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    provider: str = "rule-based"


class Agent:
    def __init__(self, llm: LLMClient | None = None, tools: Dict[str, Tool] | None = None) -> None:
        self.llm = llm or get_llm()
        self.tools = tools or REGISTRY

    def run(self, message: str, history: List[Dict[str, str]] | None = None) -> AgentResult:
        messages: List[Dict[str, str]] = list(history or [])
        messages.append({"role": "user", "content": message})

        executed: List[Dict[str, Any]] = []

        for _ in range(MAX_STEPS):
            decision: Decision = self.llm.decide(messages, self.tools)

            if decision.tool_calls:
                for call in decision.tool_calls:
                    result = self._execute_tool(call["name"], call.get("arguments", {}))
                    executed.append(
                        {"name": call["name"], "arguments": call.get("arguments", {}), "result": result}
                    )
                    messages.append({"role": "tool", "content": result})
                continue

            return AgentResult(
                reply=decision.final_text or "",
                tool_calls=executed,
                provider=self.llm.name,
            )

        # Safety valve: summarize whatever tool output we have.
        fallback = executed[-1]["result"] if executed else "I couldn't complete that request."
        return AgentResult(reply=fallback, tool_calls=executed, provider=self.llm.name)

    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            return tool.func(**arguments)
        except TypeError as exc:
            return f"Invalid arguments for {name}: {exc}"
        except Exception as exc:  # noqa: BLE001 - surface tool errors to the agent
            return f"Tool {name} failed: {exc}"
