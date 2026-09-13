"""FastAPI application: agent API + static web UI."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent
from .booking import list_bookings
from .leads import get_lead, import_leads_from_csv, list_leads
from .llm import RuleBasedLLM, get_llm
from .schemas import ChatRequest, ChatResponse, HealthResponse, LeadModel, ToolCall
from .sdr import SDR_TOOLS, build_sdr_system_prompt
from .tools import REGISTRY

logger = logging.getLogger("agentic")


def _friendly_llm_error(exc: Exception) -> str:
    """Map an LLM failure to a clear, user-facing explanation."""
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if any(k in name for k in ("auth",)) or any(
        k in text for k in ("invalid_api_key", "incorrect api key", "401", "unauthorized")
    ):
        return (
            "⚠️ I couldn't reach the AI model — the OpenAI API key looks invalid or "
            "expired. Update OPENAI_API_KEY (or remove it to use offline mode). "
            "I've answered in offline mode below."
        )
    if "ratelimit" in name or any(
        k in text for k in ("insufficient_quota", "quota", "429", "rate limit")
    ):
        return (
            "⚠️ The AI model is rate-limited or out of quota. Check your OpenAI "
            "plan/billing, then try again. I've answered in offline mode below."
        )
    return (
        "⚠️ The AI model had a temporary problem, so I switched to offline mode for "
        "this reply. Please try again in a moment."
    )

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
    history = [{"role": m.role, "content": m.content} for m in request.history]

    system_prompt = None
    if request.mode == "sdr":
        lead = get_lead(request.lead_id)
        system_prompt = build_sdr_system_prompt(lead)

    try:
        agent = Agent(system_prompt=system_prompt)
        result = agent.run(request.message, history=history)
        return ChatResponse(
            reply=result.reply,
            tool_calls=[ToolCall(**tc) for tc in result.tool_calls],
            provider=result.provider,
        )
    except Exception as exc:  # noqa: BLE001 - never surface a raw 500 to the chat UI
        logger.warning("Primary agent failed (%s): %s", type(exc).__name__, exc)
        note = _friendly_llm_error(exc)
        # Graceful fallback: answer with the offline brain so the app stays usable
        # even when the LLM (e.g. invalid key, quota, timeout) is unavailable.
        try:
            fallback = Agent(llm=RuleBasedLLM(), system_prompt=system_prompt)
            fb = fallback.run(request.message, history=history)
            reply = f"{note}\n\n{fb.reply}" if fb.reply else note
            return ChatResponse(
                reply=reply,
                tool_calls=[ToolCall(**tc) for tc in fb.tool_calls],
                provider="rule-based (fallback)",
            )
        except Exception as inner:  # noqa: BLE001
            logger.error("Fallback agent also failed: %s", inner)
            return ChatResponse(reply=note, tool_calls=[], provider="error")


@app.get("/api/leads", response_model=list[LeadModel])
def leads() -> list[LeadModel]:
    return [LeadModel(**lead.as_dict()) for lead in list_leads()]


@app.post("/api/leads/import")
async def import_leads(request: Request) -> dict:
    """Import leads from a raw CSV body (e.g. a Salesbot.io / Bowtie export)."""
    raw = (await request.body()).decode("utf-8-sig", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Empty CSV upload.")
    try:
        leads_list = import_leads_from_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "imported": len(leads_list),
        "source": "imported",
        "leads": [LeadModel(**lead.as_dict()).model_dump() for lead in leads_list],
    }


@app.get("/api/bookings")
def bookings() -> list[dict]:
    return list_bookings()


if FRONTEND_DIR.exists():
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
