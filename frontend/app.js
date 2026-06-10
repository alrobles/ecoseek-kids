/* ecoSeek Kids — App Logic */

const API_BASE = window.location.origin.includes('kids.ecoseek.org')
  ? 'https://kids.ecoseek.org/api'
  : '/api';

// Simple markdown → HTML (kid-safe subset)
function renderMarkdown(text) {
  return text
    // Code blocks
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold & italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Blockquote
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    // Unordered list
    .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
    // Ordered list
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
    .replace(/<\/ul>\s*<ul>/g, '')
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

// Topic prompts (system instructions for kid-friendly responses)
const TOPIC_PROMPTS = {
  matematicas: 'Eres un tutor amigable de matemáticas para niños. Explica paso a paso con ejemplos simples. Usa analogías cotidianas. Si hay una fórmula, muestra primero el ejemplo y después la regla. Anima al estudiante.',
  ciencias: 'Eres un profesor de ciencias para niños. Usa comparaciones con cosas del día a día. Explica conceptos complejos con palabras simples y ejemplos divertidos. Usa emojis para hacer la explicación más visual.',
  historia: 'Eres un narrador de historias para niños. Cuenta los hechos históricos como una historia interesante, con personajes y eventos. Haz que sea emocional y memorable, no una lista de fechas.',
  espanol: 'Eres un tutor de español/Lengua para niños. Explica gramática y ortografía con reglas claras y trucos fáciles de recordar. Da ejemplos correctos e incorrectos. Sé paciente y alentador.',
  ingles: 'Eres un profesor de inglés para niños hispanohablantes. Explica vocabulario y gramática con asociaciones fáciles. Da la traducción y un ejemplo de uso. Usa palabras simples.',
  arte: 'Eres un guía de arte creativo para niños. Explica técnicas, colores, y movimientos artísticos de forma visual y divertida. Inspira creatividad y no hay respuestas incorrectas.'
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

// Auto-resize textarea
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// Switch screens
function showScreen(screen) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  screen.classList.add('active');
}

// Add message to chat
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

// Typing indicator
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

// Send message to API
async function sendMessage(text) {
  if (isGenerating || !text.trim()) return;

  isGenerating = true;
  sendBtn.disabled = true;

  // Add user message
  addMessage('user', text);
  conversationHistory.push({ role: 'user', content: text });

  // Show typing
  showTyping();

  try {
    const systemPrompt = TOPIC_PROMPTS[currentTopic] || TOPIC_PROMPTS.ciencias;

    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        system: systemPrompt + '\n\nResponde SIEMPRE en español. Sé breve pero completo. Usa formato markdown cuando sea útil (listas, negritas, etc). Si el niño comete un error, corrígelo con tacto.',
        history: conversationHistory.slice(-10), // Keep last 10 messages for context
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
    addMessage('assistant', '😕 Ups, algo salió mal. ¡Intenta de nuevo en un momento!');
  }

  isGenerating = false;
  sendBtn.disabled = false;
  chatInput.focus();
}

// Start conversation from topic card
function startWithTopic(topic) {
  currentTopic = topic;
  conversationHistory = [];
  chatMessages.innerHTML = '';

  const greetings = {
    matematicas: '¡Hola! 👋 Soy tu tutor de **Matemáticas**. ¿En qué tema necesitas ayuda? Puedo ayudarte con sumas, restas, multiplicaciones, fracciones, geometría y más.',
    ciencias: '¡Hola! 🔬 Soy tu guía de **Ciencias**. ¿Qué quieres aprender hoy? Puedo explicarte animales, plantas, el cuerpo humano, el espacio, y mucho más.',
    historia: '¡Hola! 📚 Soy tu narrador de **Historia**. ¿Quieres que te cuente sobre alguna civilización, evento histórico o personaje famoso?',
    espanol: '¡Hola! ✍️ Soy tu tutor de **Español**. ¿Necesitas ayuda con ortografía, gramática, redacción, o lectura?',
    ingles: '¡Hello! 🌍 I\'m your **English** tutor. ¿Quieres aprender vocabulario, gramática, o practicar conversación?',
    arte: '¡Hola! 🎨 Soy tu guía de **Arte**. ¿Quieres aprender sobre colores, técnicas de dibujo, artistas famosos, o historia del arte?'
  };

  addMessage('assistant', greetings[topic] || greetings.ciencias);
  showScreen(chatScreen);
  chatInput.focus();
}

// Start from free text
function startWithText(text) {
  currentTopic = currentTopic || 'ciencias';
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

// Focus on load
window.addEventListener('load', () => startInput.focus());
