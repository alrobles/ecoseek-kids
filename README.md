# ecoSeek Kids

**Scientific Agent Environment for Ecology (kids version)**

Una versión infantil del asistente científico ecoSeek, diseñada para niños de 6-15 años. Enfocado en ciencia, ecología y naturaleza.

## Visión

ecoSeek es un asistente científico. ecoSeek Kids es la puerta de entrada para los más pequeños — misma identidad de marca, mismo enfoque en ciencia, pero con lenguaje simple, colores pasteles y una interfaz ligera sin panel derecho.

## Temas

| Tema | Enfoque |
|------|---------|
| Ecología | Ecosistemas, cadenas alimenticias, cambio climático |
| Animales | Zoología, hábitats, clasificación, datos curiosos |
| Plantas | Botánica, fotosíntesis, experimentos caseros |
| La Tierra | Volcanes, terremotos, ciclo del agua, rocas |
| Espacio | Sistema solar, estrellas, Luna, planetas |
| Cuerpo Humano | Sistemas del cuerpo, hábitos saludables |

## Arquitectura

```
kids.ecoseek.org                    hermes.ecoseek.org
       │                                  │
  Cloudflare Tunnel                  Cloudflare Tunnel
       │                                  │
  ┌────▼────┐                       ┌─────▼─────┐
  │ Python  │  ─── /api/chat ───▶  │  Hermes    │
  │ server  │  ◀── response ─────  │  Gateway   │
  │ :4100   │                       │  :8642     │
  └─────────┘                       └─────┬─────┘
                                          │
                                    ┌─────▼─────┐
                                    │  MiMo v2.5 │ ← Xiaomi API
                                    │  Pro       │ ← Temp 0.4
                                    └───────────┘
```

**Flujo de comunicación:**
1. El niño escribe en kids.ecoseek.org
2. El frontend JS envía POST a `/api/chat` en el mismo origen
3. El server Python (puerto 4100) reenvía la petición a hermes.ecoseek.org (gateway Hermes, puerto 8642)
4. Hermes ejecuta el agente con MiMo v2.5 Pro como modelo
5. La respuesta vuelve al frontend con datos GBIF enriquecidos cuando aplica

**Comunicación con MiMo:** Toda la comunicación con el modelo MiMo pasa por Hermes (hermes.ecoseek.org). El server Python de kids.ecoseek.org NO habla directamente con la API de Xiaomi — usa Hermes como gateway.

## Stack

- **Frontend:** HTML/CSS/JS vanilla (sin frameworks)
- **Backend:** Python HTTP server (stdlib, sin dependencias)
- **API:** MiMo v2.5 Pro via Hermes Gateway
- **Gateway:** hermes.ecoseek.org (Hermes Agent, puerto 8642)
- **Servicio:** systemd user service
- **Tunnel:** Cloudflare Tunnel → kids.ecoseek.org
- **Puerto:** 4100

## Características

### Emily Astronauta (PR #6)

Emily es la mascota animada del chat — una astronauta que flota en la esquina inferior derecha con múltiples estados de animación:

| Estado | Trigger | Animación |
|--------|---------|-----------|
| `idle` | Default | Flotación suave con rotación, 4s cycle |
| `think` | Usuario envía mensaje | Inclinación + balanceo, bubble con dots |
| `talk` | Respuesta recibida | Vibración rápida, sparkle burst |
| `celebrate` | Después de responder | Salto + escala |
| `wave` | Entrar al chat | Balanceo amplio (saludo) |
| `flame` | Siempre activo | Llameo del jetpack (0.3s) |

**Efectos visuales:**
- 6 estrellas con twinkle independiente
- 4 partículas orbitando
- 12 chat-stars flotando en fondo del chat
- Glint sweep en el visor del casco
- Sparkle burst al recibir respuesta
- Avatar 👩‍🔬 con pulso brillante en mensajes
- Speech bubble con saludo aleatorio
- Burbujas de texto al pensar

**Archivos:**
- `frontend/emily-astronaut.svg` — SVG del personaje
- `frontend/emily-chat.css` — Animaciones CSS (6 keyframes + efectos)
- `frontend/emily-chat.js` — Motor de estados e integración

### Tarjetas de Temas con SVG (PR #5)

Las tarjetas de temas usan ilustraciones SVG (80×80px) en vez de emojis. Incluye escenas de savana con leones (Animales), cuerpo humano con corazón y cerebro (Body), etc.

**Archivos:** `frontend/icons/{ecology,animals,plants,earth,space,body}.svg`

### Respuestas Kid-Friendly (PR #3)

- Respuestas adaptadas para niños ≤8 años
- Botones de follow-up clickeables después de cada respuesta
- Respuestas cortas y directas con lenguaje simple

### Seguridad (PR #1, #4)

- Headers de seguridad (X-Frame-Options, CSP, X-Content-Type-Options)
- Sanitización HTML contra XSS en frontend y backend
- CORS restringido a ecoseek.org
- Rate limiting en API
- Content safety guardrails (bloquea temas inapropiados para niños)
- Input sanitization en el server

### Internacionalización (PR #2)

6 idiomas: EN, ES, ZH, HI, AR, PT
- Selector con iniciales de idioma (no banderas)
- Soporte RTL para árabe
- i18n.js con todas las traducciones

## Despliegue

```bash
# Servicio
systemctl --user status ecoseek-kids

# Logs
journalctl --user -u ecoseek-kids -f

# Restart
systemctl --user restart ecoseek-kids
```

## Diferencias con ecoSeek (Emily)

| | ecoSeek (Emily) | ecoSeek Kids |
|---|---|---|
| Audiencia | Investigadores, profesionales | Niños 6-15 años |
| Interfaz | Chat completo + panel derecho | Chat simplificado, sin panel |
| Backend | Hermes gateway + herramientas | Python HTTP server ligero |
| Comunicación | hermes.ecoseek.org directo | Python → hermes.ecoseek.org |
| HPC | Sí (KU CRC) | No |
| Herramientas | Terminal, web, archivos, subagentes | Ninguna |
| Colores | Oscuro/profesional | Blanco + pasteles |
| Dominio | emily.ecoseek.org | kids.ecoseek.org |
| Mascota | Avatar circular | Emily astronauta animada |

## PRs

| # | Título | Autor | Estado |
|---|--------|-------|--------|
| 1 | Security hardening (headers, XSS, CORS, rate-limit) | Devin | Merged |
| 2 | Language initials + home button | Devin | Merged |
| 3 | Kid-friendly responses + follow-up options | Devin | Merged |
| 4 | Content safety guardrails | Devin | Merged |
| 5 | SVG illustrated topic cards + logos | Devin | Merged |
| 6 | Emily astronaut animated character | Hermes/MiMo | Merged |
| 7 | Responsive fixes + followup buttons | Devin | Open |

## Repositorio

- GitHub: https://github.com/alrobles/ecoseek-kids
- Local: ~/dev/ecoseek-kids
