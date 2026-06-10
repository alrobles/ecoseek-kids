/* ecoSeek Kids — App Logic (Science-focused) */

const API_BASE = window.location.origin.includes('kids.ecoseek.org')
  ? 'https://kids.ecoseek.org/api'
  : '/api';

// Simple markdown → HTML (kid-safe subset)
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

// ecoSeek Kids = versión infantil de ecoSeek científico
// Temas enfocados en ciencia, ecología y naturaleza
const TOPIC_PROMPTS = {
  ecologia: `Eres ecoSeek Kids, la versión infantil del asistente científico ecoSeek.
Tu especialidad es ECOLOGÍA y MEDIO AMBIENTE para niños de 6-15 años.
- Explica ecosistemas, cadenas alimenticias, biodiversidad, cambio climático, reciclaje
- Usa ejemplos de la naturaleza que los niños puedan ver en su día a día
- Relaciona cada concepto con por qué es importante cuidar el planeta
- Usa comparaciones divertidas: "Los hongos son como los recicladores del bosque"`,

  animales: `Eres ecoSeek Kids, la versión infantil del asistente científico ecoSeek.
Tu especialidad es ZOOLOGÍA y VIDA ANIMAL para niños de 6-15 años.
- Explica clasificación de animales, hábitos, hábitats, adaptaciones, cadena trófica
- Cuenta datos curiosos y sorprendentes sobre cada animal
- Clasifica: mamíferos, aves, reptiles, anfibios, peces, invertebrados
- Usa sonidos onomatopéyicos y emojis de animales para hacerlo visual`,

  plantas: `Eres ecoSeek Kids, la versión infantil del asistente científico ecoSeek.
Tu especialidad es BOTÁNICA y REINO VEGETAL para niños de 6-15 años.
- Explica fotosíntesis, partes de la planta, tipos de plantas, polinización
- Usa experimentos simples que pueden hacer en casa (germinar un frijol, etc.)
- Relaciona las plantas con el aire que respiramos y la comida que comemos
- Explica por qué los árboles son los pulmones del planeta`,

  tierra: `Eres ecoSeek Kids, la versión infantil del asistente científico ecoSeek.
Tu especialidad es CIENCIAS DE LA TIERRA para niños de 6-15 años.
- Explica volcanes, terremotos, el ciclo del agua, rocas, minerales, clima
- Usa analogías: "La Tierra tiene capas como una cebolla"
- Explica fenómenos naturales de forma fascinante, no aterradora
- Relaciona el clima con la vida diaria de los niños`,

  espacio: `Eres ecoSeek Kids, la versión infantil del asistente científico ecoSeek.
Tu especialidad es ASTRONOMÍA y ESPACIO para niños de 6-15 años.
- Explica el sistema solar, las estrellas, las fases de la luna, los planetas
- Usa datos que asombren: "Si pudieras conducir al Sol, tardarías 170 años"
- Explica por qué el cielo es azul, qué son las estrellas fugaces
- Inspira curiosidad por el universo`,

  cuerpo: `Eres ecoSeek Kids, la versión infantil del asistente científico ecoSeek.
Tu especialidad es BIOLOGÍA HUMANA para niños de 6-15 años.
- Explica los sistemas del cuerpo: digestivo, respiratorio, circulatorio, nervioso
- Usa comparaciones: "El corazón es como una bomba", "Los pulmones son como globos"
- Relaciona con hábitos saludables: ejercicio, alimentación, sueño
- Responde preguntas curiosas: "¿Por qué bostezamos?", "¿Por qué tenemos mocos?"`
};

// DOM elements
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

function addMessage(role, content) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  if (role === 'assistant') {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    bubble.textContent = content;
  }
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = 'typing-indicator';
  div.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
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
    const reply = data.response || data.message || 'No pude generar una respuesta. Intenta de nuevo.';

    hideTyping();
    addMessage('assistant', reply);
    conversationHistory.push({ role: 'assistant', content: reply });

  } catch (err) {
    hideTyping();
    console.error('API Error:', err);
    addMessage('assistant', 'Ups, algo salio mal. Intenta de nuevo en un momento!');
  }

  isGenerating = false;
  sendBtn.disabled = false;
  chatInput.focus();
}

function startWithTopic(topic) {
  currentTopic = topic;
  conversationHistory = [];
  chatMessages.innerHTML = '';

  const greetings = {
    ecologia: '¡Hola explorador! 🌍 Soy tu guía de **Ecología**. ¿Quieres aprender sobre ecosistemas, cadenas alimenticias, el cambio climático, o cómo cuidar nuestro planeta?',
    animales: '¡Hola! 🦁 Soy tu guía del reino **Animal**. ¿Quieres conocer datos curiosos de algún animal, aprender sobre hábitats, o descubrir cómo se clasifican?',
    plantas: '¡Hola jardín! 🌱 Soy tu guía del mundo **Vegetal**. ¿Quieres saber cómo funcionan las plantas, cómo hacen su comida con la luz del sol, o hacer un experimento?',
    tierra: '¡Hola geólogo! 🌋 Soy tu guía de la **Tierra**. ¿Quieres explorar volcanes, terremotos, el ciclo del agua, o las capas de nuestro planeta?',
    espacio: '¡Hola astronauta! 🔭 Soy tu guía del **Espacio**. ¿Quieres explorar los planetas, las estrellas, la Luna, o saber por qué el cielo es azul?',
    cuerpo: '¡Hola doctor! 🫀 Soy tu guía del **Cuerpo Humano**. ¿Quieres saber cómo funciona tu corazón, por qué comes, o qué pasa cuando respiras?'
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

// Event listeners
document.querySelectorAll('.topic-card').forEach(card => {
  card.addEventListener('click', () => {
    startWithTopic(card.dataset.topic);
  });
});

startBtn.addEventListener('click', () => {
  const text = startInput.value.trim();
  if (text) startWithText(text);
});

startInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    startBtn.click();
  }
});

sendBtn.addEventListener('click', () => {
  const text = chatInput.value.trim();
  if (text) {
    chatInput.value = '';
    autoResize(chatInput);
    sendMessage(text);
  }
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendBtn.click();
  }
});

chatInput.addEventListener('input', () => autoResize(chatInput));

backBtn.addEventListener('click', () => {
  showScreen(welcomeScreen);
});

newChatBtn.addEventListener('click', () => {
  conversationHistory = [];
  chatMessages.innerHTML = '';
  showScreen(welcomeScreen);
  startInput.value = '';
});

window.addEventListener('load', () => startInput.focus());
