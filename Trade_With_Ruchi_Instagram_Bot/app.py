from __future__ import annotations

import os
import random
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
SOURCES_FILE = BASE_DIR / "sources.txt"
HISTORY_FILE = BASE_DIR / "uploaded_urls.txt"

BRAND = os.getenv("BRAND_NAME", "Trade With Ruchi")
IG_USER_ID = os.getenv("Ruchi_IG_USER_ID", "").strip()
ACCESS_TOKEN = os.getenv("Ruchi_IG_ACCESS_TOKEN", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0").strip()
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}
SHARE_TO_FEED = os.getenv("SHARE_TO_FEED", "true").lower() in {"1", "true", "yes", "on"}
POLL_SECONDS = max(5, int(os.getenv("POLL_SECONDS", "10")))
MAX_WAIT_SECONDS = max(60, int(os.getenv("MAX_WAIT_SECONDS", "600")))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(1024 * 1024 * 1024)))


def _is_instagram_reel_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().split(":")[0]
        path = parsed.path.lower()
        is_instagram = host == "instagram.com" or host.endswith(".instagram.com")
        is_supported_path = "/reel/" in path or "/reels/" in path or "/p/" in path
        return parsed.scheme == "https" and is_instagram and is_supported_path
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
        if not _is_instagram_reel_url(url):
            print(f"Skipping non-Instagram Reel/Post source: {url}")
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
    response = requests.post(url, data=data, timeout=90)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}
    if not response.ok:
        raise RuntimeError(f"Meta API POST failed ({response.status_code}): {payload}")
    return payload


def graph_get(path: str, params: dict) -> dict:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path.lstrip('/')}"
    response = requests.get(url, params=params, timeout=90)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}
    if not response.ok:
        raise RuntimeError(f"Meta API GET failed ({response.status_code}): {payload}")
    return payload


def download_instagram_reel(source_url: str, workdir: Path) -> Path:
    output_template = str(workdir / "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": False,
        "no_warnings": False,
        "overwrites": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(source_url, download=True)
        if not info:
            raise RuntimeError("yt-dlp did not return Instagram media information.")
        prepared = Path(ydl.prepare_filename(info))

    if prepared.exists():
        video_path = prepared
    else:
        candidates = sorted(
            (p for p in workdir.iterdir() if p.is_file()),
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not candidates:
            raise RuntimeError("Instagram Reel download finished but no video file was found.")
        video_path = candidates[0]

    if video_path.suffix.lower() != ".mp4":
        raise RuntimeError(
            f"Highest downloaded Instagram source is {video_path.suffix or 'unknown format'}, not MP4. "
            "Bot will not transcode it because quality-preservation mode is enabled."
        )

    file_size = video_path.stat().st_size
    if file_size <= 0:
        raise RuntimeError("Downloaded Instagram Reel is empty.")
    if file_size > MAX_FILE_BYTES:
        raise RuntimeError(
            f"Downloaded Reel is too large ({file_size} bytes); max allowed is {MAX_FILE_BYTES}."
        )

    print(
        f"Downloaded highest available source without re-encoding: "
        f"{video_path.name} ({file_size / 1024 / 1024:.2f} MiB)"
    )
    return video_path


def create_resumable_reel_container(caption: str) -> tuple[str, str]:
    payload = graph_post(
        f"{IG_USER_ID}/media",
        {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "share_to_feed": "true" if SHARE_TO_FEED else "false",
            "access_token": ACCESS_TOKEN,
        },
    )
    container_id = str(payload.get("id", "")).strip()
    upload_uri = str(payload.get("uri", "")).strip()

    if not container_id:
        raise RuntimeError(f"Meta API did not return a creation container id: {payload}")

    if not upload_uri:
        upload_uri = (
            f"https://rupload.facebook.com/ig-api-upload/"
            f"{GRAPH_VERSION}/{container_id}"
        )

    return container_id, upload_uri


def upload_video_binary(upload_uri: str, video_path: Path) -> None:
    file_size = video_path.stat().st_size
    headers = {
        "Authorization": f"OAuth {ACCESS_TOKEN}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Length": str(file_size),
        "Content-Type": "video/mp4",
    }

    with video_path.open("rb") as video_file:
        response = requests.post(
            upload_uri,
            headers=headers,
            data=video_file,
            timeout=600,
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if not response.ok:
        raise RuntimeError(
            f"Meta resumable upload failed ({response.status_code}): {payload}"
        )

    if payload.get("success") is False:
        raise RuntimeError(f"Meta resumable upload reported failure: {payload}")

    print("Video binary uploaded to Meta successfully.")


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
        if status_code in {"FINISHED", "PUBLISHED"}:
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
        print(
            "No Instagram Reel/Post sources configured. "
            "Add approved instagram.com/reel/... URLs to sources.txt. Safe no-op."
        )
        return 0

    seen = load_history()
    unseen = [item for item in sources if item["url"] not in seen]
    if not unseen:
        print("All configured Instagram sources have already been uploaded. Safe no-op.")
        return 0

    random.shuffle(unseen)
    picked = unseen[0]
    caption = build_caption(picked["caption"])
    print(f"Selected Instagram source: {picked['url']}")
    print(f"Brand: {BRAND}")

    if DRY_RUN:
        print("DRY_RUN=true: source selection/caption completed; nothing was published.")
        print(caption)
        return 0

    if not IG_USER_ID or not ACCESS_TOKEN:
        print("Missing Ruchi_IG_USER_ID or Ruchi_IG_ACCESS_TOKEN GitHub secret.")
        return 2

    with tempfile.TemporaryDirectory(prefix="trade-with-ruchi-") as tmp:
        workdir = Path(tmp)
        video_path = download_instagram_reel(picked["url"], workdir)
        container_id, upload_uri = create_resumable_reel_container(caption)
        print(f"Created Instagram Reel container: {container_id}")
        upload_video_binary(upload_uri, video_path)
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
