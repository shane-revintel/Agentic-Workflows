# Agentic-Workflows

A clean, working starter for building an **agentic AI product** from scratch —
tuned for an **inbound revenue motion**: turn inbound leads into booked
meetings into revenue.

It ships with a real agent architecture you can grow into a company:

- 🧠 **Agent loop** — the agent reasons, calls tools, feeds results back, and repeats until it has an answer.
- 🗣️ **Conversational SDR mode** — the agent reaches out to a lead, builds curiosity → interest, handles objections, and books a meeting (`propose_meeting_times`, `book_meeting`). Leads are modeled on Salesbot.io / Bowtie output (contact + "why they fit").
- 💸 **Inbound-revenue tools** — `score_lead`, `qualify_lead` (BANT), `forecast_revenue`, and `draft_email` cover the operational core of inbound → meeting → revenue.
- 🛠️ **Utility tools** — calculator, clock, and text utilities, all described with JSON schemas so an LLM can call them.
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

### Try the inbound-revenue tools

In offline mode, pass structured `key=value` arguments (with an LLM key you can
just type naturally and the model fills these in):

- `score lead: title=VP Marketing; company_size=800; source=demo_request; signal=viewed pricing 3x`
- `qualify: budget=yes; authority=yes; need=yes; timeline=no`
- `forecast: leads=200 meeting_rate=30% close_rate=25% acv=12000`
- `draft email: name=Sam; company=Acme; purpose=meeting_request; context=faster onboarding`

Utility examples: `What is 23 * 19?`, `What time is it in America/New_York?`.

### SDR outreach mode (converse a lead into a booked meeting)

In the web UI, switch to **SDR outreach**. The agent picks a lead (from
Salesbot.io / Bowtie — sample data by default), opens with a personalized
message, and you reply *as the prospect*. As soon as you show interest it
proposes times and books the meeting; bookings appear at `GET /api/bookings`.

Point it at your offer with these env vars (see `backend/.env`):

```bash
COMPANY_NAME="Your Company"
COMPANY_VALUE_PROP="one line describing what you do for customers"
SENDER_NAME="Alex"
```

Connect your real lead source by mapping Bowtie's export/API onto `Lead` in
`backend/app/leads.py` (guarded by `BOWTIE_API_KEY`). Connect a real calendar by
swapping the internals of `book_meeting` in `backend/app/booking.py`.

> **Plug in real data next:** the `score_lead`/`draft_email` tools are ready to be
> backed by live enrichment (e.g. ZoomInfo) and scheduling/CRM (e.g. Outlook)
> the same way the LLM backend plugs in — one function in `backend/app/revenue.py`.

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
