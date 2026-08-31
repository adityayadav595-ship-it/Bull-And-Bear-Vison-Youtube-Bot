from __future__ import annotations

import os
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

BASE_DIR = Path(__file__).resolve().parent
PROFILES_FILE = BASE_DIR / "approved_profiles.txt"
SOURCES_FILE = BASE_DIR / "sources.txt"
HISTORY_FILE = BASE_DIR / "uploaded_urls.txt"

BRAND = os.getenv("BRAND_NAME", "Trade With Ruchi")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN", "").strip()
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID", "").strip()
INSTAGRAMAPI_KEY = os.getenv("INSTAGRAMAPI_KEY", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}
PROFILES_PER_RUN = max(1, int(os.getenv("PROFILES_PER_RUN", "3")))
REELS_PER_PROFILE = max(1, int(os.getenv("REELS_PER_PROFILE", "3")))
BUFFER_API_URL = "https://api.buffer.com"
IG_API_BASE = "https://api.instagramapi.dev/v1"
UA = "Trade-With-Ruchi-Auto-Uploader/2.1"


def username(value: str) -> str:
    value = value.strip()
    if value.startswith(("http://", "https://")):
        parts = [p for p in urlparse(value).path.split("/") if p]
        value = parts[0] if parts else ""
    return value.lstrip("@").strip()


def load_profiles() -> list[str]:
    if not PROFILES_FILE.exists():
        return []
    out, seen = [], set()
    for raw in PROFILES_FILE.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        u = username(raw)
        if u and u.lower() not in seen:
            out.append(u)
            seen.add(u.lower())
    return out


