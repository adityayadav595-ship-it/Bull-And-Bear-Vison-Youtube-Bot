from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

BASE_DIR = Path(__file__).resolve().parent
SOURCES_FILE = BASE_DIR / "sources.txt"
HISTORY_FILE = BASE_DIR / "uploaded_urls.txt"

BRAND = os.getenv("BRAND_NAME", "Trade With Ruchi")
IG_USER_ID = os.getenv("Ruchi_IG_USER_ID", "").strip()
ACCESS_TOKEN = os.getenv("Ruchi_IG_ACCESS_TOKEN", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v22.0").strip()
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}
SHARE_TO_FEED = os.getenv("SHARE_TO_FEED", "true").lower() in {"1", "true", "yes", "on"}
POLL_SECONDS = max(5, int(os.getenv("POLL_SECONDS", "10")))
MAX_WAIT_SECONDS = max(60, int(os.getenv("MAX_WAIT_SECONDS", "600")))


def _validate_public_https_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https" and bool(parsed.netloc)
    except Exception:
        return False


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
        if not _validate_public_https_url(url):
            print(f"Skipping invalid/non-HTTPS source: {url}")
            continue
        items.append({"url": url, "caption": caption})
    return items


def load_history() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    return {
        line.strip()
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def append_history(url: str) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
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
        "#trading #trader #market #tradingeducation #tradewithruchi"
    )[:2200]


def graph_post(path: str, data: dict) -> dict:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path.lstrip('/')}"
    response = requests.post(url, data=data, timeout=60)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}
    if not response.ok:
        raise RuntimeError(f"Meta API POST failed ({response.status_code}): {payload}")
    return payload


def graph_get(path: str, params: dict) -> dict:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path.lstrip('/')}"
    response = requests.get(url, params=params, timeout=60)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}
    if not response.ok:
        raise RuntimeError(f"Meta API GET failed ({response.status_code}): {payload}")
    return payload


def create_reel_container(video_url: str, caption: str) -> str:
    payload = graph_post(
        f"{IG_USER_ID}/media",
        {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if SHARE_TO_FEED else "false",
            "access_token": ACCESS_TOKEN,
        },
    )
    container_id = str(payload.get("id", "")).strip()
    if not container_id:
        raise RuntimeError(f"Meta API did not return a creation container id: {payload}")
    return container_id


def wait_until_ready(container_id: str) -> None:
    deadline = time.time() + MAX_WAIT_SECONDS
    last_status = ""
    while time.time() < deadline:
        payload = graph_get(
            container_id,
            {
                "fields": "status_code,status",
                "access_token": ACCESS_TOKEN,
            },
        )
        status_code = str(payload.get("status_code", "")).upper()
        status_text = str(payload.get("status", ""))
        if status_code != last_status:
            print(f"Container status: {status_code or 'UNKNOWN'} {status_text}".strip())
            last_status = status_code
        if status_code == "FINISHED":
            return
        if status_code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram container failed: {payload}")
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"Instagram container was not ready within {MAX_WAIT_SECONDS}s")


def publish_reel(container_id: str) -> str:
    payload = graph_post(
        f"{IG_USER_ID}/media_publish",
        {
            "creation_id": container_id,
            "access_token": ACCESS_TOKEN,
        },
    )
    media_id = str(payload.get("id", "")).strip()
    if not media_id:
        raise RuntimeError(f"Meta API did not return a published media id: {payload}")
    return media_id


def main() -> int:
    sources = load_sources()
    if not sources:
        print("No sources configured. Add public HTTPS video URLs to sources.txt. Safe no-op.")
        return 0

    seen = load_history()
    unseen = [item for item in sources if item["url"] not in seen]
    if not unseen:
        print("All configured sources have already been uploaded. Safe no-op.")
        return 0

    random.shuffle(unseen)
    picked = unseen[0]
    caption = build_caption(picked["caption"])
    print(f"Selected source: {picked['url']}")
    print(f"Brand: {BRAND}")

    if DRY_RUN:
        print("DRY_RUN=true: selection and caption completed; nothing was published.")
        print(caption)
        return 0

    if not IG_USER_ID or not ACCESS_TOKEN:
        print("Missing Ruchi_IG_USER_ID or Ruchi_IG_ACCESS_TOKEN GitHub secret.")
        return 2

    container_id = create_reel_container(picked["url"], caption)
    print(f"Created Instagram Reel container: {container_id}")
    wait_until_ready(container_id)
    media_id = publish_reel(container_id)
    append_history(picked["url"])
    print(f"UPLOAD SUCCESSFUL | Instagram media id: {media_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"UPLOAD FAILED | {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
