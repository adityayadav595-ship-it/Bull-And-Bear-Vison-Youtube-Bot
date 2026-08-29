from __future__ import annotations

import hashlib
import re

STOPWORDS={"the","and","for","with","this","that","your","from","into","how","what","you","are","was","were","have","has","had","but","not","too","very","just","video","short","shorts","trading","quotex","viral","reel","status","pinterest","pin","setup"}
SOURCE_PLATFORM_RE=re.compile(r"\b(?:pinterest(?:\s+(?:video|pin|reel))?|pin\.it|source\s+video|downloaded\s+video)\b",re.I)
TOPICS=[
("aroon","Aroon Indicator","#AroonIndicator","Aroon indicator"),("rsi","RSI","#RSI","RSI indicator"),("relative strength index","RSI","#RSI","RSI indicator"),("macd","MACD","#MACD","MACD indicator"),("ema","EMA","#EMA","EMA strategy"),("moving average","Moving Average","#MovingAverage","moving average"),("bollinger","Bollinger Bands","#BollingerBands","Bollinger Bands"),("support","Support & Resistance","#PriceAction","support and resistance"),("resistance","Support & Resistance","#PriceAction","support and resistance"),("breakout","Breakout","#PriceAction","breakout setup"),("candlestick","Candlestick","#Candlestick","candlestick pattern"),("candle pattern","Candlestick","#Candlestick","candlestick pattern"),("price action","Price Action","#PriceAction","price action"),("trendline","Trendline","#TechnicalAnalysis","trendline setup"),("risk reward","Risk vs Reward","#RiskManagement","risk reward"),("risk","Risk Management","#RiskManagement","risk management"),("psychology","Trading Psychology","#TradingPsychology","trading psychology"),("mindset","Trader Mindset","#TradingPsychology","trader mindset"),("patience","Trading Patience","#TradingPsychology","trading patience"),("discipline","Trading Discipline","#TradingPsychology","trading discipline")]
CORE_TAGS=["quotex","quotex trading","trading strategy","technical analysis","trading education"]
TOPIC_TAGS={"Aroon Indicator":["aroon indicator","quotex indicator"],"RSI":["rsi strategy","rsi indicator"],"MACD":["macd strategy","macd indicator"],"EMA":["ema strategy","ema indicator"],"Moving Average":["moving average strategy"],"Bollinger Bands":["bollinger bands strategy"],"Support & Resistance":["support and resistance","price action trading"],"Breakout":["breakout strategy","price action trading"],"Candlestick":["candlestick patterns","candlestick trading"],"Price Action":["price action trading","price action strategy"],"Trendline":["trendline strategy"],"Risk vs Reward":["risk reward trading"],"Risk Management":["trading risk management"],"Trading Psychology":["trading psychology"],"Trader Mindset":["trader mindset"],"Trading Patience":["trading psychology"],"Trading Discipline":["trading discipline"],"Trading Setup":["trading setup","quotex setup"]}
RISK_PATTERNS=[r"\b100\s*%\s*(?:guaranteed|sure|win(?:ning)?|profit|returns?)\b",r"\bguaranteed?\s+(?:profit|return|income|winning|win)\b",r"\b(?:profit|return|income)\s+guarantee(?:d)?\b",r"\bsure\s*shot\b",r"\brisk[ -]?free\b",r"\bno\s*risk\b",r"\beasy\s*money\b",r"\binstant\s+guaranteed\s+profit\b",r"\bfixed\s*return\b",r"\bget\s*rich\s*quick\b",r"\bdouble\s*(?:your\s*)?money\b",r"\bfree\s*money\b",r"\bvip\s*signals?\b",r"\bpromo\s*code\b",r"\bdeposit\s*bonus\b",r"\bsub\s*(4|for)\s*sub\b",r"\blike\s*(4|for)\s*like\b",r"\bview\s*(4|for)\s*view\b"]
OFF_PLATFORM_TERMS=["telegram","whatsapp","signal group","vip group","dm me","contact me","join my group","join our group"]
FINANCIAL_CTA_TERMS=["profit","signals","signal","deposit","bonus","promo code","trade","trading"]

def _raw_source_text(info): return f"{info.get('title','')} {info.get('description','')}".strip()
def compliance_reason(info):
    raw=_raw_source_text(info); lower=raw.lower()
    for pattern in RISK_PATTERNS:
        if re.search(pattern,raw,re.I): return f"blocked risky claim/promotion: {pattern}"
    if any(x in lower for x in OFF_PLATFORM_TERMS) and any(x in lower for x in FINANCIAL_CTA_TERMS): return "blocked off-platform financial promotion/funneling"
    return None

def _clean_text(value):
    text=re.sub(r"https?://\S+"," ",value or ""); text=SOURCE_PLATFORM_RE.sub(" ",text); text=re.sub(r"[^A-Za-z0-9+#% .,_:-]+"," ",text)
    for pattern in RISK_PATTERNS: text=re.sub(pattern," ",text,flags=re.I)
    return re.sub(r"\s+"," ",text).strip(" -|:,. ")
def _detect_topic(text):
    lower=text.lower()
    for keyword,label,hashtag,phrase in TOPICS:
        if keyword in lower:return label,hashtag,phrase
    return "Trading Setup","#Trading","trading setup"
