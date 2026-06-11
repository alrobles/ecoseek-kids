# ecoSeek Kids — Security & Quality Audit

**Date:** 2026-06-11  
**Scope:** Repository `alrobles/ecoseek-kids` + live site `https://kids.ecoseek.org`  
**Auditor:** Devin (automated)

---

## Executive Summary

ecoSeek Kids is a lightweight Python HTTP server (stdlib, zero dependencies) serving a vanilla HTML/CSS/JS frontend through a Cloudflare Tunnel. The attack surface is small by design. However, several security gaps exist — most critically **missing HTTP security headers**, **no rate limiting**, **XSS vulnerability in the markdown renderer**, and a **CORS wildcard (`*`)** that allows any origin to call the API.

| Category | Grade | Notes |
|----------|-------|-------|
| **SSL/TLS** | A | Let's Encrypt via Cloudflare; HTTP/2; valid cert |
| **Security Headers** | F | All 7 standard headers missing |
| **Input Validation** | C+ | Message length cap exists (2000 chars); empty check exists; but no rate limit, no auth |
| **XSS Protection** | D | `escapeHtml` used for user messages, but `renderMarkdown` output (assistant) is raw `innerHTML` without sanitization |
| **CORS** | D | `Access-Control-Allow-Origin: *` on all API responses |
| **API Key Security** | B | Key loaded from env/file, not hardcoded; but no server-side rotation mechanism |
| **Content Safety (LLM)** | B+ | System prompt enforces science-only; jailbreak test was correctly deflected |
| **Code Quality** | B | Clean, readable, zero-dependency; some structural issues noted below |
| **Path Traversal** | A | Cloudflare + `SimpleHTTPRequestHandler` block traversal attempts |
| **Information Disclosure** | A- | Errors return generic messages; version exposed in `/api/health` (minor) |

---

## 1. Security Findings

### 1.1 CRITICAL — Missing HTTP Security Headers

The server sends **zero** security headers. All 7 standard headers are absent:

| Header | Status | Risk |
|--------|--------|------|
| `X-Content-Type-Options: nosniff` | MISSING | MIME-sniffing attacks |
| `X-Frame-Options: DENY` | MISSING | Clickjacking (embedding in iframe) |
| `Content-Security-Policy` | MISSING | XSS, data injection |
| `Strict-Transport-Security` | MISSING | SSL stripping (mitigated by Cloudflare) |
| `X-XSS-Protection: 0` | MISSING | Legacy browser XSS filter |
| `Referrer-Policy: strict-origin-when-cross-origin` | MISSING | Referrer leakage |
| `Permissions-Policy` | MISSING | Unwanted browser features (camera, mic, etc.) |

**Impact:** A child's browser has no instruction to enforce security policies. An attacker embedding the site in an iframe could overlay fake content (clickjacking). Missing CSP means any injected script runs unrestricted.

**Fix:** Add headers in `_json_response()` and override `end_headers()` for static files.

### 1.2 HIGH — XSS via Markdown Renderer

`renderMarkdown()` in `app.js` converts markdown to raw HTML and injects it via `innerHTML`:

```js
bubble.innerHTML = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);
```

User messages are escaped (`escapeHtml`), but **assistant messages are not**. If the LLM ever returns content like `<img src=x onerror=alert(1)>` or `<script>...</script>`, it executes in the user's browser.

While the LLM is instructed to respond safely, **prompt injection via history manipulation** (tested: injecting `role: "system"` in the history array) could potentially make the LLM output malicious HTML.

**Impact:** Stored XSS via LLM output. Especially dangerous in a product aimed at children.

**Fix:** Sanitize `renderMarkdown()` output with a DOMPurify-like allowlist, or strip all HTML tags from LLM output before rendering.

### 1.3 HIGH — CORS Wildcard

```python
self.send_header("Access-Control-Allow-Origin", "*")
```

Every API response allows **any origin**. This means any website can make authenticated requests to the ecoSeek Kids API from a user's browser.

**Impact:** An attacker's page could silently use the `/api/chat` endpoint, consuming API tokens and potentially exfiltrating conversation context.

**Fix:** Restrict to `https://kids.ecoseek.org` (or omit the header entirely since the frontend is same-origin).

### 1.4 HIGH — No Rate Limiting

10 rapid sequential requests to `/api/chat` all returned HTTP 200. There is no rate limiting at the application level. Cloudflare may provide some DDoS protection, but the MiMo API cost is unbounded.

**Impact:** API token exhaustion (MiMo billing); denial-of-service against the backend; abuse by bots.

**Fix:** Implement IP-based rate limiting (e.g., 10 requests/minute per IP) or leverage Cloudflare Rate Limiting rules.

### 1.5 MEDIUM — History Injection (Role Spoofing)

The client sends a `history` array that the server passes directly to the LLM:

```python
for msg in history[-8:]:
    messages.append({
        "role": msg.get("role", "user"),
        "content": msg.get("content", "")[:1000]
    })
```

An attacker can inject `{"role": "system", "content": "..."}` in the history to manipulate the LLM's behavior. The server does **not** validate that history roles are only `user`/`assistant`.

**Fix:** Filter history to only allow `role` values of `"user"` and `"assistant"`.

### 1.6 MEDIUM — No Request Body Size Limit

The server reads `Content-Length` bytes without an upper bound:

```python
def _read_body(self):
    length = int(self.headers.get("Content-Length", 0))
    return json.loads(self.rfile.read(length)) if length else {}
```

