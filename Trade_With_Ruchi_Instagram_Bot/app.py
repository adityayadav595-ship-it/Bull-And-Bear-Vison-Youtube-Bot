from __future__ import annotations

import html
import itertools
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import instaloader
import requests
import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
SOURCES_FILE = BASE_DIR / "sources.txt"
PROFILES_FILE = BASE_DIR / "approved_profiles.txt"
HISTORY_FILE = BASE_DIR / "uploaded_urls.txt"

BRAND = os.getenv("BRAND_NAME", "Trade With Ruchi")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN", "").strip()
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID", "").strip()
BUFFER_API_URL = "https://api.buffer.com"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}
PROFILES_PER_RUN = max(1, int(os.getenv("PROFILES_PER_RUN", "3")))
REELS_PER_PROFILE = max(1, int(os.getenv("REELS_PER_PROFILE", "3")))
SOURCE_IG_SESSION_JSON = os.getenv("RUCHI_SOURCE_IG_SESSION_JSON", "").strip()

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)
REEL_RE = re.compile(r"(?:https?:\\/\\/(?:www\\.)?instagram\\.com)?\\?/reel\\?/([A-Za-z0-9_-]{5,})", re.I)
SHORTCODE_RE = re.compile(r'"shortcode"\s*:\s*"([A-Za-z0-9_-]{5,})"')


def _is_instagram_reel_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().split(":")[0]
        path = parsed.path.lower()
        return (
            parsed.scheme == "https"
            and (host == "instagram.com" or host.endswith(".instagram.com"))
            and ("/reel/" in path or "/reels/" in path or "/p/" in path)
        )
    except Exception:
        return False


