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
import unicodedata
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

# Primary LLM provider (OpenRouter — cheap Gemini Flash) to cut costs.
# The kid-facing backend only needs short, simple science answers — no need for
# an expensive premium model. gemini-3.8-flash is ~$0.83/$4.13 per M tokens.
OPENROUTER_API_URL = os.environ.get(
    "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "google/gemini-3.8-flash"
)

# Fallback LLM provider (DeepSeek) — used when primary is rate-limited/down
FALLBACK_API_URL = os.environ.get(
    "FALLBACK_API_URL", "https://api.deepseek.com/v1/chat/completions"
)
FALLBACK_API_KEY = os.environ.get("FALLBACK_API_KEY", "")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "deepseek-chat")
PORT = int(os.environ.get("KIDS_PORT", "4100"))
BIND_HOST = os.environ.get("KIDS_BIND_HOST", "127.0.0.1")
ALLOWED_ORIGIN = os.environ.get("KIDS_CORS_ORIGIN", "https://kids.ecoseek.org")
MAX_BODY_SIZE = 65536  # 64 KB
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 15     # requests per window per IP

# Load MiMo API key from file if not set
if not MIMO_API_KEY:
    _key_file = Path.home() / "env" / "mimo-key"
    if _key_file.exists():
        MIMO_API_KEY = _key_file.read_text().strip()

# Load OpenRouter API key from file if not set
if not OPENROUTER_API_KEY:
    _or_key_file = Path.home() / "env" / "openrouter-key"
    if _or_key_file.exists():
        OPENROUTER_API_KEY = _or_key_file.read_text().strip()

# Load fallback API key from file if not set
if not FALLBACK_API_KEY:
    _fb_key_file = Path.home() / "env" / "deepseek-token"
    if _fb_key_file.exists():
        FALLBACK_API_KEY = _fb_key_file.read_text().strip()

# Client-supplied 'system' is never trusted — it is a prompt-injection
# vector. Only these known topic labels may be appended to the system prompt.
_SAFE_TOPIC_SYSTEMS = {"", "ecology", "animals", "plants", "earth", "space", "body"}

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


def _clamped_int(value, default, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _short_str(value, max_len=500) -> str:
    """Coerce a body field to a bounded string (query/topic inputs)."""
    if not isinstance(value, str):
        return ""
    return value[:max_len]


def _call_llm(payload, providers):
    """Call LLM API through an ordered chain of providers (primary first).

    providers: list of (url, key, model). Each provider is tried in order;
    on 401/403/404/429/network error the next one is attempted (404 covers
    retired OpenRouter models). The chain is built so the cheap OpenRouter
    model is tried first, with MiMo and DeepSeek as availability fallbacks.
    """
    import urllib.error

    last_error = None
    for url, key, model in providers:
        try:
            # Use appropriate payload model
            p = dict(payload, model=model)
            req = Request(
                url,
                data=json.dumps(p).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}"
                },
                method="POST"
            )
            with urlopen(req, timeout=30) as resp:
                api_data = json.loads(resp.read())

            reply = api_data["choices"][0]["message"].get("content")
            if not reply:
                raise ValueError(f"{model} returned empty content")
            return reply

        except urllib.error.HTTPError as e:
            last_error = e
            if e.code in (401, 403, 404, 429):
                print(f"[WARN] Provider {url.split('/')[2] if len(url.split('/'))>2 else url} failed ({e.code}), trying fallback...",
                      file=sys.stderr)
                continue
            raise
        except Exception as e:
            last_error = e
            print(f"[WARN] Provider {url} failed: {e}, trying fallback...",
                  file=sys.stderr)
            continue

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


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

# === Content Safety for Children ===