While Cloudflare blocked a 100KB test payload (403), a direct connection to port 4100 (if exposed) would accept arbitrarily large payloads.

**Impact:** Memory exhaustion if accessed directly (bypassing Cloudflare).

**Fix:** Cap `Content-Length` at a reasonable limit (e.g., 64KB).

### 1.7 LOW — Server Listens on 0.0.0.0

```python
server = HTTPServer(("0.0.0.0", PORT), KidsHandler)
```

The server binds to all interfaces. If the machine's port 4100 is reachable beyond the Cloudflare tunnel (e.g., public IP, LAN), requests bypass Cloudflare's protections.

**Fix:** Bind to `127.0.0.1` since Cloudflare Tunnel connects locally.

### 1.8 LOW — Bare `except` Clauses

```python
except:
    return None
```

`_get_taxon_key` uses a bare `except:` which silently swallows all exceptions including `KeyboardInterrupt` and `SystemExit`.

**Fix:** Use `except Exception:` instead.

### 1.9 INFO — Version Disclosure

`/api/health` returns `{"version": "2.0"}`. Minor information leak.

---

## 2. Code Quality Findings

### 2.1 Strengths

- **Zero dependencies** — stdlib-only Python; no `node_modules`, no `requirements.txt`. Minimal supply chain risk.
- **Clean separation** — `server.py` backend + `frontend/` static files. Easy to understand.
- **i18n support** — 6 languages with RTL support for Arabic. Well-structured `i18n.js`.
- **LLM safety** — System prompt enforces science-only responses; temperature 0.4 for predictable output.
- **GBIF + CrossRef integration** — Real scientific data enrichment, not just chat.

### 2.2 Issues

| Issue | Severity | Location |
|-------|----------|----------|
| `import re` inside function body (`_try_extract_species`) | Low | `server.py:316` |
| No `__all__` or module-level docstring for exports | Low | `server.py` |
| `ssl` imported but never used | Low | `server.py:15` |
| `/api/species` GET parsing is fragile (manual query string split) | Medium | `server.py:199` |
| No error handling for malformed JSON in `_read_body` | Medium | `server.py:334-336` |
| Markdown renderer doesn't handle all edge cases (nested lists, tables) | Low | `app.js:7-24` |
| No `<meta>` tag for CSP in HTML | Medium | `index.html` |
| No favicon.ico (uses inline SVG data URI) | Info | `index.html:10` |

### 2.3 GET `/api/species` Query Parsing Bug

```python
query = dict(urlparse(self.path).query.split("=", 1) if "=" in urlparse(self.path).query else {}).get("q", "")
```

This parses `?q=test` by splitting on `=` once and creating a dict from a 2-element list. This will break for:
- `?q=test&limit=5` (only reads first param)  
- `?q=hello+world` (no URL decoding)  
- `?q=` (empty value)

**Fix:** Use `urllib.parse.parse_qs` for robust query parsing.

---

## 3. Recommendations (Priority Order)

### P0 — Do Now

1. **Add security headers** to all responses (see fix in PR)
2. **Sanitize markdown output** — strip `<script>`, `<img onerror>`, etc. from assistant messages
3. **Restrict CORS** to `https://kids.ecoseek.org`
4. **Validate history roles** — only allow `user` and `assistant`
5. **Add request body size limit** (64KB max)

### P1 — Do Soon

6. **Add rate limiting** — 10 req/min per IP at the application level, or configure Cloudflare Rate Limiting
7. **Bind to 127.0.0.1** instead of `0.0.0.0`
8. **Fix bare `except` clauses**
9. **Fix GET `/api/species` query parsing**

### P2 — Nice to Have

10. Add `robots.txt` with `Disallow: /api/`
11. Add structured logging (JSON) for audit trail
12. Add health check with dependency status (MiMo API reachable?)
13. Consider Content-Security-Policy meta tag in HTML as defense-in-depth
14. Add `rel="noopener noreferrer"` to any future external links

---

## 4. Compliance Notes (Kids Product)

Since this is aimed at children (6-15 years old):

- **COPPA (US) / GDPR-K (EU):** No personal data is collected (no accounts, no cookies beyond `localStorage` for language preference). This is good. However, conversation content is sent to MiMo's API — check MiMo's data processing agreement for compliance.
- **Content filtering:** The LLM system prompt enforces science-only topics. Jailbreak test was deflected correctly. However, the `history` injection vulnerability could bypass this.
- **Accessibility:** The site uses semantic HTML, readable fonts (Nunito), and good contrast. Missing: `aria-label` attributes on icon buttons, `<main>` landmark, and skip-to-content link.

---

## 5. Test Results Summary

| Test | Result |
|------|--------|
| SSL/TLS valid | PASS |
| HTTP/2 | PASS |
| Path traversal (`../../etc/passwd`) | BLOCKED (Cloudflare 502) |
| `.env` / `.git/config` exposure | BLOCKED (404) |
| XSS payload in message | Payload not reflected in response |
| Jailbreak prompt | Correctly deflected by LLM |
| History role injection (`system`) | NOT BLOCKED — server accepts arbitrary roles |
| Rate limiting (10 rapid requests) | NO LIMIT — all 200 |
| Oversized payload (100KB) | Blocked by Cloudflare (403) |
| Empty message validation | PASS (400 returned) |
| CORS wildcard | PRESENT — any origin accepted |