def _profile_username(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        try:
            parsed = urlparse(value)
            host = parsed.netloc.lower().split(":")[0]
            if host != "instagram.com" and not host.endswith(".instagram.com"):
                return ""
            parts = [p for p in parsed.path.split("/") if p]
            if not parts:
                return ""
            value = parts[0]
        except Exception:
            return ""
    value = value.lstrip("@").strip()
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._"
    return value if value and all(ch in allowed for ch in value) else ""


def load_sources() -> list[dict]:
    if not SOURCES_FILE.exists():
        return []
    items: list[dict] = []
    for raw in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        url = parts[0]
        caption = parts[1] if len(parts) > 1 else ""
        if _is_instagram_reel_url(url):
            items.append({"url": url, "caption": caption, "timestamp": 0, "origin": "direct"})
    return items


def load_profiles() -> list[str]:
    if not PROFILES_FILE.exists():
        return []
    profiles: list[str] = []
    seen: set[str] = set()
    for raw in PROFILES_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        username = _profile_username(line)
        if username and username.lower() not in seen:
            profiles.append(username)
            seen.add(username.lower())
    return profiles


def load_history() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    return {
        line.strip()
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def append_history(url: str) -> None:
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(url + "\n")


def build_caption(custom_caption: str) -> str:
    custom_caption = custom_caption.strip()
    if custom_caption:
        return custom_caption[:2200]
    return (
        f"{BRAND} 📈\n\n"
        "Trading education & market-learning content.\n"
        "For educational purposes only. Trading involves risk.\n\n"
        "#tradewithruchi #trading #trader #marketanalysis #tradingeducation"
    )[:2200]


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    if not BUFFER_ACCESS_TOKEN:
        raise RuntimeError("BUFFER_ACCESS_TOKEN GitHub secret is missing.")
    response = requests.post(
        BUFFER_API_URL,
        headers={
            "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
        json={"query": query, "variables": variables or {}},
        timeout=45,
    )
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(f"Buffer returned non-JSON response ({response.status_code}): {response.text[:500]}")
    if not response.ok:
        raise RuntimeError(f"Buffer API HTTP {response.status_code}: {payload}")
    if payload.get("errors"):
        raise RuntimeError(f"Buffer GraphQL error: {payload['errors']}")
    return payload.get("data") or {}


def resolve_instagram_channel() -> str:
    if BUFFER_CHANNEL_ID:
        print("Using configured Buffer Instagram channel id.")
        return BUFFER_CHANNEL_ID

    org_data = buffer_graphql(
        """
        query GetOrganizations {
          account { organizations { id name } }
        }
        """
    )
    orgs = ((org_data.get("account") or {}).get("organizations") or [])
    if not orgs:
        raise RuntimeError("Buffer key is valid but no organization was returned.")

    instagram_channels: list[dict] = []
    for org in orgs:
        data = buffer_graphql(
            """
            query GetChannels($orgId: OrganizationId!) {
              channels(input: { organizationId: $orgId }) {
                id name displayName service
              }
            }
            """,
            {"orgId": org["id"]},
        )
        for channel in data.get("channels") or []:
            if str(channel.get("service", "")).lower() == "instagram":
                instagram_channels.append(channel)

    if not instagram_channels:
        raise RuntimeError("No Instagram channel is connected to this Buffer account.")
    if len(instagram_channels) > 1:
        names = ", ".join(str(c.get("displayName") or c.get("name") or c.get("id")) for c in instagram_channels)
        raise RuntimeError(
            "More than one Instagram channel is connected. Set BUFFER_CHANNEL_ID. "
            f"Found: {names}"
        )
    channel = instagram_channels[0]
    print(f"Buffer connection OK | Instagram channel: {channel.get('displayName') or channel.get('name') or channel['id']}")
    return str(channel["id"])


def _profiles_for_this_run(profiles: list[str]) -> list[str]:
    if len(profiles) <= PROFILES_PER_RUN:
        return profiles
    slot = int(time.time() // (3 * 60 * 60))
    start = slot % len(profiles)
    ordered = profiles[start:] + profiles[:start]
    return ordered[:PROFILES_PER_RUN]


def _discover_from_public_html(username: str, seen_urls: set[str]) -> list[dict]:
    url = f"https://www.instagram.com/{username}/"
    response = requests.get(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=15,
        allow_redirects=True,
    )
    if response.status_code == 429:
        print(f"@{username}: Instagram HTML rate-limited (429); skipping immediately.")
        return []
    if not response.ok:
        print(f"@{username}: Instagram HTML returned HTTP {response.status_code}.")
        return []

    body = html.unescape(response.text).replace("\\/", "/")
    codes: list[str] = []
    for match in REEL_RE.finditer(body):
        code = match.group(1)
        if code not in codes:
            codes.append(code)
    if not codes:
        for match in SHORTCODE_RE.finditer(body):
            code = match.group(1)
            if code not in codes:
                codes.append(code)

    found: list[dict] = []
    for code in codes[:REELS_PER_PROFILE]:
        reel_url = f"https://www.instagram.com/reel/{code}/"
        if reel_url in seen_urls:
            continue
        found.append({
            "url": reel_url,
            "caption": "",
            "timestamp": 0,
            "origin": f"profile-html:@{username}",
        })
    if found:
        print(f"@{username}: found {len(found)} Reel candidate(s) from public profile HTML.")
    return found


def _build_instaloader() -> instaloader.Instaloader:
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        max_connection_attempts=1,
        request_timeout=12.0,
    )
    if SOURCE_IG_SESSION_JSON:
        try:
            cookies = json.loads(SOURCE_IG_SESSION_JSON)
            if isinstance(cookies, dict):
                loader.context.update_cookies({str(k): str(v) for k, v in cookies.items()})
                print("Optional Instagram source session loaded.")
        except Exception as exc:
            print(f"Optional Instagram source session could not be loaded: {exc}")
    return loader


def discover_profile_reels(seen_urls: set[str]) -> list[dict]:
    profiles = load_profiles()
    if not profiles:
        return []
    selected = _profiles_for_this_run(profiles)
    print("Scanning approved source profiles:", ", ".join(f"@{u}" for u in selected))

    candidates: list[dict] = []
    for username in selected:
        try:
            candidates.extend(_discover_from_public_html(username, seen_urls))
        except Exception as exc:
            print(f"@{username}: HTML discovery skipped: {type(exc).__name__}: {exc}")
        if candidates:
            break
        time.sleep(1)

    # Instaloader is only a last fallback and is tried once, never across many profiles.
    if not candidates and selected:
        username = selected[0]
        loader = _build_instaloader()
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            for post in itertools.islice(profile.get_reels(), REELS_PER_PROFILE):
                shortcode = str(getattr(post, "shortcode", "") or "").strip()
                if not shortcode:
                    continue
                reel_url = f"https://www.instagram.com/reel/{shortcode}/"
                if reel_url in seen_urls:
                    continue
                try:
                    timestamp = int(post.date_utc.timestamp())
                except Exception:
                    timestamp = 0
                candidates.append({
                    "url": reel_url,
                    "caption": "",
                    "timestamp": timestamp,
                    "origin": f"instaloader:@{username}",
                })
        except Exception as exc:
            print(f"@{username}: Instaloader fallback skipped: {type(exc).__name__}: {exc}")

    candidates.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)
    return candidates


def extract_public_video_url(source_url: str) -> str:
    opts = {
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "skip_download": True,
        "socket_timeout": 20,
        "retries": 1,
        "http_headers": {"User-Agent": UA},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source_url, download=False)
    if not info:
        raise RuntimeError("Could not resolve source Reel media.")

    direct = str(info.get("url") or "").strip()
    if not direct:
        requested = info.get("requested_formats") or []
        for fmt in requested:
            if fmt.get("vcodec") != "none" and fmt.get("url"):
                direct = str(fmt["url"]).strip()
                break
    if not direct.startswith("https://"):
        raise RuntimeError("Instagram source did not expose an HTTPS video URL Buffer can fetch.")

    # Verify it is reachable before handing it to Buffer.
    try:
        check = requests.get(direct, headers={"User-Agent": UA, "Range": "bytes=0-1023"}, timeout=20, stream=True)
        if check.status_code not in {200, 206}:
            raise RuntimeError(f"Resolved Instagram video URL returned HTTP {check.status_code}.")
    finally:
        try:
            check.close()
        except Exception:
            pass
    print("Resolved and verified source video URL for immediate Buffer publishing.")
    return direct


def create_buffer_reel(channel_id: str, caption: str, video_url: str) -> str:
    query = """
    mutation CreateInstagramReel($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id text dueAt status }
        }
        ... on MutationError { message }
      }
    }
    """
    variables = {
        "input": {
            "text": caption,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "shareNow",
            "assets": [
                {
                    "video": {
                        "url": video_url,
                        "metadata": {"thumbnailOffset": 1000},
                    }
                }
            ],
            "metadata": {
                "instagram": {
                    "type": "reel",
                    "shouldShareToFeed": True,
                }
            },
        }
    }
    data = buffer_graphql(query, variables)
    result = data.get("createPost") or {}
    if result.get("message"):
        raise RuntimeError(f"Buffer rejected Reel: {result['message']}")
    post = result.get("post") or {}
    post_id = str(post.get("id") or "").strip()
    if not post_id:
        raise RuntimeError(f"Buffer did not return a post id: {result}")
    print(f"BUFFER POST CREATED | id={post_id} | status={post.get('status')}")
    return post_id


def main() -> int:
    # Validate Buffer first so publishing credentials/channel errors are surfaced immediately.
    channel_id = ""
    if not DRY_RUN:
        channel_id = resolve_instagram_channel()

    seen = load_history()
    direct_candidates = [item for item in load_sources() if item["url"] not in seen]
    if direct_candidates:
        random.shuffle(direct_candidates)
        picked = direct_candidates[0]
    else:
        profile_candidates = discover_profile_reels(seen)
        if not profile_candidates:
            print("No unseen Reel could be discovered this run. Safe no-op; no long retry.")
            return 0
        picked = profile_candidates[0]

    caption = build_caption(picked.get("caption", ""))
    print(f"Selected: {picked['url']} ({picked.get('origin', 'unknown')})")

    if DRY_RUN:
        print("DRY_RUN=true: nothing will be published.")
        print(caption)
        return 0

    video_url = extract_public_video_url(picked["url"])
    post_id = create_buffer_reel(channel_id, caption, video_url)
    append_history(picked["url"])
    print(f"UPLOAD REQUEST SUCCESSFUL | Buffer post id: {post_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
