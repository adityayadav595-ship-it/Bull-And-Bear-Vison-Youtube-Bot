\
from __future__ import annotations
import re

EDU_WORDS = {
    "indicator","strategy","tutorial","how to","rsi","macd","bollinger","aroon",
    "ema","sma","price action","candlestick","support","resistance","trend",
    "signal","setup","analysis","chart","entry","technical analysis"
}
LIFESTYLE_WORDS = {
    "lifestyle","motivation","pov","money","success","grind","luxury","hustle",
    "mindset","trader life","dream","goal"
}

BASE_TAGS = [
    "trading shorts","trading","trader","trading motivation","trader lifestyle",
    "forex trading","technical analysis","price action","day trading",
    "trading for beginners","financial markets","bull and bear vision"
]

def clean_text(s: str) -> str:
    s = re.sub(r"https?://\S+", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _contains(text: str, words: set[str]) -> bool:
    t = text.lower()
    return any(w in t for w in words)

def classify(text: str, cfg: dict) -> tuple[str, str]:
    md = cfg.get("metadata",{})
    if _contains(text, EDU_WORDS):
        return "education", str(md.get("education_category_id","27"))
    if _contains(text, LIFESTYLE_WORDS):
        return "lifestyle", str(md.get("default_category_id","22"))
    return "trading", str(md.get("default_category_id","22"))

def extract_keywords(text: str) -> list[str]:
    t = clean_text(text).lower()
    known = [
        "aroon indicator","bollinger bands","rsi","macd","ema","price action",
        "candlestick","support resistance","forex","quotex","trading strategy",
        "technical analysis","day trading","trader lifestyle","trading motivation"
    ]
    return [k for k in known if k in t]

def build_metadata(info: dict, cfg: dict) -> dict:
    raw_title = clean_text(info.get("title",""))
    raw_desc = clean_text(info.get("description",""))
    combined = f"{raw_title} {raw_desc}"
    kind, category_id = classify(combined, cfg)
    keys = extract_keywords(combined)
    brand = cfg.get("brand","Bull & Bear Vision")

    if kind == "education":
        main = keys[0].title() if keys else "Trading Strategy"
        title = f"{main} Explained Fast 📈🔥 #shorts"
        lead = f"Quick breakdown of {main.lower()} with a simple trading example."
        hashtags = [
            "#shorts","#trading","#tradingstrategy","#technicalanalysis",
            "#priceaction","#forextrading","#tradingtips","#daytrading",
            "#trader","#tradingeducation"
        ]
    elif kind == "lifestyle":
        title = "POV: When The Grind Finally Pays Off 💸📈 #shorts"
        lead = "Trader lifestyle, discipline, patience and consistency."
        hashtags = [
            "#shorts","#trading","#traderlife","#tradingmotivation",
            "#tradinglifestyle","#motivation","#successmindset","#forextrading",
            "#money","#financialfreedom"
        ]
    else:
        title = "Trading Setup You Need to See 📈🔥 #shorts"
        lead = "A quick trading clip focused on charts, setups and market discipline."
        hashtags = [
            "#shorts","#trading","#forextrading","#priceaction",
            "#technicalanalysis","#trader","#daytrading","#tradingtips"
        ]

    disclaimer = (
        "⚠️ Educational/entertainment content only. Trading involves financial risk. "
        "No strategy or indicator guarantees profit."
    )
    description = f"{lead}\n\nMore trading content from {brand}.\n\n{disclaimer}\n\n" + " ".join(hashtags)

    tags = []
    for k in keys + BASE_TAGS:
        if k not in tags:
            tags.append(k)
    max_tags = int(cfg.get("metadata",{}).get("max_tags",18))
    tags = tags[:max_tags]

    # Keep title comfortably under YouTube's limit.
    title = title[:95].strip()

    return {
        "title": title,
        "description": description[:4900],
        "tags": tags,
        "category_id": category_id,
        "kind": kind,
    }
