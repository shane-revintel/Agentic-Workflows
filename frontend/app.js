const messagesEl = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

const state = {
  mode: "assistant",
  leads: [],
  leadId: null,
  history: [],
};

const SDR_PROSPECT_HINTS = [
  "Who is this?",
  "Not interested, thanks.",
  "What do you actually do?",
  "I'm pretty busy right now.",
  "How is this different from what we use?",
  "Ok, what times do you have?",
];

function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : text;
  return div.innerHTML;
}

function addMessage(role, text, toolCalls) {
  const wrap = el("div", `msg ${role}`);
  const avatar = el("div", "avatar", role === "user" ? "You" : "◆");
  const bubble = el("div", "bubble", escapeHtml(text));

  if (toolCalls && toolCalls.length) {
    const tools = el("div", "tools");
    toolCalls.forEach((tc) => {
      const args = Object.entries(tc.arguments || {})
        .filter(([, v]) => v !== "" && v !== null && v !== undefined)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      tools.appendChild(
        el(
          "div",
          "tool-chip",
          `<b>⚙ ${escapeHtml(tc.name)}</b>${args ? " · " + escapeHtml(args) : ""}`
        )
      );
    });
    bubble.appendChild(tools);
  }

  wrap.appendChild(avatar);
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap;
}

function addSystemNote(text) {
  const note = el("div", "system-note", escapeHtml(text));
  messagesEl.appendChild(note);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addTyping() {
  const wrap = el("div", "msg agent typing");
  wrap.appendChild(el("div", "avatar", "◆"));
  wrap.appendChild(
    el("div", "bubble", '<span class="dots"><span>●</span><span>●</span><span>●</span></span>')
  );
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap;
}

async function sendMessage(message, opts = {}) {
  const { hideUser = false } = opts;
  if (!hideUser) addMessage("user", message);
  const priorHistory = state.history.slice();
  state.history.push({ role: "user", content: message });
  input.value = "";
  sendBtn.disabled = true;
  const typing = addTyping();

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history: priorHistory,
        mode: state.mode,
        lead_id: state.leadId,
      }),
    });
    const data = await resp.json();
    typing.remove();
    if (!resp.ok) {
      addMessage("agent", `Error: ${data.detail || resp.statusText}`);
    } else {
      addMessage("agent", data.reply, data.tool_calls);
      state.history.push({ role: "assistant", content: data.reply });
      if ((data.tool_calls || []).some((tc) => tc.name === "book_meeting")) {
        addSystemNote("🎉 Meeting booked — captured in the pipeline.");
      }
    }
  } catch (err) {
    typing.remove();
    addMessage("agent", `Network error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (message) sendMessage(message);
});

// --- Mode + SDR wiring -----------------------------------------------------

function currentLead() {
  return state.leads.find((l) => l.id === state.leadId) || state.leads[0];
}

function renderLeadCard() {
  const lead = currentLead();
  const card = document.getElementById("lead-card");
  if (!lead) {
    card.innerHTML = "";
    return;
  }
  card.innerHTML = `
    <div class="lead-name">${escapeHtml(lead.name)}</div>
    <div class="lead-title">${escapeHtml(lead.title)} · ${escapeHtml(lead.company)}</div>
    <div class="lead-fit"><b>Why they fit:</b> ${escapeHtml(lead.fit_reason)}</div>
    <div class="lead-score">Fit score: ${lead.fit_score}/100</div>
  `;
}

function renderLeadList() {
  const list = document.getElementById("lead-list");
  list.innerHTML = "";
  state.leads.forEach((lead) => {
    const btn = el("button", "lead-chip" + (lead.id === state.leadId ? " active" : ""));
    btn.textContent = `${lead.name} — ${lead.company}`;
    btn.addEventListener("click", () => {
      state.leadId = lead.id;
      renderLeadList();
      renderLeadCard();
      startOutreach();
    });
    list.appendChild(btn);
  });
}

function renderSdrHints() {
  const box = document.getElementById("sdr-hints");
  box.innerHTML = "";
  SDR_PROSPECT_HINTS.forEach((msg) => {
    const btn = el("button", "hint", escapeHtml(msg));
    btn.addEventListener("click", () => sendMessage(msg));
    box.appendChild(btn);
  });
}

function startOutreach() {
  messagesEl.innerHTML = "";
  state.history = [];
  const lead = currentLead();
  if (lead) addSystemNote(`Reaching out to ${lead.name} at ${lead.company}…`);
  sendMessage(
    "(Start the outreach: send your opening message to this lead.)",
    { hideUser: true }
  );
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode);
  });
  document.getElementById("sdr-panel").classList.toggle("hidden", mode !== "sdr");
  document.getElementById("assistant-panel").classList.toggle("hidden", mode === "sdr");

  messagesEl.innerHTML = "";
  state.history = [];

  if (mode === "sdr") {
    input.placeholder = "Reply as the prospect…";
    if (state.leads.length && !state.leadId) state.leadId = state.leads[0].id;
    renderLeadList();
    renderLeadCard();
    renderSdrHints();
    startOutreach();
  } else {
    input.placeholder = "Ask your agent anything…";
    addMessage(
      "agent",
      "Welcome to your inbound-revenue agent. I can score and qualify leads, forecast revenue, and draft outreach — or switch to SDR outreach to watch me converse a lead into a booked meeting."
    );
  }
}

document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
});

document.getElementById("restart-outreach").addEventListener("click", startOutreach);

document.querySelectorAll("#assistant-panel .hint").forEach((btn) => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.msg));
});

// --- Boot ------------------------------------------------------------------

async function loadHealth() {
  const dot = document.getElementById("status-dot");
  try {
    const resp = await fetch("/api/health");
    const data = await resp.json();
    dot.textContent = "online";
    dot.className = "dot dot-ok";
    document.getElementById("provider").textContent = data.provider;
    document.getElementById("tool-count").textContent = `${data.tools.length} available`;
  } catch (err) {
    dot.textContent = "offline";
    dot.className = "dot dot-bad";
  }
}

async function loadLeads() {
  try {
    const resp = await fetch("/api/leads");
    state.leads = await resp.json();
    if (state.leads.length) state.leadId = state.leads[0].id;
  } catch (err) {
    state.leads = [];
  }
}

(async function init() {
  await Promise.all([loadHealth(), loadLeads()]);
  setMode("assistant");
})();