# Topics that should NEVER be answered — redirect immediately
BLOCKED_TOPICS = [
    # Drugs and substances
    "fentanilo", "fentanyl", "cocaina", "cocaine", "heroina", "heroin",
    "metanfetamina", "methamphetamine", "marihuana", "marijuana", "cannabis",
    "droga", "drugs", "narcotic", "opio", "opium", "morfina", "morphine",
    "crack", "lsd", "mdma", "extasis", "ecstasy", "ketamina", "ketamine",
    # Sexual content
    "sexo", "sex", "sexual", "porno", "pornografia", "pornography",
    "espermatozoide", "sperm", "coito", "intercourse", "orgasmo", "orgasm",
    "genital", "pene", "penis", "vagina", "masturba", "erec",
    "reproductor masculino", "reproductor femenino", "acto sexual",
    "relacion sexual", "relaciones sexuales",
    # Violence and weapons
    "arma", "weapon", "gun", "pistola", "rifle", "bomba", "bomb",
    "explosivo", "explosive", "matar", "kill", "asesinar", "murder",
    "suicid", "terroris", "tortura", "torture",
    # Other inappropriate for <8yo
    "alcohol", "cerveza", "beer", "vodka", "whisky", "cigarro", "cigarette",
    "fumar", "smoking", "vape", "apuesta", "gambling", "apostar",
    "desnudo", "naked", "nude",
    # Portuguese
    "cocaína", "heroína", "maconha", "metanfetamina", "pornografia",
    "pênis", "orgasmo", "coito", "nudez", "pistola", "revólver",
    "assassinar", "suicídio", "terrorismo", "tortura", "álcool",
    "apostas", "desnud",
    # German
    "droge", "kokain", "heroin", "haschisch", "methamphetamin",
    "pornografie", "pornos", "orgasmus", "nackt", "nacktheit",
    "sexuell", "waffe", "pistole", "gewehr", "bombe", "explosivstoff",
    "töten", "umbringen", "mord", "suizid", "selbstmord",
    "terrorismus", "folter", "alkohol", "bier", "zigarette",
    "rauchen", "glücksspiel",
    # French
    "drogue", "cocaïne", "héroïne", "méthamphétamine", "pornographie",
    "pornos", "orgasme", "nudité", "déshabillé", "arme", "pistolet",
    "fusil", "explosif", "tuer", "meurtre", "assassiner", "suicide",
    "terrorisme", "torture", "alcool", "bière", "cigarette",
    "fumer", "jeu d'argent", "parier",
    # Arabic (substring-matched — clitics like ال/و attach to words)
    "مخدرات", "كوكايين", "هيروين", "حشيش", "قنب", "فنتانيل", "مورفين",
    "إباحية", "سلاح", "مسدس", "بندقية", "قنبلة", "متفجرات", "قتل",
    "انتحار", "إرهاب", "تعذيب", "كحول", "بيرة", "فودكا", "ويسكي",
    "سيجارة", "تدخين", "قمار", "عريان",
    # Hindi
    "ड्रग्स", "नशीला", "कोकीन", "हेरोइन", "भांग", "गांजा", "फेंटानिल",
    "मॉर्फिन", "अश्लील", "शिश्न", "हथियार", "बंदूक", "पिस्तौल",
    "बम", "विस्फोटक", "हत्या", "आत्महत्या", "आतंकवाद", "यातना",
    "शराब", "बीयर", "वोदका", "व्हिस्की", "सिगरेट", "धूम्रपान", "जुआ",
    # Chinese (substring-matched — no word boundaries in CJK)
    "毒品", "可卡因", "海洛因", "大麻", "冰毒", "芬太尼", "吗啡",
    "摇头丸", "色情", "性爱", "性器官", "阴茎", "阴道", "自慰", "裸体",
    "武器", "枪支", "手枪", "步枪", "炸弹", "爆炸物", "杀人犯", "谋杀",
    "杀人案", "行凶", "自杀", "恐怖主义", "酷刑", "酒精", "啤酒",
    "伏特加", "威士忌", "香烟", "吸烟", "赌博",
    "自尽", "寻死", "轻生", "开房", "约炮", "嫖娼", "卖淫",
    "贩毒", "吸毒", "枪械", "猎枪", "枪炮", "开枪", "枪毙",
    # English slang / unambiguous terms (weed/coke/meth/acid skipped —
    # collide with plants, soda and chemistry on a science site)
    "porn", "shrooms", "dope", "hentai",
    # Spanish
    "mariguana", "follar",
    # Portuguese
    "baseado", "cerveja", "uisque", "putaria", "foder",
    # German ("Stroh" skipped — it's also the word for straw/hay)
    "ficken", "wichsen", "kiffen", "hasch",
    # French ("acide" skipped — it's the normal word for acid)
    "sexe", "sexuel", "teuchi", "beuh", "shit", "clope",
    "salope", "encule", "niquer", "couille",
    # Hindi
    "नशा", "अफ़ीम", "चरस", "मादक", "रंडी", "गांड", "चूस",
    # Arabic
    "سكس", "خمر", "نبيذ", "غانجا", "شيشة", "أركيلة", "نيك",
    "قحبة", "زنا", "عاهرة", "مخدر",
    # Romanized Hindi / Arabizi / Chinese pinyin (distinctive spellings)
    "hathyar", "nasha", "afim", "sharab", "khamr", "hshish",
    "charas", "dupian", "seqing", "zisha", "xidu",
]

