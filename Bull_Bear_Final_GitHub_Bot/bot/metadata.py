EDU={"indicator","strategy","tutorial","rsi","macd","bollinger","aroon","ema","price action","candlestick","support","resistance","analysis","chart"}
LIFE={"lifestyle","motivation","pov","money","success","grind","luxury","hustle","mindset","trader life"}
BASE=["trading shorts","trading","trader","quotex","trading motivation","trader lifestyle","forex trading","technical analysis","price action","day trading","trading for beginners","financial markets","bull and bear vision"]

def build_metadata(info,cfg):
    text=f"{info.get('title','')} {info.get('description','')}".lower(); brand=cfg.get("brand","Bull & Bear Vision")
    if any(w in text for w in EDU):
        title="Trading Strategy Explained Fast 📈🔥 #shorts"; lead="Quick trading breakdown focused on market structure, indicators and price action."; cat="27"; hs=["#shorts","#trading","#quotex","#tradingstrategy","#technicalanalysis","#priceaction","#forextrading","#tradingtips"]
    elif any(w in text for w in LIFE):
        title="POV: Trader Life Hits Different 💸📈 #shorts"; lead="Trader lifestyle, discipline, patience and consistency."; cat="22"; hs=["#shorts","#trading","#quotex","#traderlife","#tradingmotivation","#tradinglifestyle","#forextrading"]
    else:
        title="Live Trading Setup You Need to See 📈🔥 #shorts"; lead="A quick trading clip focused on charts, setups and market discipline."; cat="22"; hs=["#shorts","#trading","#quotex","#forextrading","#priceaction","#technicalanalysis","#trader"]
    disclaimer="⚠️ Educational/entertainment content only. Trading involves financial risk. No strategy or indicator guarantees profit."
    desc=f"{lead}\n\nMore trading content from {brand}.\n\n{disclaimer}\n\n{' '.join(hs)}"
    return {"title":title[:95],"description":desc[:4900],"tags":BASE[:int(cfg.get('metadata',{}).get('max_tags',18))],"category_id":cat}
