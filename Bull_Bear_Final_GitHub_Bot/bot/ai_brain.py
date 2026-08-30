from __future__ import annotations

import json
import os
import time


def _client():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types
        # Keep optional AI metadata enhancement from consuming the entire autorun.
        # If Gemini is slow/unavailable, the existing fallback logic will switch
        # models and ultimately keep the local metadata instead of blocking upload.
        return genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=30_000),
        )
    except Exception as exc:
        print("Gemini brain unavailable:", exc)
        return None


def _clean_json_text(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    return raw


def _dedupe_hashtags(description: str, hashtags: list[str]) -> str:
    existing = {word.lower() for word in description.split() if word.startswith("#")}
    clean = []
    for tag in hashtags[:3]:
        tag = str(tag).strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag.replace(" ", "")
        if tag.lower() not in existing and tag.lower() not in {x.lower() for x in clean}:
            clean.append(tag)
    if not clean:
        return description
    return description.rstrip() + "\n\n" + " ".join(clean)


def _models() -> list[str]:
    primary = os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip() or "gemini-3.7-flash"
    configured = os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.6-flash,gemini-3.5-flash-lite,gemini-2.5-flash-lite",
    )
    result = []
    for model in [primary, *configured.split(",")]:
        model = model.strip()
        if model and model not in result:
            result.append(model)
    return result


def _generate_with_fallback(client, prompt: str):
    last_exc = None
    for model in _models():
        # One quick retry handles transient capacity spikes without making an upload wait for minutes.
        for attempt in range(2):
            try:
                print(f"Gemini brain: trying {model} (attempt {attempt + 1}/2)")
                response = client.models.generate_content(model=model, contents=prompt)
                return model, response
            except Exception as exc:
                last_exc = exc
                print(f"Gemini brain: {model} attempt {attempt + 1} failed: {type(exc).__name__}: {exc}")
                if attempt == 0:
                    time.sleep(2)
        print(f"Gemini brain: switching away from unavailable model {model}")
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No Gemini model configured")


def improve_metadata(meta: dict, context: str = "", category: str = "trading") -> dict:
    """Optional Gemini metadata pass with model failover. Local metadata remains the final fallback."""
    client = _client()
    if client is None:
        print("Gemini brain: GEMINI_API_KEY not configured; using local metadata engine.")
        return meta

    prompt = f"""You are the metadata editor for the YouTube channel Bull & Bear Vision.
Return ONLY valid JSON with keys title, description, tags, hashtags.
Content category: {category}.
Visible/video context: {context[:1200]}
Draft metadata: {json.dumps(meta, ensure_ascii=False)[:2500]}

Rules:
- Accurately describe only what the supplied context supports; never invent results or events.
- Make the title natural, curiosity-driven and non-repetitive, maximum 70 characters.
- Never claim guaranteed profit, 100% win, sure-shot, risk-free, fixed-return, easy-money or guaranteed results.
- Trading content must be educational and must not give personalized financial advice.
- Lifestyle content must not be falsely labelled as a Quotex or trading setup.
- Keep tags relevant, maximum 20.
- Keep hashtags relevant, maximum 3.
- Do not include URLs or off-platform calls to action.
"""
    try:
        model, response = _generate_with_fallback(client, prompt)
        raw = _clean_json_text(getattr(response, "text", ""))
        obj = json.loads(raw)
        out = dict(meta)
        if isinstance(obj.get("title"), str) and obj["title"].strip():
            out["title"] = obj["title"].strip()[:70]
        if isinstance(obj.get("description"), str) and obj["description"].strip():
            out["description"] = obj["description"].strip()
        if isinstance(obj.get("tags"), list):
            out["tags"] = [str(x).strip() for x in obj["tags"] if str(x).strip()][:20]
        hashtags = obj.get("hashtags")
        if isinstance(hashtags, list):
            out["description"] = _dedupe_hashtags(out.get("description", ""), hashtags)
        print("Gemini brain: metadata enhanced with", model)
        return out
    except Exception as exc:
        print("Gemini brain failed safely after all models; using local metadata:", type(exc).__name__, exc)
        return meta