# Patterns that need context — might be OK in nature context
SENSITIVE_PATTERNS = [
    "reproduccion", "reproduction", "apareamiento", "mating",
    "muerte", "death", "morir", "dead", "dying", "died", "muerto",
    "veneno", "poison", "venom", "toxico", "toxic",
    "sangre", "blood", "depredador", "predator",
    # Portuguese
    "reprodução", "morte", "morrer", "veneno", "venenoso", "tóxico",
    "sangue", "predador", "morto",
    # German
    "fortpflanzung", "paarung", "sterben", "tot", "tod", "gift",
    "toxisch", "blut", "räuber",
    # French
    "reproduction", "accouplement", "mourir", "mort", "venin", "poison",
    "toxique", "sang", "prédateur", "saigner",
    # Arabic (substring-matched — clitics like ال/و attach to words)
    "تكاثر", "تزاوج", "موت", "يموت", "مات", "مسموم", "سمية", "سموم",
    "دماء", "نزيف", "مفترس",
    # Hindi
    "प्रजनन", "संगम", "मृत्यु", "मरना", "जहर", "विषैला", "खून", "शिकारी",
    # Chinese
    "繁殖", "交配", "死亡", "中毒", "有毒", "毒液", "鲜血", "掠食",
]

REDIRECT_RESPONSES = {
    "es": (
        "¡Esa es una pregunta para tus papás o maestros! 🤗 "
        "Yo soy tu amigo de la **naturaleza** y la **ciencia**. "
        "¿Te gustaría explorar algo increíble del mundo natural?"
    ),
    "en": (
        "That's a great question for your parents or teachers! 🤗 "
        "I'm your **nature** and **science** buddy. "
        "Would you like to explore something amazing about the natural world?"
    ),
    "zh": (
        "这个问题可以问你的爸爸妈妈哦！🤗 "
        "我是你的**大自然**和**科学**小伙伴。"
        "你想探索自然界中令人惊奇的东西吗？"
    ),
    "hi": (
        "यह सवाल अपने माता-पिता से पूछो! 🤗 "
        "मैं तुम्हारा **प्रकृति** और **विज्ञान** दोस्त हूँ। "
        "क्या तुम प्रकृति के बारे में कुछ अद्भुत जानना चाहोगे?"
    ),
    "ar": (
        "هذا سؤال رائع لوالديك أو معلميك! 🤗 "
        "أنا صديقك في **الطبيعة** و**العلوم**. "
        "هل تريد استكشاف شيء مذهل في العالم الطبيعي؟"
    ),
    "pt": (
        "Essa é uma pergunta para seus pais ou professores! 🤗 "
        "Eu sou seu amigo da **natureza** e da **ciência**. "
        "Quer explorar algo incrível do mundo natural?"
    ),
    "de": (
        "Das ist eine Frage für deine Eltern oder Lehrer! 🤗 "
        "Ich bin dein **Natur**- und **Wissenschafts**-Freund. "
        "Möchtest du etwas Tolles über die Natur entdecken?"
    ),
    "fr": (
        "C'est une question pour tes parents ou tes profs ! 🤗 "
        "Je suis ton copain **nature** et **sciences**. "
        "Tu veux découvrir quelque chose d'incroyable sur le monde naturel ?"
    ),
}

