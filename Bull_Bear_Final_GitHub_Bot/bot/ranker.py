import random
KEYWORDS={"quotex":10,"live trading":10,"trading":6,"strategy":5,"indicator":5,"price action":5,"forex":4,"candlestick":4,"setup":3,"motivation":1}

def candidate_score(c,cfg):
    text=f"{c.get('title','')} {c.get('description','')}".lower(); score=0.0
    for w,p in KEYWORDS.items():
        if w in text: score+=p
    d=c.get("duration")
    if isinstance(d,(int,float)):
        mn=int(cfg.get("discovery",{}).get("min_duration_seconds",4)); mx=int(cfg.get("discovery",{}).get("max_duration_seconds",60))
        score += 5 if mn <= d <= mx else -5
    views=c.get("view_count") or 0; likes=c.get("like_count") or 0
    if views>0: score+=min(8,views/100000)
    if likes>0: score+=min(6,likes/10000)
    if c.get("timestamp"): score+=1
    return score

def choose_random_from_best(candidates,cfg):
    if not candidates: return None
    ranked=sorted(candidates,key=lambda c:candidate_score(c,cfg),reverse=True)
    n=max(1,int(cfg.get("discovery",{}).get("top_pool_size",6)))
    return random.choice(ranked[:n])
