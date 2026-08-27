from __future__ import annotations

import random
import re

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "your", "from", "into", "how", "what",
    "you", "are", "was", "were", "have", "has", "had", "but", "not", "too", "very", "just",
    "video", "short", "shorts", "trading", "quotex"
}

TOPICS = [
    ("rsi", "RSI", "#RSI"),
    ("macd", "MACD", "#MACD"),
    ("ema", "EMA", "#EMA"),
    ("bollinger", "Bollinger Bands", "#BollingerBands"),
    ("support", "Support and Resistance", "#PriceAction"),
    ("resistance", "Support and Resistance", "#PriceAction"),
    ("breakout", "Breakout Trading", "#PriceAction"),
    ("candlestick", "Candlestick Analysis", "#Candlestick"),
    ("price action", "Price Action", "#PriceAction"),
    ("risk", "Risk Management", "#RiskManagement"),
    ("psychology", "Trading Psychology", "#TradingPsychology"),
    ("mindset", "Trading Psychology", "#TradingPsychology"),
]

SAFE_TITLE_TEMPLATES = [
    "{topic} Explained | Trading Education #Shorts",
    "Understanding {topic} | Trading Education #Shorts",
    "{topic}: A Quick Trading Lesson #Shorts",
    "Learning {topic} | Trading Basics #Shorts",
    "{topic} in Under a Minute | #Shorts",
]

GENERIC_TITLES = [
    "Trading Chart Concept Explained | #Shorts",
    "A Quick Trading Education Lesson | #Shorts",
    "Understanding a Trading Setup | #Shorts",
    "Trading Basics: Reading the Chart | #Shorts",
]

CORE_TAGS = [
    "trading education",
    "technical analysis",
    "price action",
    "risk management",
    "market analysis",
    "chart analysis",
    "trading basics",
    "bull and bear vision",
]

# Metadata phrases that are commonly associated with get-rich-quick claims,
# deceptive investment promotion, fake engagement or off-platform funneling.
RISK_PATTERNS = [
    r"\b100\s*%\b",
    r"\bguaranteed?\b",
    r"\bsure\s*shot\b",
    r"\brisk[ -]?free\b",
    r"\bno\s*risk\b",
    r"\beasy\s*money\b",
    r"\binstant\s*profit\b",
    r"\bdaily\s*profit\b",
    r"\bfixed\s*return\b",
    r"\bguaranteed\s*(profit|return|income)\b",
    r"\bwin\s*rate\b",
    r"\bget\s*rich\b",
    r"\bdouble\s*(your\s*)?money\b",
    r"\bsecret\s*strategy\b",
    r"\bfree\s*money\b",
    r"\bsub\s*(4|for)\s*sub\b",
    r"\blike\s*(4|for)\s*like\b",
    r"\bview\s*(4|for)\s*view\b",
]

OFF_PLATFORM_TERMS = [
    "telegram", "whatsapp", "signal group", "vip group", "dm me", "contact me",
    "join my group", "join our group"
]

FINANCIAL_CTA_TERMS = [
    "profit", "signals", "signal", "deposit", "bonus", "promo code", "trade", "trading"
]


def _raw_source_text(info) -> str:
    return f"{info.get('title', '')} {info.get('description', '')}".strip()


def compliance_reason(info) -> str | None:
    """Return a human-readable reason when source metadata looks policy-risky."""
    raw = _raw_source_text(info)
    lower = raw.lower()

    for pattern in RISK_PATTERNS:
        if re.search(pattern, raw, flags=re.IGNORECASE):
            return f"blocked risky claim/promotion: {pattern}"

    if any(term in lower for term in OFF_PLATFORM_TERMS) and any(
        term in lower for term in FINANCIAL_CTA_TERMS
    ):
        return "blocked off-platform financial promotion/funneling"

    return None


def _clean_text(value: str) -> str:
    text = re.sub(r"https?://\S+", " ", value or "")
    text = re.sub(r"[^A-Za-z0-9+#% ._-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for pattern in RISK_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _detect_topic(source_text: str) -> tuple[str, str]:
    lower = source_text.lower()
    for keyword, label, hashtag in TOPICS:
        if keyword in lower:
            return label, hashtag
    return "Trading Chart Analysis", "#TradingEducation"


def _extract_keywords(text: str, limit: int = 4) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text.lower())
    counts: dict[str, int] = {}
    for word in words:
        if word in STOPWORDS:
            continue
        if any(re.search(pattern, word, flags=re.IGNORECASE) for pattern in RISK_PATTERNS):
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts, key=lambda w: (-counts[w], -len(w), w))
    return ranked[:limit]


def build_metadata(info, cfg):
    risk = compliance_reason(info)
    if risk:
        raise ValueError(f"YouTube compliance gate: {risk}")

    source_title = _clean_text(info.get("title", ""))
    source_desc = _clean_text(info.get("description", ""))
    source_text = f"{source_title} {source_desc}".strip()
    brand = cfg.get("brand", "Bull & Bear Vision")

    topic, topic_hashtag = _detect_topic(source_text)
    if topic == "Trading Chart Analysis":
        title = random.choice(GENERIC_TITLES)
    else:
        title = random.choice(SAFE_TITLE_TEMPLATES).format(topic=topic)

    # Small, relevant tag set only; no keyword stuffing.
    dynamic_keywords = _extract_keywords(source_text)
    tags: list[str] = []
    for tag in [topic.lower()] + CORE_TAGS + dynamic_keywords:
        tag = _clean_text(tag).lower()
        if tag and tag not in tags:
            tags.append(tag)
    max_tags = int(cfg.get("metadata", {}).get("max_tags", 8))
    tags = tags[:max_tags]

    hashtags = ["#Shorts", "#TradingEducation"]
    if topic_hashtag not in hashtags:
        hashtags.append(topic_hashtag)

    description = (
        f"Educational trading short from {brand}.\n\n"
        f"Topic: {topic}. This video is shared for learning and commentary only. "
        "It does not promise profits, guaranteed results, or provide financial advice.\n\n"
        "Trading and investing involve risk. Always do your own research and use appropriate risk management.\n\n"
        + " ".join(hashtags[:3])
    )

    return {
        "title": title[:95],
        "description": description[:2000],
        "tags": tags,
        "category_id": "27",
    }
