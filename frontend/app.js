/* ecoSeek Kids v2.0 — Scientific Agent with GBIF + References */

const API_BASE = window.location.origin.includes('kids.ecoseek.org')
  ? 'https://kids.ecoseek.org/api'
  : '/api';

// Markdown renderer
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

// ecoSeek Kids scientific topics
const TOPIC_PROMPTS = {
  ecologia: `Eres ecoSeek Kids, la version infantil del asistente cientifico ecoSeek.
Especialidad: ECOLOGIA y MEDIO AMBIENTE para jovenes de 8-18 anos.
- Explica ecosistemas, cadenas alimenticias, biodiversidad, cambio climatico
- Usa ejemplos observables en la naturaleza
- Si tienes datos de GBIF, incluyelos en tu respuesta
- Cita referencias cientificas cuando esten disponibles`,

  animales: `Eres ecoSeek Kids, la version infantil del asistente cientifico ecoSeek.
Especialidad: ZOOLOGIA y VIDA ANIMAL para jovenes de 8-18 anos.
- Explica clasificacion, habitats, adaptaciones, cadena trofica
- Cuando menciones una especie, incluye datos de GBIF si estan disponibles
- Clasifica: mamiferos, aves, reptiles, anfibios, peces, invertebrados
- Cita referencias cientificas`,

  plantas: `Eres ecoSeek Kids, la version infantil del asistente cientifico ecoSeek.
Especialidad: BOTANICA y REINO VEGETAL para jovenes de 8-18 anos.
- Explica fotosintesis, partes de la planta, tipos, polinizacion
- Sugiere experimentos simples para hacer en casa
- Relaciona las plantas con el aire y la alimentacion`,

  tierra: `Eres ecoSeek Kids, la version infantil del asistente cientifico ecoSeek.
Especialidad: CIENCIAS DE LA TIERRA para jovenes de 8-18 anos.
- Explica volcanes, terremotos, ciclo del agua, rocas, clima
- Usa analogias: "La Tierra tiene capas como una cebolla"
- Explica fenomenos naturales de forma fascinante`,

  espacio: `Eres ecoSeek Kids, la version infantil del asistente cientifico ecoSeek.
Especialidad: ASTRONOMIA para jovenes de 8-18 anos.
- Explica sistema solar, estrellas, lunas, planetas
- Usa datos que asombren
- Inspira curiosidad por el universo`,

  cuerpo: `Eres ecoSeek Kids, la version infantil del asistente cientifico ecoSeek.
Especialidad: BIOLOGIA HUMANA para jovenes de 8-18 anos.
- Explica sistemas del cuerpo con analogias
- Relaciona con habitos saludables
- Responde preguntas curiosas`
};

// DOM
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

// Add message with optional data panels
function addMessage(role, content, data = null) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);
  div.appendChild(bubble);

  // Add GBIF data panel if species data was used
  if (data && data.enriched) {
    const panel = document.createElement('div');
    panel.className = 'data-panel';
    panel.innerHTML = `
      <div class="data-panel-header">🔬 Datos científicos incluidos</div>
      <div class="data-panel-body">Esta respuesta incluye datos reales de GBIF y referencias de CrossRef.</div>
    `;
    div.appendChild(panel);
  }

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = 'typing-indicator';
  div.innerHTML = `<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
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
    const topicPrompt = TOPIC_PROMPTS[currentTopic] || TOPIC_PROMPTS.ecologia;

    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        system: topicPrompt,
        history: conversationHistory.slice(-10),
        kid_mode: true
      })
    });

    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    const reply = data.response || 'No pude generar una respuesta.';

    hideTyping();
    addMessage('assistant', reply, { enriched: data.enriched });
    conversationHistory.push({ role: 'assistant', content: reply });

  } catch (err) {
    hideTyping();
    addMessage('assistant', 'Ups, algo salio mal. Intenta de nuevo!');
  }

  isGenerating = false;
  sendBtn.disabled = false;
  chatInput.focus();
}

// Quick actions
async function searchSpecies(query) {
  const res = await fetch(`${API_BASE}/species`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit: 5 })
  });
  return res.json();
}

async function getReferences(query) {
  const res = await fetch(`${API_BASE}/references`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit: 5 })
  });
  return res.json();
}

async function getOccurrences(species) {
  const res = await fetch(`${API_BASE}/occurrences`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ species, limit: 300 })
  });
  return res.json();
}

function startWithTopic(topic) {
  currentTopic = topic;
  conversationHistory = [];
  chatMessages.innerHTML = '';

  const greetings = {
    ecologia: '¡Hola explorador! 🌍 Soy tu guía de **Ecología**. Puedo buscar datos reales de especies en GBIF, encontrar referencias científicas, y ayudarte con tu reporte.\n\n¿Qué tema te interesa?',
    animales: '¡Hola! 🦁 Soy tu guía del reino **Animal**. Si mencionas un animal, buscaré sus datos en GBIF automáticamente — distribución, registros, clasificación.\n\n¿Qué animal quieres investigar?',
    plantas: '¡Hola! 🌱 Soy tu guía del mundo **Vegetal**. Puedo buscar datos de plantas en GBIF y referencias botánicas.\n\n¿Qué planta te interesa?',
    tierra: '¡Hola! 🌋 Soy tu guía de la **Tierra**. Volcanes, terremotos, clima — con datos científicos reales.\n\n¿Qué fenómeno quieres explorar?',
    espacio: '¡Hola! 🔭 Soy tu guía del **Espacio**. Planetas, estrellas, el universo.\n\n¿Qué quieres descubrir?',
    cuerpo: '¡Hola! 🫀 Soy tu guía del **Cuerpo Humano**. Con referencias de biología y medicina.\n\n¿Qué parte del cuerpo te interesa?'
  };

  addMessage('assistant', greetings[topic] || greetings.ecologia);
  showScreen(chatScreen);
  chatInput.focus();
}

function startWithText(text) {
  currentTopic = currentTopic || 'ecologia';
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
