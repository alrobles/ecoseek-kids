/* ===== EMILY ASTRONAUT — Chat Integration ===== */
/* Manages Emily's states, speech bubbles, sparkles, and chat stars */

const EmilyChat = (() => {
  let container = null;
  let speechBubble = null;
  let state = 'idle'; // idle, thinking, talking, celebrate, wave
  let bubbleTimeout = null;
  let stateTimeout = null;
  let starsContainer = null;

  // Emily's fun messages for different states
  const emilyPhrases = {
    thinking: [
      'Hmm, let me think about that... 🔬',
      'Searching my science notebooks... 📚',
      'Great question! Thinking... 🤔',
      'Consulting the data... 📊',
      'Almost ready! ✨',
    ],
    greeting: [
      'Hi there, explorer! 🌍',
      'Welcome back! Ready to discover? 🔭',
      'Hey! What shall we explore today? 🌿',
      'Ready for a science adventure? 🚀',
    ],
    celebrate: [
      'Science is awesome! ✨',
      'Great question! 🎉',
      'You\'re a real scientist! 🔬',
      'Keep exploring! 🌟',
    ]
  };

  function randomFrom(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  // Inject Emily's SVG + container into the page
  function init() {
    if (container) return;

    // Create main container
    container = document.createElement('div');
    container.className = 'emily-container hidden';
    container.id = 'emily-astronaut';

    // Load SVG inline so animations work
    const wrapper = document.createElement('div');
    wrapper.className = 'emily-svg-wrapper';

    // Fetch and inject SVG
    fetch('emily-astronaut.svg')
      .then(r => r.text())
      .then(svgText => {
        wrapper.innerHTML = svgText;
        // After SVG loads, start idle
        setTimeout(() => setState('idle'), 300);
      })
      .catch(() => {
        // Fallback: use img tag
        wrapper.innerHTML = '<img src="emily-astronaut.svg" alt="Emily" style="width:100%;height:100%">';
      });

    container.appendChild(wrapper);
    document.body.appendChild(container);

    // Create speech bubble
    speechBubble = document.createElement('div');
    speechBubble.className = 'emily-speech-bubble';
    speechBubble.id = 'emily-speech';
    document.body.appendChild(speechBubble);

    // Create chat stars background
    createChatStars();

    // Show Emily after a moment
    setTimeout(() => show(), 500);
  }

  // Create subtle floating stars in chat background
  function createChatStars() {
    starsContainer = document.createElement('div');
    starsContainer.className = 'chat-stars';
    const chatScreen = document.getElementById('chat-screen');
    if (chatScreen) {
      chatScreen.style.position = 'relative';
      chatScreen.insertBefore(starsContainer, chatScreen.firstChild);
    }

    for (let i = 0; i < 12; i++) {
      const star = document.createElement('div');
      star.className = 'chat-star';
      star.style.left = Math.random() * 100 + '%';
      star.style.animationDelay = Math.random() * 8 + 's';
      star.style.animationDuration = (6 + Math.random() * 6) + 's';
      const colors = ['#FFD700', '#A0D2F0', '#FFB5C2', '#D4B8F0', '#B8F0D4'];
      star.style.background = colors[Math.floor(Math.random() * colors.length)];
      starsContainer.appendChild(star);
    }
  }

  // Show/hide Emily
  function show() {
    if (!container) init();
    container.classList.remove('hidden');
    container.classList.add('visible');
  }

  function hide() {
    if (container) {
      container.classList.remove('visible');
      container.classList.add('hidden');
    }
    hideBubble();
  }

  // Set Emily's animation state
  function setState(newState, duration) {
    if (!container) return;
    clearTimeout(stateTimeout);

    // Remove all state classes
    container.classList.remove('emily-thinking', 'emily-talking', 'emily-celebrate', 'emily-wave');

    state = newState;

    // Add new state class
    switch (newState) {
      case 'thinking':
        container.classList.add('emily-thinking');
        break;
      case 'talking':
        container.classList.add('emily-talking');
        break;
      case 'celebrate':
        container.classList.add('emily-celebrate');
        break;
      case 'wave':
        container.classList.add('emily-wave');
        break;
      case 'idle':
      default:
        // No extra class, base float animation runs
        break;
    }

    // Auto-return to idle after duration
    if (duration && newState !== 'idle') {
      stateTimeout = setTimeout(() => setState('idle'), duration);
    }
  }

  // Show speech bubble with text
  function showBubble(text, duration = 4000) {
    if (!speechBubble) return;
    clearTimeout(bubbleTimeout);

    speechBubble.textContent = text;
    speechBubble.classList.add('visible');

    if (duration > 0) {
      bubbleTimeout = setTimeout(() => hideBubble(), duration);
    }
  }

  // Show thinking dots in bubble
  function showThinkingBubble() {
    if (!speechBubble) return;
    clearTimeout(bubbleTimeout);
    speechBubble.innerHTML = '<div class="bubble-dots"><div class="bubble-dot"></div><div class="bubble-dot"></div><div class="bubble-dot"></div></div>';
    speechBubble.classList.add('visible');
  }

  function hideBubble() {
    if (speechBubble) {
      speechBubble.classList.remove('visible');
    }
  }

  // Create sparkle burst effect at a position
  function sparkles(x, y) {
    const burst = document.createElement('div');
    burst.className = 'sparkle-burst';
    burst.style.left = x + 'px';
    burst.style.top = y + 'px';

    const colors = ['#FFD700', '#FF6B35', '#2CA58D', '#A0D2F0', '#FFB5C2', '#D4B8F0'];
    for (let i = 0; i < 8; i++) {
      const sparkle = document.createElement('div');
      sparkle.className = 'sparkle';
      sparkle.style.background = colors[i % colors.length];
      const angle = (i / 8) * Math.PI * 2;
      const dist = 30 + Math.random() * 40;
      sparkle.style.setProperty('--sx', Math.cos(angle) * dist + 'px');
      sparkle.style.setProperty('--sy', Math.sin(angle) * dist + 'px');
      burst.appendChild(sparkle);
    }

    document.body.appendChild(burst);
    setTimeout(() => burst.remove(), 1000);
  }

  // === EVENT HOOKS (called from app.js) ===

  // When user sends a message
  function onUserSend() {
    setState('thinking');
    showThinkingBubble();
  }

  // When Emily starts typing/generating response
  function onTypingStart() {
    setState('thinking');
    showThinkingBubble();
  }

  // When Emily finishes responding
  function onResponse(text) {
    setState('talking', 2000);
    hideBubble();

    // Sparkle near Emily
    if (container) {
      const rect = container.getBoundingClientRect();
      sparkles(rect.left + rect.width / 2, rect.top + rect.height / 3);
    }

    // Show celebrate briefly after talking
    setTimeout(() => {
      setState('celebrate', 1500);
    }, 2000);
  }

  // When entering chat screen
  function onChatEnter() {
    show();
    setState('wave', 2500);
    showBubble(randomFrom(emilyPhrases.greeting), 3000);
  }

  // When leaving chat screen
  function onChatLeave() {
    hideBubble();
    setState('idle');
    // Emily stays visible but goes idle
  }

  // Add Emily avatar to assistant message
  function decorateMessage(msgDiv) {
    if (!msgDiv.classList.contains('assistant')) return;
    const bubble = msgDiv.querySelector('.msg-bubble');
    if (!bubble) return;

    // Wrap bubble content in a row with avatar
    const row = document.createElement('div');
    row.className = 'msg-row';

    const avatar = document.createElement('div');
    avatar.className = 'emily-msg-avatar';
    const avatarImg = document.createElement('img');
    avatarImg.src = 'emily-avatar.png';
    avatarImg.alt = 'Emily';
    avatarImg.className = 'emily-avatar-img';
    avatar.appendChild(avatarImg);

    // Move bubble into row
    bubble.parentNode.insertBefore(row, bubble);
    row.appendChild(avatar);
    row.appendChild(bubble);
  }

  // Expose public API
  return {
    init,
    show,
    hide,
    setState,
    showBubble,
    showThinkingBubble,
    hideBubble,
    sparkles,
    onUserSend,
    onTypingStart,
    onResponse,
    onChatEnter,
    onChatLeave,
    decorateMessage,
  };
})();
