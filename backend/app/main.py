"""FastAPI application: agent API + static web UI."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent
from .llm import get_llm
from .schemas import ChatRequest, ChatResponse, HealthResponse, ToolCall
from .tools import REGISTRY

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(
    title="Agentic Workflows API",
    description="A starter agentic AI backend with a tool-calling agent loop.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    llm = get_llm()
    return HealthResponse(
        status="ok",
        provider=llm.name,
        tools=sorted(REGISTRY.keys()),
        llm_configured=bool(os.getenv("OPENAI_API_KEY")),
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    agent = Agent()
    history = [{"role": m.role, "content": m.content} for m in request.history]
    result = agent.run(request.message, history=history)
    return ChatResponse(
        reply=result.reply,
        tool_calls=[ToolCall(**tc) for tc in result.tool_calls],
        provider=result.provider,
    )


if FRONTEND_DIR.exists():
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
