from __future__ import annotations

import re
import time

RELEVANCE_TERMS = {
    "indicator": 5.0, "setup": 4.0, "rsi": 5.0, "macd": 5.0, "ema": 4.5,
    "moving average": 4.0, "bollinger": 5.0, "support": 3.5, "resistance": 3.5,
    "breakout": 3.5, "candlestick": 4.5, "price action": 5.0, "risk management": 5.0,
    "psychology": 3.0, "market structure": 4.5, "trendline": 3.5, "trend": 2.0,
    "liquidity": 4.0, "entry": 2.0, "stop loss": 3.0, "aroon": 5.0,
}
LOW_QUALITY_TERMS = (
    "guaranteed", "100%", "sure shot", "easy money", "instant guaranteed profit",
    "guaranteed profit", "fixed return", "risk-free", "no risk", "vip signal",
    "promo code", "deposit bonus", "free signal", "join telegram",
)
QUOTEX_TERMS = ("quotex", "qxbroker", "binary option", "binary options")
TRADING_TERMS = (
    "trading", "trade", "chart", "candlestick", "indicator", "strategy", "setup",
    "price action", "support", "resistance", "rsi", "macd", "ema", "bollinger",
    "market structure", "trendline", "liquidity", "forex", "entry", "stop loss",
)
LIFESTYLE_TERMS = (
    "car", "cars", "supercar", "lamborghini", "ferrari", "luxury", "lifestyle",
    "jet ski", "jetski", "scuba", "diving", "travel", "model", "fashion", "motivation",
)
GENERIC_TITLE_RE = re.compile(r"^(?:pinterest\s+video(?:\s*#?\d+)?|trading\s+short|viral\s+video|status|reel|video)$", re.I)
TOPIC_RULES = [
    ("indicator", ("indicator", "aroon")),
    ("rsi", ("rsi", "relative strength index")), ("macd", ("macd", "moving average convergence")),
    ("bollinger", ("bollinger",)), ("support-resistance", ("support", "resistance")),
    ("candlestick", ("candlestick", "candle pattern")), ("price-action", ("price action",)),
    ("market-structure", ("market structure", "liquidity")), ("risk", ("risk management", "risk reward", "stop loss")),
    ("psychology", ("psychology", "mindset")), ("ema", ("ema", "moving average")),
    ("breakout", ("breakout",)), ("trend", ("trendline", "trend")),
    ("setup", ("setup", "strategy")),
]


def _number(value, default=0.0):
    try: return float(value or default)
    except (TypeError, ValueError): return float(default)


def _topic(text):
    lower = text.lower()
    for name, terms in TOPIC_RULES:
        if any(term in lower for term in terms): return name
    return "general"


def _content_priority(item):
    text = f"{item.get('title', '')} {item.get('description', '')} {item.get('url', '')}".lower()
    if any(term in text for term in QUOTEX_TERMS):
        return 1, "priority-1:quotex"
    if any(term in text for term in TRADING_TERMS):
        return 2, "priority-2:trading"
    if any(term in text for term in LIFESTYLE_TERMS):
        return 3, "priority-3:lifestyle"
    return 3, "priority-3:other"


def _specificity_score(title, description):
    score, reasons = 0.0, []
    clean_title = re.sub(r"\s+", " ", title).strip()
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]+", clean_title)
    if GENERIC_TITLE_RE.match(clean_title): score -= 8.0; reasons.append("generic-source-title")
    elif len(words) >= 4: score += 3.0; reasons.append("specific-title")
    elif len(words) <= 1: score -= 3.0; reasons.append("thin-title")
    desc_words = re.findall(r"[A-Za-z][A-Za-z0-9-]+", description)
    if len(desc_words) >= 8: score += 2.0; reasons.append("useful-description-context")
    elif not description.strip(): score -= 1.0; reasons.append("missing-description")
    return score, reasons


def score_candidate(item):
    score, reasons = 0.0, []
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    text = f"{title} {description}".lower()
    priority, priority_reason = _content_priority(item)
    reasons.append(priority_reason)
    if priority == 1: score += 100.0
    elif priority == 2: score += 40.0
    else: score += 0.0
    matched = [term for term in RELEVANCE_TERMS if term in text]
    if matched:
        score += min(20.0, sum(RELEVANCE_TERMS[t] for t in matched)); reasons.append("educational-relevance:" + ",".join(matched[:3]))
    else:
        score -= 2.0; reasons.append("generic-context")
    topic = _topic(text)
    if topic in {"indicator", "rsi", "macd", "bollinger", "ema"}:
        score += 6.0; reasons.append("channel-winner:indicator")
    elif topic in {"setup", "price-action", "candlestick", "breakout"}:
        score += 3.0; reasons.append("channel-winner:setup")
    specificity, sr = _specificity_score(title, description); score += specificity; reasons.extend(sr)
    duration = _number(item.get("duration"), 0)
    if duration:
        if 12 <= duration <= 28: score += 9.0; reasons.append("strong-short-duration")
        elif 8 <= duration < 12 or 28 < duration <= 45: score += 6.0; reasons.append("good-short-duration")
        elif 45 < duration <= 60: score += 2.0; reasons.append("longer-short-duration")
        else: score -= 8.0; reasons.append("weak-duration")
    else: score -= 1.0; reasons.append("duration-unknown")
    timestamp = _number(item.get("timestamp"), 0)
    if timestamp > 0:
        age_days = max(0.0, (time.time() - timestamp) / 86400)
        if age_days <= 30: score += 3.0; reasons.append("fresh")
        elif age_days <= 180: score += 1.0; reasons.append("recent")
        elif age_days > 730: score -= 1.0; reasons.append("old-source")
    if "risk" in text or "education" in text or "learn" in text or "strategy" in text:
        score += 2.0; reasons.append("education-context")
    if any(term in text for term in LOW_QUALITY_TERMS):
        score -= 30.0; reasons.append("promotion-risk")
    bonus = min(8.0, max(0.0, _number(item.get("_source_priority_bonus"), 0)))
    if bonus:
        score += bonus; reasons.append(f"preferred-source:+{bonus:g}")
    return round(score, 2), reasons


def rank_candidates(candidates, pool_size=8):
    if not candidates: return []
    ranked = []
    for item in candidates:
        score, reasons = score_candidate(item)
        enriched = dict(item)
        enriched["_smart_score"] = score
        enriched["_smart_reasons"] = reasons
        enriched["_content_priority"] = _content_priority(item)[0]
        enriched["_smart_topic"] = _topic(f"{item.get('title', '')} {item.get('description', '')}")
        ranked.append(enriched)
    # Hard tier order: Quotex first, trading second, lifestyle/other third.
    # Score/freshness only decides order inside each tier.
    ranked.sort(key=lambda x: (int(x.get("_content_priority", 3)), -float(x.get("_smart_score", 0)), -_number(x.get("timestamp"), 0), str(x.get("url") or "")))
    print("Smart policy-safe candidate ranking (Quotex > trading > lifestyle):")
    for idx, item in enumerate(ranked[:5], 1):
        print(f"  {idx}. priority={item.get('_content_priority')} score={item.get('_smart_score')} topic={item.get('_smart_topic', 'general')} duration={item.get('duration', 'unknown')} title={item.get('title', '')[:80]}")
    return ranked


def choose_random(candidates, pool_size=8):
    ranked = rank_candidates(candidates, pool_size=pool_size)
    return ranked[0] if ranked else None
