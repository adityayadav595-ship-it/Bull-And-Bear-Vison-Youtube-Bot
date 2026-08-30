from __future__ import annotations

import json
import os


def _client():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception as exc:
        print("AI brain unavailable:", exc)
        return None


def improve_metadata(meta: dict, context: str = "", category: str = "trading") -> dict:
    """Optional AI pass. Falls back to deterministic metadata on any failure."""
    client = _client()
    if client is None:
        print("AI brain: OPENAI_API_KEY not configured; using local metadata engine.")
        return meta

    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    prompt = f"""You are the metadata editor for the YouTube channel Bull & Bear Vision.
Return ONLY valid JSON with keys title, description, tags, hashtags.
Content category: {category}.
Visible/video context: {context[:1200]}
Draft metadata: {json.dumps(meta, ensure_ascii=False)[:2500]}

Rules:
- Accurately describe the supplied context; never invent results or events.
- Make the title natural, curiosity-driven and non-repetitive, max 70 characters.
- No guaranteed profit, 100% win, sure-shot, risk-free, fixed-return, easy-money or misleading claims.
- Educational framing for trading content; do not give personalized financial advice.
- Lifestyle content must not be falsely labelled as a Quotex setup.
- Keep tags relevant, maximum 20. Keep hashtags relevant, maximum 3.
- Do not include URLs or off-platform calls to action.
"""
    try:
        response = client.responses.create(model=model, input=prompt)
        raw = response.output_text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        obj = json.loads(raw)
        out = dict(meta)
        if isinstance(obj.get("title"), str) and obj["title"].strip(): out["title"] = obj["title"].strip()[:100]
        if isinstance(obj.get("description"), str) and obj["description"].strip(): out["description"] = obj["description"].strip()
        if isinstance(obj.get("tags"), list): out["tags"] = [str(x).strip() for x in obj["tags"] if str(x).strip()][:20]
        hashtags = obj.get("hashtags")
        if isinstance(hashtags, list) and hashtags:
            hs = [str(x).strip() for x in hashtags if str(x).strip()][:3]
            if hs:
                out["description"] = out.get("description", "").rstrip() + "\n\n" + " ".join(hs)
        print("AI brain: metadata enhanced with", model)
        return out
    except Exception as exc:
        print("AI brain failed safely; using local metadata:", type(exc).__name__, exc)
        return meta