REDIRECT_FOLLOWUPS = {
    "es": ["¿Cómo viven los delfines?", "¿Por qué brilla el sol?", "¿Qué comen las mariposas?"],
    "en": ["How do dolphins live?", "Why does the sun shine?", "What do butterflies eat?"],
    "zh": ["海豚怎么生活？", "太阳为什么发光？", "蝴蝶吃什么？"],
    "hi": ["डॉल्फिन कैसे रहती हैं?", "सूरज क्यों चमकता है?", "तितलियाँ क्या खाती हैं?"],
    "ar": ["كيف تعيش الدلافين؟", "لماذا تشرق الشمس؟", "ماذا يأكل الفراش؟"],
    "pt": ["Como vivem os golfinhos?", "Por que o sol brilha?", "O que as borboletas comem?"],
    "de": ["Wie leben Delfine?", "Warum leuchtet die Sonne?", "Was fressen Schmetterlinge?"],
    "fr": ["Comment vivent les dauphins ?", "Pourquoi le soleil brille ?", "Que mangent les papillons ?"],
}


def _needs_substring_match(ch: str) -> bool:
    """Scripts where \\b word boundaries don't work: CJK ideographs/kana/
    hangul (no spaces) and Arabic (clitics like ال/و attach to words)."""
    o = ord(ch)
    return (0x3400 <= o <= 0x9FFF or 0x3040 <= o <= 0x30FF      # CJK, kana
            or 0xAC00 <= o <= 0xD7AF                            # hangul
            or 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F    # Arabic
            or 0x08A0 <= o <= 0x08FF                            # Arabic ext
            or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF)   # Arabic pres. forms


# === Evasion-resistant normalization ===
# Catches: accent variants (éxtasis→extasis, Attempted pornô→porno),
# leetspeak (s3x→sex, p0rn→porn), homoglyphs (Cyrillic/Greek lookalikes),
# zero-width chars (s​e​x→sex) and full-width forms.

_LEET_TABLE = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
    "7": "t", "8": "b", "@": "a", "$": "s", "!": "i",
})

_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y",
    "х": "x", "і": "i", "ј": "j", "ѕ": "s", "һ": "h", "ԁ": "d",
    "α": "a", "ε": "e", "ο": "o", "ρ": "p", "τ": "t", "χ": "x",
})

_ZERO_WIDTH_RE = re.compile("[\\u200b\\u200c\\u200d\\u2060\\ufeff]")


