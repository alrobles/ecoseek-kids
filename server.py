"""ecoSeek Kids — Lightweight API server.

Serves the frontend and proxies chat requests to MiMo API
with kid-friendly system prompts. No HPC access, no complex tools.

Port: 4100
Domain: kids.ecoseek.org
"""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

FRONTEND_DIR = Path(__file__).parent / "frontend"
MIMO_API_URL = os.environ.get(
    "MIMO_API_URL", "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
)
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_MODEL = os.environ.get("MIMO_MODEL", "mimo-v2.5-pro")
PORT = int(os.environ.get("KIDS_PORT", "4100"))

# Load API key from file if not set
if not MIMO_API_KEY:
    _key_file = Path.home() / "env" / "mimo-key"
    if _key_file.exists():
        MIMO_API_KEY = _key_file.read_text().strip()

KID_SYSTEM_BASE = (
    "Eres ecoSeek Kids, la version infantil del asistente cientifico ecoSeek. "
    "Eres un companero de exploracion cientifica para ninos de 6-15 anos. "
    "Tu enfoque es CIENCIA, ECOLOGIA y NATURALEZA.\n"
    "Reglas fundamentales:\n"
    "- SIEMPRE responde en espanol\n"
    "- Usa lenguaje simple y claro, sin jerga tecnica\n"
    "- Se breve pero completo — maximo 2-3 parrafos por respuesta\n"
    "- Usa emojis para hacer la explicacion mas visual y divertida\n"
    "- Si el nino comete un error, corrigelo con tacto\n"
    "- Anima y refuerza positivamente ('Muy bien!', 'Buen intento!', 'Esa es una gran pregunta!')\n"
    "- Si la pregunta es ambigua, pide amablemente que aclare\n"
    "- NUNCA hagas tareas completas — guia al nino a que aprenda por si mismo\n"
    "- Usa formato markdown: **negritas** para conceptos clave, listas para pasos\n"
    "- Si no sabes algo, di 'No estoy seguro, pero podemos investigar juntos'\n"
    "- Responde SOLO a preguntas de ciencia, ecologia, naturaleza, animales, "
    "plantas, espacio, cuerpo humano y temas relacionados.\n"
    "- Si preguntan algo fuera de ciencia (matematicas, historia, etc.), "
    "responde amablemente: 'Soy un asistente cientifico, pregunta de ciencia!'\n"
    "- Si preguntan algo inapropiado, redirige amablemente a temas de ciencia.\n"
    "- Usa analogias con cosas cotidianas: 'Las celulas son como ladrillos de una casa'\n"
    "- Relaciona siempre con el mundo real que el nino puede observar\n"
)


class KidsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/health":
            self._json_response({"status": "ok", "service": "ecoseek-kids"})
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/chat":
            self._handle_chat()
        else:
            self._json_response({"error": "Not found"}, 404)

    def _handle_chat(self):
        try:
            body = self._read_body()
            message = body.get("message", "").strip()
            topic_system = body.get("system", "")
            history = body.get("history", [])

            if not message:
                self._json_response({"error": "Empty message"}, 400)
                return

            # Sanitize — max length
            if len(message) > 2000:
                message = message[:2000]

            system_prompt = KID_SYSTEM_BASE
            if topic_system:
                system_prompt += "\n\nContexto del tema: " + topic_system

            messages = [{"role": "system", "content": system_prompt}]
            for msg in history[-8:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")[:1000]
                })
            messages.append({"role": "user", "content": message})

            api_payload = {
                "model": MIMO_MODEL,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 1500,
                "top_p": 0.9
            }

            req = Request(
                MIMO_API_URL,
                data=json.dumps(api_payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {MIMO_API_KEY}"
                },
                method="POST"
            )

            with urlopen(req, timeout=30) as resp:
                api_data = json.loads(resp.read())

            reply = api_data["choices"][0]["message"]["content"]
            self._json_response({"response": reply})

        except Exception as e:
            print(f"[ERROR] Chat: {e}", file=sys.stderr)
            self._json_response({
                "response": "Ups, algo salio mal. Intenta de nuevo en un momento!"
            }, 500)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _json_response(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    if not MIMO_API_KEY:
        print("ERROR: MIMO_API_KEY not set and ~/env/mimo-key not found", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("0.0.0.0", PORT), KidsHandler)
    print(f"ecoSeek Kids running on http://0.0.0.0:{PORT}")
    print(f"  Frontend: {FRONTEND_DIR}")
    print(f"  Model: {MIMO_MODEL}")
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
