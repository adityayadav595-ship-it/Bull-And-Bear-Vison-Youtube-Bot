from __future__ import annotations

import hashlib
import re

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "your", "from", "into", "how", "what",
    "you", "are", "was", "were", "have", "has", "had", "but", "not", "too", "very", "just",
    "video", "short", "shorts", "trading", "quotex", "viral", "reel", "status", "pinterest", "pin"
}

SOURCE_PLATFORM_RE = re.compile(
    r"\b(?:pinterest(?:\s+(?:video|pin|reel))?|pin\.it|source\s+video|downloaded\s+video)\b",
    re.IGNORECASE,
)

TOPICS = [
    ("rsi", "RSI Trading", "#RSI", "RSI trading strategy"),
    ("relative strength index", "RSI Trading", "#RSI", "RSI indicator"),
    ("macd", "MACD Trading", "#MACD", "MACD trading strategy"),
    ("moving average convergence", "MACD Trading", "#MACD", "MACD indicator"),
    ("ema", "EMA Trading", "#EMA", "EMA trading strategy"),
    ("moving average", "Moving Average Trading", "#MovingAverage", "moving average trading"),
    ("bollinger", "Bollinger Bands", "#BollingerBands", "Bollinger Bands strategy"),
    ("support", "Support and Resistance", "#PriceAction", "support and resistance"),
    ("resistance", "Support and Resistance", "#PriceAction", "support and resistance"),
    ("breakout", "Breakout Trading", "#PriceAction", "breakout trading strategy"),
    ("candlestick", "Candlestick Trading", "#Candlestick", "candlestick patterns"),
    ("candle pattern", "Candlestick Trading", "#Candlestick", "candlestick patterns"),
    ("price action", "Price Action Trading", "#PriceAction", "price action trading"),
    ("trendline", "Trendline Trading", "#TechnicalAnalysis", "trendline trading"),
    ("risk reward", "Risk Reward", "#RiskManagement", "risk reward ratio"),
    ("risk", "Risk Management", "#RiskManagement", "trading risk management"),
    ("psychology", "Trading Psychology", "#TradingPsychology", "trading psychology"),
    ("mindset", "Trading Psychology", "#TradingPsychology", "trading mindset"),
]

CORE_TAGS = ["trading education", "technical analysis", "trading for beginners", "chart analysis", "price action", "risk management"]

RISK_PATTERNS = [
    r"\b100\s*%\b", r"\bguaranteed?\b", r"\bsure\s*shot\b", r"\brisk[ -]?free\b",
    r"\bno\s*risk\b", r"\beasy\s*money\b", r"\binstant\s*profit\b", r"\bdaily\s*(profit|income|earning)\b",
    r"\bfixed\s*return\b", r"\bguaranteed\s*(profit|return|income)\b", r"\bwin\s*rate\b", r"\bget\s*rich\b",
    r"\bdouble\s*(your\s*)?money\b", r"\bsecret\s*strategy\b", r"\bfree\s*money\b", r"\bwithdrawal\s*proof\b",
    r"\bprofit\s*proof\b", r"\bcopy\s*trade\b", r"\bvip\s*signals?\b", r"\bpromo\s*code\b", r"\bdeposit\s*bonus\b",
    r"\bsub\s*(4|for)\s*sub\b", r"\blike\s*(4|for)\s*like\b", r"\bview\s*(4|for)\s*view\b",
]
OFF_PLATFORM_TERMS = ["telegram", "whatsapp", "signal group", "vip group", "dm me", "contact me", "join my group", "join our group"]
FINANCIAL_CTA_TERMS = ["profit", "signals", "signal", "deposit", "bonus", "promo code", "trade", "trading"]


def _raw_source_text(info):
    return f"{info.get('title', '')} {info.get('description', '')}".strip()


def compliance_reason(info):
    raw = _raw_source_text(info)
    lower = raw.lower()
    for pattern in RISK_PATTERNS:
        if re.search(pattern, raw, flags=re.IGNORECASE):
            return f"blocked risky claim/promotion: {pattern}"
    if any(term in lower for term in OFF_PLATFORM_TERMS) and any(term in lower for term in FINANCIAL_CTA_TERMS):
        return "blocked off-platform financial promotion/funneling"
    return None


