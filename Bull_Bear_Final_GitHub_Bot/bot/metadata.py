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

GENERIC_HOOKS=[
"POV: Trading Is Harder Than It Looks",
"The Part of Trading Nobody Talks About",
"One Chart. One Decision. No Second Chances.",
"Would You Enter Here or Wait?",
"Most Traders React Too Early Here",
"The Chart Looks Easy Until Money Is Involved",
"Read the Chart Before You Read the Result",
"This Is Where Patience Gets Tested",
"A Trader's Biggest Battle Is Usually This",
"The Entry Is Easy. The Discipline Is Hard.",
"What Would You Notice First on This Chart?",
"This Trading Moment Feels Too Real",
"Every Trader Has Faced a Chart Like This",
"Sometimes the Best Trade Is No Trade",
"The Market Tests Patience Before Skill",
"Trading Psychology in One Short Clip",
"If You Trade, You Know This Feeling",
"The Hardest Part Is Waiting",
"Before You Click Buy or Sell, Watch This",
"A Small Decision Can Change the Whole Trade",
"Trader POV: Stay Calm and Read the Chart",
"Do You See the Setup or the Trap?",
"One Mistake Traders Keep Repeating",
"This Is Why Discipline Beats Emotion",
"Watch the Chart, Not the Hype",
"The Market Doesn't Care About Your Prediction",
"Think Before the Entry",
"Would You Have the Patience to Wait?",
"A Clean Chart Can Still Fool You",
"This Is What Trading Pressure Feels Like"
]

def _raw_source_text(info): return f"{info.get('title','')} {info.get('description','')}".strip()
def compliance_reason(info):
    raw=_raw_source_text(info); lower=raw.lower()
    for pattern in RISK_PATTERNS:
        if re.search(pattern,raw,re.I): return f"blocked risky claim/promotion: {pattern}"
    if any(x in lower for x in OFF_PLATFORM_TERMS) and any(x in lower for x in FINANCIAL_CTA_TERMS): return "blocked off-platform financial promotion/funneling"
    return None

def _clean_text(value):
    text=re.sub(r"https?://\S+"," ",value or ""); text=SOURCE_PLATFORM_RE.sub(" ",text); text=re.sub(r"[^A-Za-z0-9+#% .,_:'?-]+"," ",text)
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
def _seednum(seed): return int(hashlib.sha256(seed.encode("utf-8",errors="ignore")).hexdigest()[:12],16)
def _variant(seed,options):return options[_seednum(seed)%len(options)]
def _context(source_title):
    clean=re.sub(r"#[A-Za-z0-9_]+"," ",source_title or ""); clean=SOURCE_PLATFORM_RE.sub(" ",clean); clean=re.sub(r"\s+"," ",clean).strip(" -|:,. ")
    words=[]
    for word in clean.split():
        if not words or word.lower()!=words[-1].lower(): words.append(word)
    return " ".join(words[:7])
def _hook_pool(topic,phrase):
    if topic=="Trading Setup": return GENERIC_HOOKS
    return [
        f"Can You Spot the {topic} Signal Here?",
        f"Most Traders Miss This {topic} Detail",
        f"This {topic} Setup Is Worth Studying",
        f"Watch What Happens Around This {topic} Setup",
        f"One {topic} Detail Can Change the Read",
        f"Would You Trust This {topic} Signal?",
        f"Before the Entry, Check This {topic} Detail",
        f"{topic} in Seconds: What Matters Here",
        f"A Cleaner Way to Read {topic}",
        f"This Is What {phrase.title()} Looks Like",
        f"Trader POV: Reading {topic} in Real Time",
        f"The {topic} Clue Most Beginners Ignore",
        f"Do You See the {topic} Setup Yet?",
        f"Wait for This {topic} Confirmation",
        f"Quick Chart Check: {topic}"
    ]
def _title_score(title):
    score=0
    n=len(title)
    if 28<=n<=62: score+=5
    elif n<=72: score+=3
    else: score-=2
    if "?" in title: score+=2
    if title.lower().startswith(("pov:","would you","can you","do you","before","most traders","this is","watch")): score+=2
    if any(w in title.lower() for w in ["patience","discipline","mistake","pressure","signal","trap","entry","chart"]): score+=1
    if len(set(re.findall(r"\w+",title.lower()))) < max(4,len(re.findall(r"\w+",title.lower()))-2): score-=3
    return score
