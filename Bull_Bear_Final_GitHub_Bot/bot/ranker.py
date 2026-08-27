from __future__ import annotations

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
    "risk management": 5.0,
    "psychology": 3.0,
    "market structure": 4.0,
    "trend": 2.0,
}

LOW_QUALITY_TERMS = (
    "guaranteed",
    "100%",
    "sure shot",
    "easy money",
    "instant profit",
    "daily profit",
    "withdrawal proof",
    "profit proof",
    "vip signal",
    "promo code",
    "deposit bonus",
)


def _number(value, default=0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return float(default)


def score_candidate(item: dict) -> tuple[float, list[str]]:
    """Deterministic educational quality/relevance score; engagement metrics are ignored."""
    score = 0.0
    reasons: list[str] = []

    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    text = f"{title} {description}".lower()

    matched = [term for term in RELEVANCE_TERMS if term in text]
    if matched:
        relevance = min(14.0, sum(RELEVANCE_TERMS[t] for t in matched))
        score += relevance
        reasons.append("educational-relevance:" + ",".join(matched[:3]))
    else:
        score += 1.0
        reasons.append("generic-trading")

    duration = _number(item.get("duration"), 0)
    if duration:
        if 15 <= duration <= 45:
            score += 7.0
            reasons.append("clear-short-duration")
        elif 8 <= duration <= 60:
            score += 4.0
            reasons.append("allowed-short-duration")
        else:
            score -= 8.0
            reasons.append("weak-duration")
    else:
        reasons.append("duration-unknown")

    timestamp = _number(item.get("timestamp"), 0)
    if timestamp > 0:
        age_days = max(0.0, (time.time() - timestamp) / 86400)
        if age_days <= 30:
            score += 2.0
            reasons.append("fresh")
        elif age_days <= 180:
            score += 1.0
            reasons.append("recent")

    if 12 <= len(title) <= 90:
        score += 2.0
        reasons.append("clear-title")
    elif not title:
        score -= 2.0
        reasons.append("missing-title")

    if "risk" in text or "education" in text or "learn" in text:
        score += 2.0
        reasons.append("education-or-risk-context")

    if any(term in text for term in LOW_QUALITY_TERMS):
        score -= 25.0
        reasons.append("promotion-risk")

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

    # Fully deterministic and auditable: quality score, freshness, then URL.
    ranked.sort(
        key=lambda x: (
            -float(x.get("_smart_score", 0)),
            -_number(x.get("timestamp"), 0),
            str(x.get("url") or ""),
        )
    )

    top_n = max(1, min(int(pool_size or 8), len(ranked)))
    head = ranked[:top_n]

    print("Policy-safe candidate ranking:")
    for idx, item in enumerate(head[:5], start=1):
        print(
            f"  {idx}. score={item.get('_smart_score')} "
            f"duration={item.get('duration', 'unknown')} "
            f"title={item.get('title', '')[:80]}"
        )

    return ranked


def choose_random(candidates: list[dict], pool_size: int = 8) -> dict | None:
    """Backward-compatible entry point; selection is now deterministic."""
    ranked = rank_candidates(candidates, pool_size=pool_size)
    if not ranked:
        return None
    picked = ranked[0]
    print("Top policy-safe unseen video selected")
    print("Score:", picked.get("_smart_score"))
    print("Reasons:", ", ".join(picked.get("_smart_reasons") or []))
    print("URL:", picked.get("url", ""))
    return picked
