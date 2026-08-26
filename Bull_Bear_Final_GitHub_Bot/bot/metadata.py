from __future__ import annotations

import random
import re

STOPWORDS = {
    "the","and","for","with","this","that","your","from","into","how","what",
    "you","are","was","were","have","has","had","but","not","too","very","just",
    "video","short","shorts","trading","quotex"
}

CORE_TAGS = [
    "quotex","trading","trading shorts","forex trading","day trading",
    "technical analysis","price action","trading strategy","trader",
    "candlestick trading","market analysis","trading for beginners",
    "trading psychology","risk management","bull and bear vision"
]

HOOK_TITLES = {
    "strategy": [
        "This Trading Setup Is Too Clean 📈🔥 #shorts",
        "A Simple Trading Setup Traders Miss 👀📊 #shorts",
        "Watch This Setup Before Your Next Trade 🔥📈 #shorts",
        "Clean Entry Setup Explained Fast ⚡📊 #shorts",
    ],
    "indicator": [
        "This Indicator Setup Looks Powerful 📈⚡ #shorts",
        "One Trading Indicator Setup Worth Watching 👀 #shorts",
        "Indicator + Price Action = Clean Setup 🔥 #shorts",
    ],
    "lifestyle": [
        "POV: Trader Life Hits Different 💸📈 #shorts",
        "The Trading Lifestyle Everyone Talks About 🔥 #shorts",
        "Trader Mindset > Everything 📈🧠 #shorts",
    ],
    "generic": [
        "Live Trading Setup You Need to See 📈🔥 #shorts",
        "This Trading Moment Is Wild 👀📊 #shorts",
        "One Chart. One Setup. Full Focus. 🔥📈 #shorts",
        "Trading Setup Worth Watching Till The End 👀 #shorts",
    ],
}

HASHTAG_GROUPS = {
    "strategy": [
        "#shorts","#trading","#quotex","#tradingstrategy","#priceaction",
        "#technicalanalysis","#forextrading","#daytrading","#tradingtips"
    ],
    "indicator": [
        "#shorts","#trading","#quotex","#tradingindicator","#technicalanalysis",
        "#priceaction","#forextrading","#daytrading","#trader"
    ],
    "lifestyle": [
        "#shorts","#trading","#quotex","#traderlife","#tradingmotivation",
        "#tradinglifestyle","#forextrading","#mindset","#trader"
    ],
    "generic": [
        "#shorts","#trading","#quotex","#forextrading","#priceaction",
        "#technicalanalysis","#daytrading","#trader","#tradingvideo"
    ],
}


def _clean_text(s: str) -> str:
    s = re.sub(r"https?://\S+", " ", s or "")
    s = re.sub(r"[^A-Za-z0-9+# ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#-]{2,}", text.lower())
    counts = {}
    for w in words:
        if w in STOPWORDS:
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts, key=lambda w: (-counts[w], -len(w), w))
    return ranked[:limit]


def _classify(text: str) -> str:
    t = text.lower()
    indicator_words = ["rsi","macd","ema","bollinger","indicator","aroon","stochastic"]
    strategy_words = ["strategy","setup","entry","support","resistance","breakout","price action","candlestick","analysis"]
    lifestyle_words = ["lifestyle","motivation","money","success","grind","luxury","mindset","trader life","pov"]

    if any(w in t for w in indicator_words):
        return "indicator"
    if any(w in t for w in strategy_words):
        return "strategy"
    if any(w in t for w in lifestyle_words):
        return "lifestyle"
    return "generic"


def build_metadata(info, cfg):
    source_title = _clean_text(info.get("title", ""))
    source_desc = _clean_text(info.get("description", ""))
    source_text = f"{source_title} {source_desc}".strip()
    brand = cfg.get("brand", "Bull & Bear Vision")

    content_type = _classify(source_text)
    title = random.choice(HOOK_TITLES[content_type])

    dynamic_keywords = _extract_keywords(source_text)
    tags = []
    for tag in CORE_TAGS + dynamic_keywords:
        if tag and tag not in tags:
            tags.append(tag)

    max_tags = int(cfg.get("metadata", {}).get("max_tags", 18))
    tags = tags[:max_tags]

    hashtags = HASHTAG_GROUPS[content_type][:8]

    if content_type in {"strategy", "indicator"}:
        hook = "Quick breakdown of a trading setup, chart logic and market structure."
        category = "27"
    elif content_type == "lifestyle":
        hook = "Trader mindset, discipline and the lifestyle behind the charts."
        category = "22"
    else:
        hook = "A fast trading clip focused on charts, setups and execution."
        category = "22"

    source_hint = ""
    if source_title and source_title.lower() not in {"trading short", "trading shorts"}:
        source_hint = f"\n\nTopic: {source_title[:120]}"

    description = (
        f"{hook}"
        f"{source_hint}\n\n"
        f"More trading content from {brand}.\n\n"
        "⚠️ Educational/entertainment content only. Trading involves financial risk. "
        "No setup, strategy or indicator guarantees profit.\n\n"
        + " ".join(hashtags)
    )

    return {
        "title": title[:95],
        "description": description[:4900],
        "tags": tags,
        "category_id": category,
    }