def _extract_keywords(text,limit=3):
    words=re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}",text.lower()); counts={}
    for word in words:
        if word not in STOPWORDS:counts[word]=counts.get(word,0)+1
    return sorted(counts,key=lambda w:(-counts[w],-len(w),w))[:limit]
def _variant(seed,options):return options[int(hashlib.sha256(seed.encode("utf-8",errors="ignore")).hexdigest()[:8],16)%len(options)]
def _context(source_title):
    clean=re.sub(r"#[A-Za-z0-9_]+"," ",source_title or ""); clean=SOURCE_PLATFORM_RE.sub(" ",clean); clean=re.sub(r"\s+"," ",clean).strip(" -|:,. ")
    words=[]
    for word in clean.split():
        if not words or word.lower()!=words[-1].lower(): words.append(word)
    return " ".join(words[:7])
def _title(source_title,topic,phrase,unique_seed):
    context=_context(source_title)
    if topic=="Trading Setup":
        hooks=["POV: Trading Is Harder Than It Looks","One Chart. One Decision. Stay Disciplined.","What Would You Notice First on This Chart?","A Trading Moment Every Trader Understands","Read the Chart Before You Read the Result","Patience Matters More Than the Entry","The Chart Looks Simple Until Money Is Involved","Trader POV: Focus on the Process","Would You Take This Trade or Wait?","Trading Psychology in One Short Clip"]
    else:
        hooks=[f"{topic}: The Detail Most Traders Miss",f"Can You Spot the {topic} Signal Here?",f"This {topic} Example Is Worth Studying",f"Quick {topic} Lesson From the Chart",f"One {topic} Detail Traders Often Ignore",f"Trader POV: Watch This {topic} Moment",f"{topic} in Seconds: What Matters Here",f"Before the Entry, Notice This {topic} Detail",f"A Cleaner Way to Read {topic}",f"This Is What {phrase.title()} Looks Like"]
    title=_variant(unique_seed+"|hook",hooks)
    generic_context=context.lower() in {"trading setup","quotex trading setup","quotex strategy","technical analysis"}
    if context and not generic_context and len(context)>=10 and len(context)<=48 and _variant(unique_seed+"|ctx",[True,False,False,False]):
        candidate=f"{context} | {topic}"
        if len(candidate)<=78:title=candidate
    title=SOURCE_PLATFORM_RE.sub(" ",title); title=re.sub(r"\b(\w+)(?:\s+\1\b)+",r"\1",title,flags=re.I); title=re.sub(r"\s+"," ",title).strip(" -|:,. ")
    for pattern in RISK_PATTERNS:title=re.sub(pattern,"",title,flags=re.I)
    return re.sub(r"\s+"," ",title).strip(" -|:,. ")[:88]
def _description(topic,phrase,brand,hashtags,seed):
    if topic=="Trading Setup":
        intros=["A quick trading moment about patience, discipline and reading the chart before acting.","Trading is not only about entries — discipline and decision-making matter too.","A short market clip for traders who enjoy chart analysis and trading psychology.","Study the chart, manage risk and focus on the process rather than chasing outcomes."]
    else:
        intros=[f"A quick {phrase} example — watch the chart and identify the key detail for yourself.",f"This short highlights a {topic.lower()} concept traders can study on the chart.",f"Watch the {phrase} moment and focus on how the chart develops.",f"A compact {topic.lower()} example for technical-analysis practice."]
    intro=_variant(seed+"|desc",intros)
    seo_line=f"Topics: {phrase}, technical analysis, chart reading, trading education and risk awareness."
    return SOURCE_PLATFORM_RE.sub(" ",f"{intro}\n\n{seo_line}\n\n{brand} — educational trading content only. Not financial advice. Trading involves risk; profits are never guaranteed.\n\n"+" ".join(hashtags[:3]))[:2000]
def build_metadata(info,cfg):
    risk=compliance_reason(info)
    if risk:raise ValueError(f"YouTube compliance gate: {risk}")
    source_title=_clean_text(info.get("title","")); source_desc=_clean_text(info.get("description","")); source_text=f"{source_title} {source_desc}".strip(); brand=cfg.get("brand","Trading Education Channel"); topic,topic_hashtag,phrase=_detect_topic(source_text)
    unique_seed="|".join([str(info.get("id") or ""),str(info.get("url") or ""),source_text,topic]); title=_title(source_title,topic,phrase,unique_seed); dynamic=_extract_keywords(source_text); tags=[]
    for tag in [phrase,*TOPIC_TAGS.get(topic,[]),*dynamic,*CORE_TAGS]:
        tag=_clean_text(tag).lower()
        if tag and tag not in tags:tags.append(tag)
    tags=tags[:int(cfg.get("metadata",{}).get("max_tags",6))]; hashtags=["#Shorts",topic_hashtag,"#TradingEducation"]
    description=_description(topic,phrase,brand,hashtags,unique_seed)
    print("SEO topic:",topic); print("SEO title:",title); print("SEO tags:",", ".join(tags)); print("SEO hashtags:"," ".join(hashtags))
    return {"title":title,"description":description,"tags":tags,"category_id":str(cfg.get("metadata",{}).get("category_id","27"))}