def load_history() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    return {x.strip() for x in HISTORY_FILE.read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")}


def append_history(url: str) -> None:
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(url + "\n")


def direct_candidates(seen: set[str]) -> list[dict]:
    if not SOURCES_FILE.exists():
        return []
    out = []
    for raw in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        if parts[0] not in seen:
            out.append({"url": parts[0], "caption": parts[1] if len(parts) > 1 else "", "video_url": "", "taken_at": "", "origin": "direct"})
    return out


def ig_get(path: str, params: dict) -> dict:
    if not INSTAGRAMAPI_KEY:
        raise RuntimeError("INSTAGRAMAPI_KEY GitHub secret is missing.")
    r = requests.get(
        f"{IG_API_BASE}{path}",
        params=params,
        headers={"Authorization": f"Bearer {INSTAGRAMAPI_KEY}", "User-Agent": UA},
        timeout=45,
    )
    try:
        payload = r.json()
    except ValueError:
        raise RuntimeError(f"InstagramAPI returned non-JSON HTTP {r.status_code}.")
    if not r.ok:
        err = payload.get("error") or payload
        raise RuntimeError(f"InstagramAPI HTTP {r.status_code}: {err}")
    return payload


def discover_api_reels(seen: set[str]) -> list[dict]:
    profiles = load_profiles()
    if not profiles:
        raise RuntimeError("approved_profiles.txt has no source profiles.")
    random.shuffle(profiles)
    selected = profiles[:PROFILES_PER_RUN]
    print("InstagramAPI scanning:", ", ".join("@" + u for u in selected))
    found = []
    errors = []
    for u in selected:
        try:
            payload = ig_get("/profile/reels", {"handle": u})
            data = payload.get("data") or {}
            items = data.get("items") if isinstance(data, dict) else []
            items = items or []
            count = 0
            for item in items:
                if count >= REELS_PER_PROFILE:
                    break
                code = str(item.get("shortcode") or "").strip()
                reel_url = str(item.get("url") or "").strip()
                if not reel_url and code:
                    reel_url = f"https://www.instagram.com/reel/{code}/"
                if not reel_url or reel_url in seen:
                    continue
                video = str(item.get("video_url") or "").strip()
                found.append({
                    "url": reel_url,
                    "caption": str(item.get("caption") or ""),
                    "video_url": video,
                    "taken_at": str(item.get("taken_at") or ""),
                    "origin": f"instagramapi:@{u}",
                })
                count += 1
            print(f"@{u}: {count} unseen Reel candidate(s).")
        except Exception as exc:
            errors.append(f"@{u}: {exc}")
            print(errors[-1])
    if not found and errors and len(errors) == len(selected):
        raise RuntimeError("All InstagramAPI profile lookups failed: " + " | ".join(errors))
    found.sort(key=lambda x: x.get("taken_at", ""), reverse=True)
    return found


def resolve_video(item: dict) -> str:
    video = str(item.get("video_url") or "").strip()
    if not video.startswith("https://"):
        payload = ig_get("/post", {"url": item["url"]})
        data = payload.get("data") or {}
        video = str(data.get("video_url") or "").strip()
    if not video.startswith("https://"):
        raise RuntimeError("InstagramAPI did not return a public HTTPS video URL for the Reel.")

    # Buffer fetches this URL itself, so verify it is reachable without Instagram cookies.
    probe = requests.get(
        video,
        headers={"User-Agent": UA, "Range": "bytes=0-2047"},
        timeout=30,
        stream=True,
        allow_redirects=True,
    )
    try:
        if probe.status_code not in {200, 206}:
            raise RuntimeError(f"Source video URL is not publicly fetchable (HTTP {probe.status_code}).")
        content_type = str(probe.headers.get("Content-Type") or "").lower()
        if content_type and "video" not in content_type and "octet-stream" not in content_type:
            raise RuntimeError(f"Source URL is not a video response (Content-Type: {content_type}).")
    finally:
        probe.close()
    print("Source video URL verified as publicly reachable.")
    return video


def build_caption(source_caption: str) -> str:
    return (
        f"{BRAND} 📈\n\n"
        "Trading education & market-learning content.\n"
        "For educational purposes only. Trading involves risk.\n\n"
        "#tradewithruchi #trading #trader #marketanalysis #tradingeducation"
    )[:2200]


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    if not BUFFER_ACCESS_TOKEN:
        raise RuntimeError("BUFFER_ACCESS_TOKEN GitHub secret is missing.")
    r = requests.post(
        BUFFER_API_URL,
        headers={"Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}", "Content-Type": "application/json", "User-Agent": UA},
        json={"query": query, "variables": variables or {}},
        timeout=45,
    )
    try:
        payload = r.json()
    except ValueError:
        raise RuntimeError(f"Buffer returned non-JSON HTTP {r.status_code}.")
    if not r.ok or payload.get("errors"):
        raise RuntimeError(f"Buffer API error: {payload}")
    return payload.get("data") or {}


def resolve_instagram_channel() -> str:
    if BUFFER_CHANNEL_ID:
        return BUFFER_CHANNEL_ID
    org_data = buffer_graphql("query { account { organizations { id name } } }")
    orgs = ((org_data.get("account") or {}).get("organizations") or [])
    channels = []
    for org in orgs:
        data = buffer_graphql(
            "query GetChannels($orgId: OrganizationId!) { channels(input: { organizationId: $orgId }) { id name displayName service } }",
            {"orgId": org["id"]},
        )
        channels.extend(c for c in (data.get("channels") or []) if str(c.get("service", "")).lower() == "instagram")
    if not channels:
        raise RuntimeError("No Instagram channel connected in Buffer.")
    if len(channels) > 1:
        raise RuntimeError("Multiple Instagram channels found; set BUFFER_CHANNEL_ID.")
    c = channels[0]
    print("Buffer connection OK | Instagram channel:", c.get("displayName") or c.get("name") or c["id"])
    return str(c["id"])


def buffer_post_status(post_id: str) -> dict:
    query = """
    query GetPost($id: PostId!) {
      post(input: { id: $id }) {
        id
        status
        sentAt
        externalLink
        error { message rawError supportUrl }
      }
    }
    """
    data = buffer_graphql(query, {"id": post_id})
    return data.get("post") or {}


def _buffer_error_text(post: dict) -> str:
    err = post.get("error") or {}
    parts = []
    if err.get("message"):
        parts.append(str(err["message"]))
    if err.get("rawError") and str(err.get("rawError")) not in parts:
        parts.append(str(err["rawError"]))
    if err.get("supportUrl"):
        parts.append("support=" + str(err["supportUrl"]))
    return " | ".join(parts) or "Buffer marked the post as error without an error message."


def create_buffer_reel(channel_id: str, caption: str, video_url: str) -> str:
    mutation = """
    mutation CreateInstagramReel($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id text dueAt status sentAt externalLink
            error { message rawError supportUrl }
          }
        }
        ... on MutationError { message }
      }
    }
    """
    variables = {"input": {
        "text": caption,
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "shareNow",
        "assets": [{"video": {"url": video_url, "metadata": {"thumbnailOffset": 1000}}}],
        "metadata": {"instagram": {"type": "reel", "shouldShareToFeed": True}},
    }}
    data = buffer_graphql(mutation, variables)
    result = data.get("createPost") or {}
    if result.get("message"):
        raise RuntimeError("Buffer rejected Reel: " + str(result["message"]))
    post = result.get("post") or {}
    post_id = str(post.get("id") or "").strip()
    if not post_id:
        raise RuntimeError(f"Buffer did not return a post id: {result}")

    status = str(post.get("status") or "").lower()
    print(f"BUFFER POST CREATED | id={post_id} | status={status or 'unknown'}")
    if status == "error":
        raise RuntimeError("Buffer publishing failed: " + _buffer_error_text(post))
    if status == "sent":
        print("BUFFER PUBLISH CONFIRMED | status=sent | link=", post.get("externalLink") or "not returned")
        return post_id

    # shareNow can briefly be scheduled/sending. Do not record history until Buffer confirms sent.
    for attempt in range(1, 13):
        time.sleep(5)
        post = buffer_post_status(post_id)
        status = str(post.get("status") or "").lower()
        print(f"Buffer publish check {attempt}/12 | status={status or 'unknown'}")
        if status == "sent":
            print("BUFFER PUBLISH CONFIRMED | status=sent | link=", post.get("externalLink") or "not returned")
            return post_id
        if status == "error":
            raise RuntimeError("Buffer publishing failed: " + _buffer_error_text(post))

    raise RuntimeError(f"Buffer publish was not confirmed within 60 seconds (last status={status or 'unknown'}). History not recorded.")


def main() -> int:
    channel_id = "" if DRY_RUN else resolve_instagram_channel()
    seen = load_history()
    candidates = direct_candidates(seen)
    if not candidates:
        candidates = discover_api_reels(seen)
    if not candidates:
        raise RuntimeError("No unseen Reel found in the approved profiles.")
    picked = candidates[0]
    print(f"Picked {picked['url']} from {picked['origin']}")
    if DRY_RUN:
        print("DRY RUN OK")
        return 0
    video_url = resolve_video(picked)
    create_buffer_reel(channel_id, build_caption(picked.get("caption", "")), video_url)
    append_history(picked["url"])
    print("UPLOAD CONFIRMED ON INSTAGRAM VIA BUFFER AND HISTORY RECORDED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", flush=True)
        raise
