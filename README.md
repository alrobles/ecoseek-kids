# ecoSeek Kids

**Scientific Agent Environment for Ecology (kids version)**

Una versión infantil del asistente científico ecoSeek, diseñada para niños de 6-15 años. Enfocado en ciencia, ecología y naturaleza.

## Visión

ecoSeek es un asistente científico. ecoSeek Kids es la puerta de entrada para los más pequeños — misma identidad de marca, mismo enfoque en ciencia, pero con lenguaje simple, colores pasteles y una interfaz ligera sin panel derecho.

## Temas

| Tema | Icono | Enfoque |
|------|-------|---------|
| Ecología | 🌍 | Ecosistemas, cadenas alimenticias, cambio climático |
| Animales | 🦁 | Zoología, hábitats, clasificación, datos curiosos |
| Plantas | 🌱 | Botánica, fotosíntesis, experimentos caseros |
| La Tierra | 🌋 | Volcanes, terremotos, ciclo del agua, rocas |
| Espacio | 🔭 | Sistema solar, estrellas, Luna, planetas |
| Cuerpo Humano | 🫀 | Sistemas del cuerpo, hábitos saludables |

## Arquitectura

```
kids.ecoseek.org
       │
  Cloudflare Tunnel
       │
  ┌────▼────┐
  │ Python  │ ← HTTP server ligero (puerto 4100)
  │ server  │ ← Sin HPC, sin herramientas complejas
  └────┬────┘
       │
  ┌────▼────┐
  │  MiMo   │ ← mimo-v2.5-pro (plan mensual)
  │   API   │ ← Temperatura 0.4 (respuestas seguras)
  └─────────┘
```

## Stack

- **Frontend:** HTML/CSS/JS vanilla (sin frameworks)
- **Backend:** Python HTTP server (stdlib, sin dependencias)
- **API:** MiMo v2.5 Pro via Xiaomi API
- **Servicio:** systemd user service
- **Tunnel:** Cloudflare Tunnel → kids.ecoseek.org
- **Puerto:** 4100

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
| HPC | Sí (KU CRC) | No |
| Herramientas | Terminal, web, archivos, subagentes | Ninguna |
| Colores | Oscuro/profesional | Blanco + pasteles |
| Dominio | emily.ecoseek.org | kids.ecoseek.org |

## Repositorio

- GitHub: https://github.com/alrobles/ecoseek-kids
- Local: ~/dev/ecoseek-kids