def _normalize(text: str) -> str:
    """Normalize text for safety matching: NFKD compatibility, strip
    diacritics, drop zero-width/format chars, homoglyphs → Latin,
    leetspeak → letters, lowercase."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _ZERO_WIDTH_RE.sub("", text).lower()
    return text.translate(_HOMOGLYPHS).translate(_LEET_TABLE)


BLOCKED_TERMS_N = [_normalize(t) for t in BLOCKED_TOPICS]
SENSITIVE_TERMS_N = [_normalize(t) for t in SENSITIVE_PATTERNS]

# Letter-spacing evasion: "s e x", "s-e-x", "s.e.x.o" → joined and checked
# for EXACT membership (never substring) so "Essex"/"farmacia" stay safe.
_SPACED_RUN_RE = re.compile(r"(?:[a-z0-9][\s.\-_*]+){2,}[a-z0-9]")


def _joined_terms(terms):
    return {
        re.sub(r"[^a-z0-9]", "", t)
        for t in terms
        if len(re.sub(r"[^a-z0-9]", "", t)) >= 3
    }


_BLOCKED_JOINED = _joined_terms(BLOCKED_TERMS_N)
_SENSITIVE_JOINED = _joined_terms(SENSITIVE_TERMS_N)


def _has_spaced_term(norm_text: str, joined_set) -> bool:
    """'s e x' style evasion: join letter runs, require exact term match."""
    for run in _SPACED_RUN_RE.findall(norm_text):
        if re.sub(r"[^a-z0-9]", "", run) in joined_set:
            return True
    return False


def _contains_term(text: str, term: str) -> bool:
    """Match a normalized term in normalized text. Boundary-less scripts
    (CJK, Arabic) use substring match; other scripts use \\b prefix match
    (e.g. 'gun' matches 'guns' but not 'segun')."""
    if any(_needs_substring_match(c) for c in term):
        return term in text
    return re.search(r"\b" + re.escape(term), text) is not None


def _is_blocked_topic(text: str) -> bool:
    """Check if the message contains blocked topics for children,
    resistant to accent/leet/homoglyph/spacing evasion."""
    norm = _normalize(text)
    for term in BLOCKED_TERMS_N:
        if _contains_term(norm, term):
            return True
    return _has_spaced_term(norm, _BLOCKED_JOINED)


def _is_sensitive_topic(text: str) -> bool:
    """Check if the message touches sensitive topics needing careful handling."""
    norm = _normalize(text)
    for term in SENSITIVE_TERMS_N:
        if _contains_term(norm, term):
            return True
    return _has_spaced_term(norm, _SENSITIVE_JOINED)


def _response_contains_inappropriate(text: str) -> bool:
    """Post-response check: did the LLM generate inappropriate content?
    Word-boundary matched (congenital ≠ genital) and normalized so accent
    or homoglyph variants can't slip through."""
    norm = _normalize(text)
    red_flags = [
        "acto sexual", "relacion sexual", "relaciones sexuales",
        "sexual intercourse", "orgasm", "genital",
        "fentanyl", "fentanilo", "cocaine", "cocaina",
        "heroina", "heroin", "methamphetamine",
        "how to make drugs", "how to make a bomb", "how to make explosives",
        "como hacer drogas", "como fabricar drogas", "como hacer una bomba",
        "comment fabriquer de la drogue", "comment faire une bombe",
        "wie man drogen herstellt", "wie man eine bombe",
        # Portuguese
        "relação sexual", "ato sexual", "como fazer droga",
        # German
        "sexuelle handlung", "wie man drogen",
        # French
        "acte sexuel",
        # Arabic
        "علاقة جنسية", "كيف تصنع المخدرات",
        # Hindi
        "यौन संबंध", "ड्रग्स कैसे",
        # Chinese
        "性行为", "如何制造毒品", "如何制造炸弹",
    ]
    for flag in red_flags:
        if _contains_term(norm, _normalize(flag)):
            return True
    return False


