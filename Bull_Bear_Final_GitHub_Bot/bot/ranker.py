from __future__ import annotations

import math
import random
import time

RELEVANCE_TERMS = {
    "rsi": 4.0,
    "macd": 4.0,
    "ema": 3.5,
    "bollinger": 4.0,
    "support": 3.0,
    "resistance": 3.0,
    "breakout": 3.0,
    "candlestick": 3.5,
    "price action": 4.0,
    "risk management": 4.0,
    "psychology": 2.5,
    "market structure": 3.5,
    "trend": 2.0,
}

LOW_QUALITY_TERMS = (
    "guaranteed",
    "100%",
    "sure shot",
    "easy money",
    "instant profit",
    "daily profit",
)


def _number(value, default=0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return float(default)


def score_candidate(item: dict) -> tuple[float, list[str]]:
    """Quality/relevance score. Views help a little but never decide eligibility."""
    score = 0.0
    reasons: list[str] = []

    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    text = f"{title} {description}".lower()

    matched = [term for term in RELEVANCE_TERMS if term in text]
    if matched:
        relevance = min(12.0, sum(RELEVANCE_TERMS[t] for t in matched))
        score += relevance
        reasons.append("relevant:" + ",".join(matched[:3]))
    else:
        score += 1.0
        reasons.append("generic-trading")

    duration = _number(item.get("duration"), 0)
    if duration:
        if 15 <= duration <= 45:
            score += 7.0
            reasons.append("ideal-duration")
        elif 8 <= duration <= 60:
            score += 4.0
            reasons.append("shorts-duration")
        else:
            score -= 8.0
            reasons.append("weak-duration")
    else:
        score += 1.0
        reasons.append("duration-unknown")

    # Light engagement signal only. Personal/approved sources with 0/unknown views
    # remain fully eligible.
    views = max(0.0, _number(item.get("view_count"), 0))
    likes = max(0.0, _number(item.get("like_count"), 0))
    if views:
        score += min(4.0, math.log10(views + 1))
        reasons.append("has-view-signal")
    if likes:
        score += min(3.0, math.log10(likes + 1))
        reasons.append("has-like-signal")

    timestamp = _number(item.get("timestamp"), 0)
    if timestamp > 0:
        age_days = max(0.0, (time.time() - timestamp) / 86400)
        if age_days <= 30:
            score += 4.0
            reasons.append("fresh")
        elif age_days <= 180:
            score += 2.0
            reasons.append("recent")

    if 12 <= len(title) <= 90:
        score += 2.0
        reasons.append("clear-title")
    elif not title:
        score -= 2.0
        reasons.append("missing-title")

    if any(term in text for term in LOW_QUALITY_TERMS):
        score -= 20.0
        reasons.append("promo-risk")

    return round(score, 2), reasons


def rank_candidates(candidates: list[dict], pool_size: int = 8) -> list[dict]:
    if not candidates:
        return []

    ranked: list[dict] = []
    for item in candidates:
        score, reasons = score_candidate(item)
        enriched = dict(item)
        enriched["_smart_score"] = score
        enriched["_smart_reasons"] = reasons
        ranked.append(enriched)

    ranked.sort(
        key=lambda x: (
            x.get("_smart_score", 0),
            _number(x.get("timestamp"), 0),
        ),
        reverse=True,
    )

    # Keep a little variety: shuffle only among near-equal top candidates,
    # never across the whole pool.
    top_n = max(1, min(int(pool_size or 8), len(ranked)))
    head, tail = ranked[:top_n], ranked[top_n:]
    if len(head) > 1:
        best = head[0].get("_smart_score", 0)
        close = [x for x in head if best - x.get("_smart_score", 0) <= 1.5]
        rest = [x for x in head if x not in close]
        random.shuffle(close)
        head = close + rest

    print("Smart candidate ranking:")
    for idx, item in enumerate(head[:5], start=1):
        print(
            f"  {idx}. score={item.get('_smart_score')} "
            f"duration={item.get('duration', 'unknown')} "
            f"views={item.get('view_count', 'unknown')} "
            f"title={item.get('title', '')[:80]}"
        )

    return head + tail


def choose_random(candidates: list[dict], pool_size: int = 8) -> dict | None:
    """Backward-compatible entry point: choose from smart-ranked candidates."""
    ranked = rank_candidates(candidates, pool_size=pool_size)
    if not ranked:
        return None
    picked = ranked[0]
    print("Smart unseen video selected")
    print("Score:", picked.get("_smart_score"))
    print("Reasons:", ", ".join(picked.get("_smart_reasons") or []))
    print("URL:", picked.get("url", ""))
    return picked
