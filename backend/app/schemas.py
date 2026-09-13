"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's message to the agent.")
    history: List[ChatMessage] = Field(
        default_factory=list, description="Prior turns of the conversation."
    )
    mode: Literal["assistant", "sdr"] = Field(
        default="assistant",
        description="'assistant' for the general agent; 'sdr' for conversational outreach.",
    )
    lead_id: Optional[str] = Field(
        default=None, description="In SDR mode, which lead the agent is reaching out to."
    )


class ToolCall(BaseModel):
    name: str
    arguments: dict
    result: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls: List[ToolCall] = Field(default_factory=list)
    provider: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    tools: List[str]
    llm_configured: bool


class LeadModel(BaseModel):
    id: str
    name: str
    title: str
    company: str
    industry: str = ""
    email: str = ""
    source: str = ""
    fit_reason: str = ""
    fit_score: int = 0
    notes: str = ""
