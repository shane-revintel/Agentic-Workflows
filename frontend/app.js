const messagesEl = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

const history = [];

function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
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

async function sendMessage(message) {
  addMessage("user", message);
  history.push({ role: "user", content: message });
  input.value = "";
  sendBtn.disabled = true;
  const typing = addTyping();

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: history.slice(0, -1) }),
    });
    const data = await resp.json();
    typing.remove();
    if (!resp.ok) {
      addMessage("agent", `Error: ${data.detail || resp.statusText}`);
    } else {
      addMessage("agent", data.reply, data.tool_calls);
      history.push({ role: "assistant", content: data.reply });
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

document.querySelectorAll(".hint").forEach((btn) => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.msg));
});

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

addMessage(
  "agent",
  "Welcome to your inbound-revenue agent. I can score and qualify inbound leads, draft the outreach that books the meeting, and forecast the revenue those meetings produce — with a real tool-calling loop. Try the buttons on the left, or type 'help'."
);
loadHealth();
