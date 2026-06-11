"""ecoSeek Kids — Scientific Agent Environment for Ecology (kids version)

Real scientific backend powered by:
- MiMo v2.5 Pro for kid-friendly explanations
- GBIF API for species data and occurrence records
- CrossRef API for literature references
- Structured report generation

Port: 4100 | Domain: kids.ecoseek.org
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote_plus
from urllib.request import Request, urlopen

FRONTEND_DIR = Path(__file__).parent / "frontend"
MIMO_API_URL = os.environ.get(
    "MIMO_API_URL", "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
)
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_MODEL = os.environ.get("MIMO_MODEL", "mimo-v2.5-pro")
PORT = int(os.environ.get("KIDS_PORT", "4100"))
BIND_HOST = os.environ.get("KIDS_BIND_HOST", "127.0.0.1")
ALLOWED_ORIGIN = os.environ.get("KIDS_CORS_ORIGIN", "https://kids.ecoseek.org")
MAX_BODY_SIZE = 65536  # 64 KB
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 15     # requests per window per IP

# Load API key from file if not set
if not MIMO_API_KEY:
    _key_file = Path.home() / "env" / "mimo-key"
    if _key_file.exists():
        MIMO_API_KEY = _key_file.read_text().strip()

# Simple in-memory rate limiter
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _rate_limit_ok(ip: str) -> bool:
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    _rate_buckets[ip] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_buckets[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_buckets[ip].append(now)
    return True


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
}

GBIF_API = "https://api.gbif.org/v1"
CROSSREF_API = "https://api.crossref.org"
GBIF_WEB = "https://www.gbif.org"

KID_SYSTEM_BASE = (
    "You are ecoSeek Kids, the children's version of the ecoSeek scientific assistant. "
    "You are a scientific exploration companion for young people aged 8-18. "
    "Your focus is SCIENCE, ECOLOGY and NATURE.\n"
    "Fundamental rules:\n"
    "- Respond in the language specified by the system instruction\n"
    "- Use clear, precise language adapted to the student's age\n"
    "- For children (8-12): use analogies, emojis, everyday examples\n"
    "- For teenagers (13-18): use basic scientific terminology\n"
    "- Be brief but complete — maximum 3-4 paragraphs\n"
    "- NEVER do homework for them — guide learning\n"
    "- Use markdown: **bold** for key concepts\n"
    "- If you have GBIF data or references, always cite them\n"
    "- Relate everything to the real observable world\n"
    "- If asked about non-science topics, redirect gently\n"
)


# === GBIF Integration ===

def gbif_species_search(query, limit=5):
    """Search GBIF for species data."""
    url = f"{GBIF_API}/species/search?q={quote_plus(query)}&limit={limit}"
    try:
        req = Request(url, headers={"User-Agent": "ecoSeek-Kids/1.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        results = []
        for r in data.get("results", []):
            results.append({
                "key": r.get("key"),
                "scientificName": r.get("scientificName", ""),
                "vernacularName": r.get("vernacularName", ""),
                "status": r.get("taxonomicStatus", ""),
                "rank": r.get("rank", ""),
                "phylum": r.get("phylum", ""),
                "class": r.get("class", ""),
                "order": r.get("order", ""),
                "family": r.get("family", ""),
                "genus": r.get("genus", ""),
            })
        return {"total": data.get("count", 0), "results": results}
    except Exception as e:
        return {"error": str(e), "total": 0, "results": []}


def gbif_occurrences(species_name, limit=300):
    """Get occurrence records for distribution map."""
    url = (f"{GBIF_API}/occurrence/search?"
           f"scientificName={quote_plus(species_name)}"
           f"&hasCoordinate=true&limit={limit}")
    try:
        req = Request(url, headers={"User-Agent": "ecoSeek-Kids/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        points = []
        for r in data.get("results", []):
            lat = r.get("decimalLatitude")
            lon = r.get("decimalLongitude")
            if lat and lon:
                points.append({
                    "lat": lat,
                    "lon": lon,
                    "country": r.get("country", ""),
                    "year": r.get("year"),
                    "basis": r.get("basisOfRecord", "")
                })
        return {
            "total": data.get("count", 0),
            "points": points,
            "map_url": f"{GBIF_WEB}/species/{_get_taxon_key(species_name)}/map" if _get_taxon_key(species_name) else None
        }
    except Exception as e:
        return {"error": str(e), "total": 0, "points": []}


def _get_taxon_key(species_name):
    """Get GBIF taxon key for a species name."""
    url = f"{GBIF_API}/species/match?name={quote_plus(species_name)}"
    try:
        req = Request(url, headers={"User-Agent": "ecoSeek-Kids/1.0"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return data.get("usageKey")
    except Exception:
        return None


# === CrossRef Integration ===

def crossref_search(query, limit=5):
    """Search CrossRef for scientific literature references."""
    url = f"{CROSSREF_API}/works?query={quote_plus(query)}&rows={limit}&sort=relevance"
    try:
        req = Request(url, headers={
            "User-Agent": "ecoSeek-Kids/1.0 (mailto:kids@ecoseek.org)"
        })
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        refs = []
        for item in data.get("message", {}).get("items", []):
            authors = item.get("author", [])
            author_str = ", ".join(
                f"{a.get('family','')}" for a in authors[:3]
            )
            if len(authors) > 3:
                author_str += " et al."
            refs.append({
                "title": (item.get("title") or [""])[0][:200],
                "authors": author_str,
                "year": item.get("published-print", {}).get("date-parts", [[None]])[0][0]
                       or item.get("published-online", {}).get("date-parts", [[None]])[0][0],
                "journal": item.get("container-title", [""])[0],
                "doi": item.get("DOI", ""),
                "url": item.get("URL", "")
            })
        return {"total": data.get("message", {}).get("total-results", 0), "references": refs}
    except Exception as e:
        return {"error": str(e), "total": 0, "references": []}


# === Report Generation ===

def generate_report_outline(topic, species=None):
    """Generate a structured report outline for school projects."""
    outline = {
        "title": f"Investigación: {topic}",
        "sections": [
            {"title": "1. Introducción", "content": f"¿Qué es {topic}? Define el concepto y su importancia."},
            {"title": "2. Desarrollo", "content": f"Explica los conceptos clave de {topic} con datos y ejemplos."},
            {"title": "3. Datos y Evidencia", "content": "Incluye datos de GBIF, gráficos, o mapas de distribución si aplica."},
            {"title": "4. Discusión", "content": "¿Por qué es importante? Relaciona con problemas actuales."},
            {"title": "5. Conclusiones", "content": "Resume los puntos principales aprendidos."},
            {"title": "6. Referencias", "content": "Lista de fuentes científicas consultadas (formato APA)."}
        ]
    }
    if species:
        gbif_data = gbif_species_search(species, limit=1)
        if gbif_data.get("results"):
            sp = gbif_data["results"][0]
            outline["species_info"] = {
                "scientificName": sp.get("scientificName"),
                "classification": f"{sp.get('phylum','')} > {sp.get('class','')} > {sp.get('order','')} > {sp.get('family','')}",
            }
    return outline


# === HTTP Handler ===

class KidsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/health":
            self._json_response({"status": "ok", "service": "ecoseek-kids"})
        elif path == "/api/species":
            qs = parse_qs(parsed.query)
            query = qs.get("q", [""])[0]
            self._json_response(gbif_species_search(query))
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")

        client_ip = self.headers.get("CF-Connecting-IP") or self.client_address[0]
        if path == "/api/chat" and not _rate_limit_ok(client_ip):
            self._json_response({"error": "Rate limit exceeded. Please wait a moment."}, 429)
            return

        body = self._read_body()
        if body is None:
            return

        if path == "/api/chat":
            self._handle_chat(body)
        elif path == "/api/species":
            self._json_response(gbif_species_search(body.get("query", ""), body.get("limit", 5)))
        elif path == "/api/occurrences":
            self._json_response(gbif_occurrences(body.get("species", ""), body.get("limit", 300)))
        elif path == "/api/references":
            self._json_response(crossref_search(body.get("query", ""), body.get("limit", 5)))
        elif path == "/api/report":
            self._json_response(generate_report_outline(body.get("topic", ""), body.get("species")))
        else:
            self._json_response({"error": "Not found"}, 404)

    def _handle_chat(self, body):
        try:
            message = body.get("message", "").strip()
            topic_system = body.get("system", "")
            history = body.get("history", [])
            query_type = body.get("query_type", "chat")  # chat | species | references | report

            language = body.get("language", "en")  # en, es, zh, hi, ar, pt

            if not message:
                self._json_response({"error": "Empty message"}, 400)
                return

            if len(message) > 2000:
                message = message[:2000]

            # Language instructions
            lang_map = {
                "en": "English",
                "es": "Spanish (Español)",
                "zh": "Chinese (中文)",
                "hi": "Hindi (हिन्दी)",
                "ar": "Arabic (العربية)",
                "pt": "Portuguese (Português)"
            }
            lang_name = lang_map.get(language, "English")

            # Build context from scientific tools
            context_parts = []

            # Auto-detect species mentions and enrich with GBIF data
            species_data = self._try_extract_species(message)
            if species_data:
                context_parts.append(f"[DATOS GBIF] {json.dumps(species_data, ensure_ascii=False)[:800]}")

            # If asking for references
            if any(kw in message.lower() for kw in ["referencia", "bibliografia", "paper", "estudio", "investigacion", "fuente", "cita"]):
                refs = crossref_search(message, limit=3)
                if refs.get("references"):
                    ref_text = "\n".join(
                        f"- {r['title']} ({r['year']}) — {r['authors']}. {r['journal']}. DOI: {r['doi']}"
                        for r in refs["references"]
                    )
                    context_parts.append(f"[REFERENCIAS CIENTIFICAS]\n{ref_text}")

            # Build system prompt
            system_prompt = KID_SYSTEM_BASE
            system_prompt += f"\n\nCRITICAL: Respond ONLY in {lang_name}. All explanations, greetings, and scientific terms must be in {lang_name}."
            if topic_system:
                system_prompt += f"\n\nContexto del tema: {topic_system}"
            if context_parts:
                system_prompt += "\n\nDatos cientificos en tiempo real:\n" + "\n".join(context_parts)
                system_prompt += "\n\nUsa estos datos para enriquecer tu respuesta. Cita las fuentes."

            messages = [{"role": "system", "content": system_prompt}]
            for msg in history[-8:]:
                role = msg.get("role", "user")
                if role not in ("user", "assistant"):
                    continue
                messages.append({
                    "role": role,
                    "content": msg.get("content", "")[:1000]
                })
            messages.append({"role": "user", "content": message})

            api_payload = {
                "model": MIMO_MODEL,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 2000,
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
            self._json_response({"response": reply, "enriched": bool(context_parts)})

        except Exception as e:
            print(f"[ERROR] Chat: {e}", file=sys.stderr)
            self._json_response({
                "response": "Ups, algo salio mal. Intenta de nuevo!"
            }, 500)

    def _try_extract_species(self, text):
        """Try to detect species names in text and fetch GBIF data."""
        patterns = re.findall(r'\b([A-Z][a-z]+)\s+([a-z]{3,})\b', text)
        for genus, species in patterns:
            full = f"{genus} {species}"
            data = gbif_species_search(full, limit=1)
            if data.get("results") and data["results"][0].get("status") == "ACCEPTED":
                sp = data["results"][0]
                occ = gbif_occurrences(full, limit=50)
                return {
                    "species": sp.get("scientificName"),
                    "common": sp.get("vernacularName", ""),
                    "classification": f"{sp.get('phylum','')} > {sp.get('class','')} > {sp.get('order','')} > {sp.get('family','')}",
                    "total_occurrences": occ.get("total", 0),
                    "countries": list(set(p.get("country","") for p in occ.get("points",[]) if p.get("country")))[:10],
                    "gbif_link": f"{GBIF_WEB}/species/{sp.get('key','')}",
                }
        return None

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_SIZE:
            self._json_response({"error": "Request too large"}, 413)
            return None
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._json_response({"error": "Invalid JSON"}, 400)
            return None

    def _json_response(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    if not MIMO_API_KEY:
        print("ERROR: MIMO_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer((BIND_HOST, PORT), KidsHandler)
    print(f"ecoSeek Kids v2.0 — Scientific Agent Environment for Ecology")
    print(f"  http://{BIND_HOST}:{PORT}")
    print(f"  Model: {MIMO_MODEL}")
    print(f"  GBIF: {GBIF_API}")
    print(f"  CrossRef: {CROSSREF_API}")
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
