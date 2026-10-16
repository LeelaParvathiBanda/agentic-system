const listEl = document.getElementById("ticket-list");
const countEl = document.getElementById("ticket-count");
const form = document.getElementById("ticket-form");
const formTitle = document.getElementById("form-title");
const cancelEdit = document.getElementById("cancel-edit");
const toastEl = document.getElementById("toast");
const ticketIdInput = document.getElementById("ticket_id");

let editingId = null;
let tickets = [];

function toast(message) {
  toastEl.textContent = message;
  toastEl.classList.remove("hidden");
  window.clearTimeout(toastEl._timer);
  toastEl._timer = window.setTimeout(() => toastEl.classList.add("hidden"), 2800);
}

function money(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function statusClass(status, eligible) {
  const value = String(status || "").toLowerCase();
  if (value.includes("refund")) return "refund";
  if (value.includes("closed") || value.includes("resolved")) return "closed";
  if (!eligible) return "denied";
  return "";
}

function resetForm() {
  editingId = null;
  form.reset();
  ticketIdInput.disabled = false;
  document.getElementById("eligible_for_refund").checked = true;
  document.getElementById("status").value = "Open";
  formTitle.textContent = "Create ticket";
  cancelEdit.classList.add("hidden");
}

function fillForm(ticket) {
  editingId = ticket.ticket_id;
  ticketIdInput.value = ticket.ticket_id;
  ticketIdInput.disabled = true;
  document.getElementById("customer_name").value = ticket.customer_name;
  document.getElementById("customer_email").value = ticket.customer_email || "";
  document.getElementById("issue").value = ticket.issue;
  document.getElementById("purchase_amount").value = ticket.purchase_amount;
  document.getElementById("max_refund").value = ticket.max_refund;
  document.getElementById("status").value = ticket.status;
  document.getElementById("eligible_for_refund").checked = Boolean(ticket.eligible_for_refund);
  formTitle.textContent = `Edit ticket #${ticket.ticket_id}`;
  cancelEdit.classList.remove("hidden");
}

function renderTickets() {
  countEl.textContent = String(tickets.length);
  if (!tickets.length) {
    listEl.innerHTML = `<div class="empty">No tickets yet. Create one to test the agent.</div>`;
    return;
  }

  listEl.innerHTML = tickets.map((ticket) => `
    <article class="ticket-card">
      <div class="ticket-meta">
        <strong class="ticket-id">#${ticket.ticket_id}</strong>
        <span class="status ${statusClass(ticket.status, ticket.eligible_for_refund)}">${ticket.status}</span>
      </div>
      <p class="issue">${ticket.issue}</p>
      <p class="sub">${ticket.customer_name} · ${ticket.customer_email || "no email"} · ${money(ticket.purchase_amount)} · refund ${ticket.eligible_for_refund ? "up to " + money(ticket.max_refund) : "not eligible"}</p>
      <div class="card-actions">
        <button type="button" data-ask="${ticket.ticket_id}">Ask</button>
        <button type="button" data-edit="${ticket.ticket_id}">Edit</button>
        <button type="button" class="danger" data-delete="${ticket.ticket_id}">Delete</button>
      </div>
    </article>
  `).join("");
}

async function loadTickets() {
  const response = await fetch("/api/tickets");
  const data = await response.json();
  tickets = data.tickets || [];
  renderTickets();
}

function formPayload() {
  const maxRefund = document.getElementById("max_refund").value;
  return {
    ticket_id: ticketIdInput.value.trim() || null,
    customer_name: document.getElementById("customer_name").value.trim(),
    customer_email: document.getElementById("customer_email").value.trim(),
    issue: document.getElementById("issue").value.trim(),
    purchase_amount: Number(document.getElementById("purchase_amount").value || 0),
    max_refund: maxRefund === "" ? null : Number(maxRefund),
    status: document.getElementById("status").value,
    eligible_for_refund: document.getElementById("eligible_for_refund").checked,
  };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = formPayload();
  const url = editingId ? `/api/tickets/${editingId}` : "/api/tickets";
  const method = editingId ? "PUT" : "POST";
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    toast(data.detail || "Could not save ticket");
    return;
  }
  toast(editingId ? `Updated ticket #${data.ticket_id}` : `Created ticket #${data.ticket_id}`);
  resetForm();
  await loadTickets();
});

