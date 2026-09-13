# Agentic-Workflows

A clean, working starter for building an **agentic AI product** from scratch.

It ships with a real agent architecture you can grow into a company:

- 🧠 **Agent loop** — the agent reasons, calls tools, feeds results back, and repeats until it has an answer.
- 🛠️ **Tools** — pluggable capabilities (calculator, clock, text utilities) described with JSON schemas so an LLM can call them.
- 🔌 **Swappable LLM backend** — runs fully offline in demo mode with a deterministic "brain", and upgrades to a real model the moment you set `OPENAI_API_KEY`.
- 💬 **Web chat UI** — a modern single-page interface served straight from the backend.
- ✅ **Tests** — automated coverage for the agent, tools, and API.

You do **not** need any API keys to run this. Offline demo mode works out of the box; add a key later for full natural-language reasoning over the same tools.

---

## Project layout

```
Agentic-Workflows/
├── backend/
│   ├── app/
│   │   ├── main.py      # FastAPI app: /api/chat, /api/health, serves the UI
│   │   ├── agent.py     # The agent loop (reason → call tools → answer)
│   │   ├── llm.py       # LLM abstraction: rule-based (offline) + OpenAI
│   │   ├── tools.py     # Tool registry (calculator, time, text utils)
│   │   └── schemas.py   # Request/response models
│   ├── tests/           # pytest suite (no API keys required)
│   └── requirements.txt
├── frontend/            # index.html + styles.css + app.js chat UI
└── .cursor/environment.json
```

## Run it locally

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Start the server (serves API + web UI on http://localhost:8000)
cd backend
python3 -m uvicorn app.main:app --reload

# 3. Open http://localhost:8000 in your browser
```

Try: `What is 23 * 19?`, `What time is it in America/New_York?`, or `reverse text: agentic ai company`.

## Enable a real LLM

Set an OpenAI API key and the agent automatically switches from the offline
brain to real function-calling over the same tools:

```bash
export OPENAI_API_KEY=sk-...
# optional: export OPENAI_MODEL=gpt-4o-mini
```

## Run the tests

```bash
cd backend
python3 -m pytest
```

## How to extend it

- **Add a tool:** write a function in `backend/app/tools.py` and register it in
  `build_registry()`. It's immediately available to both the offline brain and
  the LLM.
- **Add an LLM provider:** implement a new `LLMClient` subclass in
  `backend/app/llm.py` and select it in `get_llm()`.
- **Add an endpoint:** extend `backend/app/main.py`.

This is your fresh canvas — build your agentic company on top of it.