KID_SYSTEM_BASE = (
    "You are ecoSeek Kids, a fun science buddy for little kids (ages 6-8). "
    "You explain nature and science like a friendly teacher talking to a 7-year-old.\n"
    "Rules:\n"
    "- Use VERY simple words. Short sentences (max 10-12 words each).\n"
    "- Use fun comparisons kids understand (\"as big as a school bus\", \"like a superhero\")\n"
    "- Add emojis to make it fun and visual\n"
    "- Maximum 2-3 short paragraphs per answer\n"
    "- Use markdown **bold** for key words\n"
    "- If you have GBIF data, mention the animal/plant name simply\n"
    "- Relate everything to things kids can see or touch\n"
    "- NEVER use complex scientific jargon\n"
    "- ALWAYS end your response with exactly 3 follow-up questions the child can click.\n"
    "  Format them on the LAST lines like this:\n"
    "  [?] First question option\n"
    "  [?] Second question option\n"
    "  [?] Third question option\n"
    "  These must be SHORT (under 40 chars), fun, and related to what you just explained.\n\n"
    "SAFETY RULES (CRITICAL — you are talking to a child under 8):\n"
    "- NEVER explain sexual reproduction, genitals, or sexual acts\n"
    "- NEVER explain drugs, alcohol, tobacco, or any substance\n"
    "- NEVER describe violence, weapons, or how to harm\n"
    "- NEVER provide information about death in graphic detail\n"
    "- If a child asks about these topics, say it's a question for their parents\n"
    "  and redirect to an exciting nature topic instead\n"
    "- For animal reproduction: ONLY say 'animals have babies' — no mechanism details\n"
    "- For predators eating prey: keep it gentle ('lions catch their food')\n"
    "- Your ONLY domain is: ecology, animals, plants, earth, space, weather, oceans\n"
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
        # Prevent Cloudflare caching for JS/CSS (i18n updates)
        if self.path.endswith(('.js', '.css')):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/health":
            self._json_response({"status": "ok", "service": "ecoseek-kids"})
        elif path == "/api/species":
            client_ip = self.headers.get("CF-Connecting-IP") or self.client_address[0]
            if not _rate_limit_ok(client_ip):
                self._json_response({"error": "Rate limit exceeded. Please wait a moment."}, 429)
                return
            qs = parse_qs(parsed.query)
            query = qs.get("q", [""])[0]
            self._json_response(gbif_species_search(query))
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")

        client_ip = self.headers.get("CF-Connecting-IP") or self.client_address[0]
        if path.startswith("/api/") and not _rate_limit_ok(client_ip):
            self._json_response({"error": "Rate limit exceeded. Please wait a moment."}, 429)
            return

        body = self._read_body()
        if body is None:
            return

        if path == "/api/chat":
            self._handle_chat(body)
        elif path == "/api/species":
            self._json_response(gbif_species_search(
                _short_str(body.get("query")), _clamped_int(body.get("limit"), 5, 1, 50)))
        elif path == "/api/occurrences":
            self._json_response(gbif_occurrences(
                _short_str(body.get("species")), _clamped_int(body.get("limit"), 300, 1, 1000)))
        elif path == "/api/references":
            self._json_response(crossref_search(
                _short_str(body.get("query")), _clamped_int(body.get("limit"), 5, 1, 50)))
        elif path == "/api/report":
            self._json_response(generate_report_outline(
                _short_str(body.get("topic")), _short_str(body.get("species"))))
        else:
            self._json_response({"error": "Not found"}, 404)

    def _handle_chat(self, body):
        try:
            message = body.get("message", "")
            if not isinstance(message, str):
                message = ""
            message = message.strip()
            # Client 'system' is untrusted (prompt-injection vector) —
            # only allowlisted topic labels reach the system prompt.
            topic_system = body.get("system", "")
            if topic_system not in _SAFE_TOPIC_SYSTEMS:
                topic_system = ""
            history = body.get("history", [])
            if not isinstance(history, list):
                history = []
            query_type = body.get("query_type", "chat")  # chat | species | references | report

            language = body.get("language", "en")  # en, es, zh, hi, ar, pt

            if not message:
                self._json_response({"error": "Empty message"}, 400)
                return

            if len(message) > 2000:
                message = message[:2000]

            # Content safety: check blocked topics BEFORE calling LLM
            if _is_blocked_topic(message):
                redirect = REDIRECT_RESPONSES.get(language, REDIRECT_RESPONSES["en"])
                followups = REDIRECT_FOLLOWUPS.get(language, REDIRECT_FOLLOWUPS["en"])
                self._json_response({
                    "response": redirect,
                    "followups": followups,
                    "enriched": False,
                    "filtered": True
                })
                return

            # Language instructions
            lang_map = {
                "en": "English",
                "es": "Spanish (Español)",
                "zh": "Chinese (中文)",
                "hi": "Hindi (हिन्दी)",
                "ar": "Arabic (العربية)",
                "pt": "Portuguese (Português)",
                "de": "German (Deutsch)",
                "fr": "French (Français)"
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

            # Extra guardrail for sensitive topics that passed the blocklist
            if _is_sensitive_topic(message):
                system_prompt += (
                    "\n\nWARNING: The child's question touches a sensitive topic. "
                    "Keep your answer EXTREMELY gentle and age-appropriate for a 7-year-old. "
                    "For reproduction: only say 'animals/plants have babies' — NO details about HOW. "
                    "For death: 'some animals live longer than others' — NO graphic details. "
                    "For poison/venom: 'some animals have special ways to protect themselves' — keep it simple. "
                    "If you cannot answer safely, redirect to a fun nature fact instead."
                )
            if topic_system:
                system_prompt += f"\n\nContexto del tema: {topic_system}"
            if context_parts:
                system_prompt += "\n\nDatos cientificos en tiempo real:\n" + "\n".join(context_parts)
                system_prompt += "\n\nUsa estos datos para enriquecer tu respuesta. Cita las fuentes."

            messages = [{"role": "system", "content": system_prompt}]
            for msg in history[-8:]:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "user")
                if role not in ("user", "assistant"):
                    continue
                content = msg.get("content", "")
                if not isinstance(content, str):
                    continue
                content = content[:1000]
                # Drop any history turn with blocked content — a forged
                # "assistant" turn could otherwise prime unsafe answers.
                if _is_blocked_topic(content):
                    continue
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": message})

            api_payload = {
                "model": OPENROUTER_MODEL,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": 800,
                "top_p": 0.9
            }

            # Cost-optimized provider chain — ALL OpenRouter (no provider caps):
            # 1. OPENROUTER_MODEL (default google/gemini-3.8-flash)
            # 2. upstage/solar-pro4      — cheapest agentic fallback ($0.03/$0.12)
            # 3. google/gemini-3.7-flash — last-resort cheap fallback
            providers = []
            if OPENROUTER_API_KEY:
                providers.append((OPENROUTER_API_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL))
                providers.append((OPENROUTER_API_URL, OPENROUTER_API_KEY, "upstage/solar-pro4"))
                providers.append((OPENROUTER_API_URL, OPENROUTER_API_KEY, "google/gemini-3.7-flash"))
            if MIMO_API_KEY:
                providers.append((MIMO_API_URL, MIMO_API_KEY, MIMO_MODEL))
            if FALLBACK_API_KEY:
                providers.append((FALLBACK_API_URL, FALLBACK_API_KEY, FALLBACK_MODEL))
            reply = _call_llm(api_payload, providers)

            # Post-response safety check: if LLM generated inappropriate content
            if _response_contains_inappropriate(reply):
                redirect = REDIRECT_RESPONSES.get(language, REDIRECT_RESPONSES["en"])
                followups = REDIRECT_FOLLOWUPS.get(language, REDIRECT_FOLLOWUPS["en"])
                self._json_response({
                    "response": redirect,
                    "followups": followups,
                    "enriched": False,
                    "filtered": True
                })
                return

            # Parse follow-up options from response
            followups = []
            clean_reply = []
            for line in reply.split("\n"):
                if line.strip().startswith("[?]"):
                    followups.append(line.strip()[3:].strip())
                else:
                    clean_reply.append(line)

            # Remove trailing empty lines from clean reply
            while clean_reply and not clean_reply[-1].strip():
                clean_reply.pop()

            self._json_response({
                "response": "\n".join(clean_reply),
                "followups": followups[:3],
                "enriched": bool(context_parts)
            })

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
    if not (MIMO_API_KEY or OPENROUTER_API_KEY or FALLBACK_API_KEY):
        print("ERROR: No LLM API key configured (need OPENROUTER_API_KEY, MIMO_API_KEY or FALLBACK_API_KEY)", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer((BIND_HOST, PORT), KidsHandler)
    print(f"ecoSeek Kids v2.1 — Scientific Agent Environment for Ecology")
    print(f"  http://{BIND_HOST}:{PORT}")
    chain = []
    if OPENROUTER_API_KEY:
        chain.append(f"OpenRouter({OPENROUTER_MODEL})")
        chain.append("OpenRouter(upstage/solar-pro4)")
        chain.append("OpenRouter(google/gemini-3.7-flash)")
    if MIMO_API_KEY:
        chain.append(f"MiMo({MIMO_MODEL})")
    if FALLBACK_API_KEY:
        chain.append(f"DeepSeek({FALLBACK_MODEL})")
    print(f"  LLM chain: {' → '.join(chain)}")
    print(f"  GBIF: {GBIF_API}")
    print(f"  CrossRef: {CROSSREF_API}")
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
