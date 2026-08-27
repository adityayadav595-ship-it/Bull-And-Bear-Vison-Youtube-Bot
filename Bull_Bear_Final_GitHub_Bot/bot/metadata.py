from __future__ import annotations

import re

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "your", "from", "into", "how", "what",
    "you", "are", "was", "were", "have", "has", "had", "but", "not", "too", "very", "just",
    "video", "short", "shorts", "trading", "quotex", "viral", "reel", "status"
}

# keyword, display topic, hashtag, primary search phrase
TOPICS = [
    ("rsi", "RSI Trading", "#RSI", "RSI trading strategy for beginners"),
    ("relative strength index", "RSI Trading", "#RSI", "RSI indicator explained"),
    ("macd", "MACD Trading", "#MACD", "MACD trading strategy for beginners"),
    ("moving average convergence", "MACD Trading", "#MACD", "MACD indicator explained"),
    ("ema", "EMA Trading", "#EMA", "EMA trading strategy for beginners"),
    ("moving average", "Moving Average Trading", "#MovingAverage", "moving average trading for beginners"),
    ("bollinger", "Bollinger Bands", "#BollingerBands", "Bollinger Bands strategy for beginners"),
    ("support", "Support and Resistance", "#PriceAction", "support and resistance trading for beginners"),
    ("resistance", "Support and Resistance", "#PriceAction", "support and resistance trading for beginners"),
    ("breakout", "Breakout Trading", "#PriceAction", "breakout trading strategy for beginners"),
    ("candlestick", "Candlestick Trading", "#Candlestick", "candlestick patterns for beginners"),
    ("candle pattern", "Candlestick Trading", "#Candlestick", "candlestick patterns explained"),
    ("price action", "Price Action Trading", "#PriceAction", "price action trading for beginners"),
    ("trendline", "Trendline Trading", "#TechnicalAnalysis", "trendline trading strategy for beginners"),
    ("risk reward", "Risk Reward", "#RiskManagement", "risk reward ratio in trading"),
    ("risk", "Risk Management", "#RiskManagement", "trading risk management for beginners"),
    ("psychology", "Trading Psychology", "#TradingPsychology", "trading psychology for beginners"),
    ("mindset", "Trading Psychology", "#TradingPsychology", "trading psychology for beginners"),
]

CORE_TAGS = [
    "trading education",
    "technical analysis",
    "trading for beginners",
    "chart analysis",
    "price action",
    "risk management",
]

RISK_PATTERNS = [
    r"\b100\s*%\b",
    r"\bguaranteed?\b",
    r"\bsure\s*shot\b",
    r"\brisk[ -]?free\b",
    r"\bno\s*risk\b",
    r"\beasy\s*money\b",
    r"\binstant\s*profit\b",
    r"\bdaily\s*(profit|income|earning)\b",
    r"\bfixed\s*return\b",
    r"\bguaranteed\s*(profit|return|income)\b",
    r"\bwin\s*rate\b",
    r"\bget\s*rich\b",
    r"\bdouble\s*(your\s*)?money\b",
    r"\bsecret\s*strategy\b",
    r"\bfree\s*money\b",
    r"\bwithdrawal\s*proof\b",
    r"\bprofit\s*proof\b",
    r"\bcopy\s*trade\b",
    r"\bvip\s*signals?\b",
    r"\bpromo\s*code\b",
    r"\bdeposit\s*bonus\b",
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
    text = re.sub(r"[^A-Za-z0-9+#% .,_:-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for pattern in RISK_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _detect_topic(source_text: str) -> tuple[str, str, str]:
    lower = source_text.lower()
    for keyword, label, hashtag, search_phrase in TOPICS:
        if keyword in lower:
            return label, hashtag, search_phrase
    return (
        "Technical Analysis",
        "#TechnicalAnalysis",
        "technical analysis for beginners",
    )


def _extract_keywords(text: str, limit: int = 3) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text.lower())
    counts: dict[str, int] = {}
    for word in words:
        if word in STOPWORDS:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts, key=lambda w: (-counts[w], -len(w), w))
    return ranked[:limit]


def _source_context(source_title: str, topic: str) -> str:
    """Keep a short truthful source-specific phrase when useful."""
    clean = re.sub(r"#[A-Za-z0-9_]+", " ", source_title or "")
    clean = re.sub(r"\s+", " ", clean).strip(" -|:,. ")
    if not clean:
        return ""

    # Avoid copying spammy/very long source titles into SEO metadata.
    words = clean.split()
    if len(words) > 7:
        clean = " ".join(words[:7])

    if clean.lower() == topic.lower():
        return ""
    return clean


def _search_title(source_title: str, topic: str, search_phrase: str) -> str:
    context = _source_context(source_title, topic)

    # Put the searchable phrase first; keep the title readable and truthful.
    title = search_phrase.title()
    if context and context.lower() not in title.lower():
        candidate = f"{title} | {context}"
        if len(candidate) <= 87:
            title = candidate

    if "#shorts" not in title.lower():
        title += " #Shorts"
    return title[:95].rstrip(" -|:,. ")


def _search_description(topic: str, search_phrase: str, brand: str, hashtags: list[str]) -> str:
    # First 1-2 lines intentionally describe the same query as the title,
    # without stuffing or repeating the phrase unnaturally.
    return (
        f"Learn {search_phrase} with a quick {topic.lower()} example. "
        f"This {brand} short explains the chart concept in a simple educational format for traders learning technical analysis.\n\n"
        "Educational content only. Not financial advice. Trading involves risk and results are not guaranteed. "
        "Use appropriate risk management and review every setup independently.\n\n"
        + " ".join(hashtags[:3])
    )[:2000]


def build_metadata(info, cfg):
    risk = compliance_reason(info)
    if risk:
        raise ValueError(f"YouTube compliance gate: {risk}")

    source_title = _clean_text(info.get("title", ""))
    source_desc = _clean_text(info.get("description", ""))
    source_text = f"{source_title} {source_desc}".strip()
    brand = cfg.get("brand", "Trading Education Channel")

    topic, topic_hashtag, search_phrase = _detect_topic(source_text)
    title = _search_title(source_title, topic, search_phrase)

    dynamic_keywords = _extract_keywords(source_text)
    tags: list[str] = []
    candidate_tags = [
        search_phrase,
        topic.lower(),
        f"{topic.lower()} for beginners",
        *CORE_TAGS,
        *dynamic_keywords,
    ]
    for tag in candidate_tags:
        tag = _clean_text(tag).lower()
        if tag and tag not in tags:
            tags.append(tag)

    max_tags = int(cfg.get("metadata", {}).get("max_tags", 6))
    tags = tags[:max_tags]

    hashtags = ["#Shorts", "#TradingEducation"]
    if topic_hashtag not in hashtags:
        hashtags.append(topic_hashtag)

    description = _search_description(topic, search_phrase, brand, hashtags)

    print("SEO topic:", topic)
    print("SEO search phrase:", search_phrase)

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": str(cfg.get("metadata", {}).get("category_id", "27")),
    }
