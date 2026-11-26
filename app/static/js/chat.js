const box = document.getElementById('messages');
const input = document.getElementById('chatInput');
const form = document.getElementById('chatForm');
const chatCsrf = document.querySelector('meta[name="csrf-token"]')?.content;

const seenIds = new Set();
document.querySelectorAll('#messages [data-msg-id]').forEach((el) => {
  const id = Number(el.dataset.msgId);
  if (id) seenIds.add(id);
});
let lastId = Number(window.lastMessageId || 0);
box.scrollTop = box.scrollHeight;

function appendMessage(m) {
  if (!m || !m.id || seenIds.has(m.id)) return;
  seenIds.add(m.id);
  if (m.id > lastId) lastId = m.id;
  const el = document.createElement('div');
  el.className = 'chat-bubble ' + (m.sender_id === window.currentUserId ? 'mine' : '');
  el.dataset.msgId = String(m.id);
  const name = document.createElement('small');
  name.textContent = `${m.sender} · ${new Date(m.created_at).toLocaleString()}`;
  const p = document.createElement('p');
  p.textContent = m.body;
  el.append(name, p);
  box.append(el);
  box.scrollTop = box.scrollHeight;
}

async function pollMessages() {
  try {
    const res = await fetch(`/api/conversations/${window.conversationId}/messages?after=${lastId}`, {
      credentials: 'same-origin',
    });
    if (!res.ok) return;
    const data = await res.json();
    (data.messages || []).forEach(appendMessage);
  } catch {
    // Ignore transient network errors during background polling.
  }
}

setInterval(pollMessages, 2000);

let socket = null;
if (typeof io === 'function') {
  try {
    socket = io({ transports: ['websocket', 'polling'], reconnectionAttempts: 2 });
    socket.on('connect', () => {
      socket.emit('join', { conversation_id: window.conversationId });
    });
    socket.on('message', appendMessage);
  } catch {
    socket = null;
  }
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = input.value.trim();
  if (!body) return;
  const submitBtn = form.querySelector('button[type="submit"], button');
  if (submitBtn) submitBtn.disabled = true;
  try {
    const res = await fetch(`/api/conversations/${window.conversationId}/messages`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': chatCsrf || '',
      },
      body: JSON.stringify({ body }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Could not send message.');
    }
    appendMessage(data);
    input.value = '';
    input.focus();
  } catch (err) {
    if (typeof toast === 'function') {
      toast(err.message || 'Could not send message.');
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
});
