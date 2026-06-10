/* ecoSeek Kids v2.1 — Scientific Agent with i18n + GBIF */

const API_BASE = window.location.origin.includes('kids.ecoseek.org')
  ? 'https://kids.ecoseek.org/api'
  : '/api';

function renderMarkdown(text) {
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
    .replace(/<\/ul>\s*<ul>/g, '')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

const welcomeScreen = document.getElementById('welcome-screen');
const chatScreen = document.getElementById('chat-screen');
const startInput = document.getElementById('start-input');
const startBtn = document.getElementById('start-btn');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const backBtn = document.getElementById('back-btn');
const newChatBtn = document.getElementById('new-chat-btn');

let currentTopic = null;
let conversationHistory = [];
let isGenerating = false;

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function showScreen(screen) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  screen.classList.add('active');
}

function addMessage(role, content, data = null) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);
  div.appendChild(bubble);

  if (data && data.enriched) {
    const panel = document.createElement('div');
    panel.className = 'data-panel';
    panel.innerHTML = `
      <div class="data-panel-header">${t('data_included')}</div>
      <div class="data-panel-body">${t('data_desc')}</div>
    `;
    div.appendChild(panel);
  }

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = 'typing-indicator';
  div.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

async function sendMessage(text) {
  if (isGenerating || !text.trim()) return;
  isGenerating = true;
  sendBtn.disabled = true;

  addMessage('user', text);
  conversationHistory.push({ role: 'user', content: text });
  showTyping();

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        system: '',
        history: conversationHistory.slice(-10),
        kid_mode: true,
        language: currentLang
      })
    });

    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    const reply = data.response || 'Error.';

    hideTyping();
    addMessage('assistant', reply, { enriched: data.enriched });
    conversationHistory.push({ role: 'assistant', content: reply });

  } catch (err) {
    hideTyping();
    addMessage('assistant', 'Something went wrong. Try again!');
  }

  isGenerating = false;
  sendBtn.disabled = false;
  chatInput.focus();
}

function startWithTopic(topic) {
  currentTopic = topic;
  conversationHistory = [];
  chatMessages.innerHTML = '';

  const greetingKey = `greetings.${topic}`;
  const greeting = t(greetingKey);
  addMessage('assistant', greeting !== greetingKey ? greeting : t('greetings.ecology'));
  showScreen(chatScreen);
  chatInput.focus();
}

function startWithText(text) {
  currentTopic = currentTopic || 'ecology';
  conversationHistory = [];
  chatMessages.innerHTML = '';
  showScreen(chatScreen);
  sendMessage(text);
}

// Events
document.querySelectorAll('.topic-card').forEach(card => {
  card.addEventListener('click', () => startWithTopic(card.dataset.topic));
});

startBtn.addEventListener('click', () => {
  const text = startInput.value.trim();
  if (text) startWithText(text);
});

startInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); startBtn.click(); }
});

sendBtn.addEventListener('click', () => {
  const text = chatInput.value.trim();
  if (text) { chatInput.value = ''; autoResize(chatInput); sendMessage(text); }
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendBtn.click(); }
});

chatInput.addEventListener('input', () => autoResize(chatInput));
backBtn.addEventListener('click', () => showScreen(welcomeScreen));
newChatBtn.addEventListener('click', () => {
  conversationHistory = [];
  chatMessages.innerHTML = '';
  showScreen(welcomeScreen);
  startInput.value = '';
});

window.addEventListener('load', () => startInput.focus());