def _title(source_title,topic,phrase,unique_seed):
    context=_context(source_title)
    pool=_hook_pool(topic,phrase)
    start=_seednum(unique_seed+"|hook")%len(pool)
    rotated=pool[start:]+pool[:start]
    title=max(rotated[:8],key=_title_score)
    generic_context=context.lower() in {"trading setup","quotex trading setup","quotex strategy","technical analysis","trading setup and technical analysis example"}
    if context and not generic_context and len(context)>=12 and len(context)<=46 and _seednum(unique_seed+"|ctx")%5==0:
        candidate=f"{context} | {topic}"
        if _title_score(candidate)>=_title_score(title): title=candidate
    title=SOURCE_PLATFORM_RE.sub(" ",title)
    title=re.sub(r"\b(\w+)(?:\s+\1\b)+",r"\1",title,flags=re.I)
    title=re.sub(r"\s+"," ",title).strip(" -|:,. ")
    for pattern in RISK_PATTERNS:title=re.sub(pattern,"",title,flags=re.I)
    return re.sub(r"\s+"," ",title).strip(" -|:,. ")[:88]
def _description(topic,phrase,brand,hashtags,seed):
    if topic=="Trading Setup":
        intros=[
            "Trading is not only about finding an entry. Patience, discipline and decision-making matter just as much.",
            "A quick trading moment for anyone learning to stay patient and read the chart before acting.",
            "The chart is only one part of the trade. Risk awareness and emotional control matter too.",
            "Study the chart, manage risk and focus on the process instead of chasing the outcome.",
            "A short reminder that good trading starts with observation, patience and discipline."
        ]
    else:
        intros=[
            f"A quick {phrase} example — watch the chart and identify the key detail for yourself.",
            f"This short highlights a {topic.lower()} concept traders can study directly on the chart.",
            f"Watch the {phrase} moment and focus on how price behaves around the setup.",
            f"A compact {topic.lower()} example for technical-analysis practice.",
            f"Can you identify the important {phrase} clue before the chart develops?"
        ]
    intro=_variant(seed+"|desc",intros)
    seo_line=f"Topics: {phrase}, chart reading, technical analysis, trading education and risk awareness."
    return SOURCE_PLATFORM_RE.sub(" ",f"{intro}\n\n{seo_line}\n\n{brand} — educational trading content only. Not financial advice. Trading involves risk; profits are never guaranteed.\n\n"+" ".join(hashtags[:3]))[:2000]
def build_metadata(info,cfg):
    risk=compliance_reason(info)
    if risk:raise ValueError(f"YouTube compliance gate: {risk}")
    source_title=_clean_text(info.get("title","")); source_desc=_clean_text(info.get("description","")); source_text=f"{source_title} {source_desc}".strip(); brand=cfg.get("brand","Trading Education Channel"); topic,topic_hashtag,phrase=_detect_topic(source_text)
    unique_seed="|".join([str(info.get("id") or ""),str(info.get("url") or ""),source_text,topic]); title=_title(source_title,topic,phrase,unique_seed); dynamic=_extract_keywords(source_text); tags=[]
    for tag in [phrase,*TOPIC_TAGS.get(topic,[]),*dynamic,*CORE_TAGS]:
        tag=_clean_text(tag).lower()
        if tag and tag not in tags:tags.append(tag)
    tags=tags[:int(cfg.get("metadata",{}).get("max_tags",6))]
    hashtags=["#Shorts",topic_hashtag,"#TradingEducation"]
    description=_description(topic,phrase,brand,hashtags,unique_seed)
    print("SEO topic:",topic); print("SEO title:",title); print("Title hook score:",_title_score(title)); print("SEO tags:",", ".join(tags)); print("SEO hashtags:"," ".join(hashtags))
    return {"title":title,"description":description,"tags":tags,"category_id":str(cfg.get("metadata",{}).get("category_id","27"))}