def _clean_text(value):
    text = re.sub(r"https?://\S+", " ", value or "")
    text = SOURCE_PLATFORM_RE.sub(" ", text)
    text = re.sub(r"[^A-Za-z0-9+#% .,_:-]+", " ", text)
    for pattern in RISK_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" -|:,. ")


def _detect_topic(text):
    lower = text.lower()
    for keyword, label, hashtag, phrase in TOPICS:
        if keyword in lower:
            return label, hashtag, phrase
    return "Technical Analysis", "#TechnicalAnalysis", "technical analysis"


def _extract_keywords(text, limit=3):
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text.lower())
    counts = {}
    for word in words:
        if word not in STOPWORDS:
            counts[word] = counts.get(word, 0) + 1
    return sorted(counts, key=lambda w: (-counts[w], -len(w), w))[:limit]


def _context(source_title, topic):
    clean = re.sub(r"#[A-Za-z0-9_]+", " ", source_title or "")
    clean = SOURCE_PLATFORM_RE.sub(" ", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" -|:,. ")
    words = clean.split()[:6]
    clean = " ".join(words)
    return "" if clean.lower() == topic.lower() else clean


def _variant(seed, options):
    idx = int(hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:8], 16) % len(options)
    return options[idx]


def _title(source_title, topic, phrase):
    context = _context(source_title, topic)
    seed = source_title + topic
    templates = [
        f"{topic}: What Traders Should Notice",
        f"Watch This {topic} Setup Carefully",
        f"{phrase.title()} Explained Simply",
        f"Can You Spot This {topic} Setup?",
        f"A Quick {topic} Lesson for Traders",
        f"Don't Miss This {topic} Detail",
    ]
    title = _variant(seed, templates)
    if context and len(context) >= 5:
        candidate = f"{title} | {context}"
        if len(candidate) <= 88:
            title = candidate
    title = SOURCE_PLATFORM_RE.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip(" -|:,. ")
    return (title + " #Shorts")[:95].rstrip(" -|:,. ")


def _description(topic, phrase, brand, hashtags, seed):
    intros = [
        f"A quick look at {phrase} and the chart detail traders should understand.",
        f"Learn the key idea behind {phrase} with this short chart example.",
        f"See how {topic.lower()} can be read on a chart in a simple educational example.",
        f"One quick {topic.lower()} concept to add to your technical-analysis study routine.",
    ]
    intro = _variant(seed + "desc", intros)
    text = (
        f"{intro}\n\n"
        f"{brand} shares short trading-education examples focused on chart reading, technical analysis and risk awareness.\n\n"
        "Educational content only — not financial advice. Trading involves risk; evaluate setups independently and use appropriate risk management.\n\n"
        + " ".join(hashtags[:3])
    )
    return SOURCE_PLATFORM_RE.sub(" ", text)[:2000]


def build_metadata(info, cfg):
    risk = compliance_reason(info)
    if risk:
        raise ValueError(f"YouTube compliance gate: {risk}")
    source_title = _clean_text(info.get("title", ""))
    source_desc = _clean_text(info.get("description", ""))
    source_text = f"{source_title} {source_desc}".strip()
    brand = cfg.get("brand", "Trading Education Channel")
    topic, topic_hashtag, phrase = _detect_topic(source_text)
    title = _title(source_title, topic, phrase)
    dynamic = _extract_keywords(source_text)
    tags = []
    for tag in [phrase, topic.lower(), *dynamic, *CORE_TAGS]:
        tag = _clean_text(tag).lower()
        if tag and tag not in tags:
            tags.append(tag)
    tags = tags[:int(cfg.get("metadata", {}).get("max_tags", 6))]
    hashtags = ["#Shorts", topic_hashtag, "#TradingEducation"]
    description = _description(topic, phrase, brand, hashtags, source_text)
    print("SEO topic:", topic)
    print("SEO title:", title)
    print("SEO hashtags:", " ".join(hashtags))
    return {"title": title, "description": description, "tags": tags, "category_id": str(cfg.get("metadata", {}).get("category_id", "27"))}