listEl.addEventListener("click", async (event) => {
  const askId = event.target.dataset.ask;
  const editId = event.target.dataset.edit;
  const deleteId = event.target.dataset.delete;
  if (askId) {
    document.getElementById("agent-message").value = `Look up ticket #${askId}`;
    document.getElementById("agent-message").focus();
    return;
  }
  if (editId) {
    const ticket = tickets.find((item) => item.ticket_id === editId);
    if (ticket) fillForm(ticket);
    return;
  }
  if (deleteId && window.confirm(`Delete ticket #${deleteId}?`)) {
    const response = await fetch(`/api/tickets/${deleteId}`, { method: "DELETE" });
    if (!response.ok) {
      const data = await response.json();
      toast(data.detail || "Could not delete ticket");
      return;
    }
    if (editingId === deleteId) resetForm();
    toast(`Deleted ticket #${deleteId}`);
    await loadTickets();
  }
});

document.getElementById("new-ticket").addEventListener("click", () => {
  resetForm();
  document.getElementById("customer_name").focus();
});
cancelEdit.addEventListener("click", resetForm);

const chatLog = document.getElementById("chat-log");
const agentInput = document.getElementById("agent-message");
const SESSION_KEY = "ticket-desk-chat";
let chatState = JSON.parse(window.localStorage.getItem(SESSION_KEY) || "null") || {
  sessionId: "",
  messages: [],
};

function saveChat() {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(chatState));
}

function renderEmptyChat() {
  chatLog.innerHTML = `<div class="chat-empty">Start with a ticket question, then keep asking follow-ups like “Is it eligible?” or “Refund $50.”</div>`;
}

function appendBubble(role, text, pending = false) {
  const empty = chatLog.querySelector(".chat-empty");
  if (empty) empty.remove();
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}${pending ? " pending" : ""}`;
  bubble.textContent = text;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

function restoreChat() {
  if (!chatState.messages.length) {
    renderEmptyChat();
    return;
  }
  chatLog.innerHTML = "";
  chatState.messages.forEach((item) => appendBubble(item.role, item.text));
}

restoreChat();

document.getElementById("new-chat").addEventListener("click", async () => {
  if (chatState.sessionId) {
    await fetch(`/api/support-agent/sessions/${chatState.sessionId}`, { method: "DELETE" }).catch(() => {});
  }
  chatState = { sessionId: "", messages: [] };
  saveChat();
  renderEmptyChat();
  agentInput.focus();
});

document.getElementById("agent-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = agentInput.value.trim();
  if (!message) return;
  agentInput.value = "";
  appendBubble("user", message);
  const pending = appendBubble("agent", "Thinking…", true);
  const sendBtn = event.target.querySelector("button[type='submit']");
  sendBtn.disabled = true;
  try {
    const response = await fetch("/api/support-agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: chatState.sessionId || null }),
    });
    const data = await response.json();
    if (data.session_id) chatState.sessionId = data.session_id;
    const reply = data.response || data.detail || "No response";
    pending.classList.remove("pending");
    pending.textContent = reply;
    chatState.messages.push({ role: "user", text: message }, { role: "agent", text: reply });
    saveChat();
    await loadTickets();
  } catch (error) {
    pending.classList.remove("pending");
    pending.textContent = "Could not reach the agent.";
  } finally {
    sendBtn.disabled = false;
    agentInput.focus();
  }
});

agentInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.getElementById("agent-form").requestSubmit();
  }
});

loadTickets().catch(() => toast("Could not load tickets"));
