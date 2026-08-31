from __future__ import annotations

import os
import random
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader
import cv2
import requests
from yt_dlp import YoutubeDL

BASE_DIR = Path(__file__).resolve().parent
PROFILES_FILE = BASE_DIR / "approved_profiles.txt"
PINTEREST_FILE = BASE_DIR / "pinterest_sources.txt"
SOURCES_FILE = BASE_DIR / "sources.txt"
HISTORY_FILE = BASE_DIR / "uploaded_urls.txt"

BRAND = os.getenv("BRAND_NAME", "Trade With Ruchi")
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN", "").strip()
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID", "").strip()
INSTAGRAMAPI_KEY = os.getenv("INSTAGRAMAPI_KEY", "").strip()
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}
PROFILES_PER_RUN = max(1, int(os.getenv("PROFILES_PER_RUN", "3")))
REELS_PER_PROFILE = max(1, int(os.getenv("REELS_PER_PROFILE", "3")))
BUFFER_API_URL = "https://api.buffer.com"
IG_API_BASE = "https://api.instagramapi.dev/v1"
UA = "Trade-With-Ruchi-Auto-Uploader/4.0"
BUFFER_POLL_SECONDS = 5
BUFFER_MAX_CHECKS = 96
MAX_CANDIDATES_TO_TEST = 8


def username(value: str) -> str:
    value = value.strip()
    if value.startswith(("http://", "https://")):
        parts = [p for p in urlparse(value).path.split("/") if p]
        value = parts[0] if parts else ""
    return value.lstrip("@").strip()


def read_urls(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")]


def load_history() -> set[str]:
    return set(read_urls(HISTORY_FILE))


def append_history(url: str) -> None:
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(url + "\n")


def ig_get(path: str, params: dict) -> dict:
    if not INSTAGRAMAPI_KEY:
        raise RuntimeError("INSTAGRAMAPI_KEY GitHub secret is missing.")
    r = requests.get(
        f"{IG_API_BASE}{path}", params=params,
        headers={"Authorization": f"Bearer {INSTAGRAMAPI_KEY}", "User-Agent": UA}, timeout=45,
    )
    try:
        payload = r.json()
    except ValueError:
        raise RuntimeError(f"InstagramAPI returned non-JSON HTTP {r.status_code}.")
    if not r.ok:
        raise RuntimeError(f"InstagramAPI HTTP {r.status_code}: {payload.get('error') or payload}")
    return payload


def instagram_candidates(seen: set[str]) -> list[dict]:
    profiles = [username(x) for x in read_urls(PROFILES_FILE)]
    profiles = [x for x in profiles if x]
    random.shuffle(profiles)
    selected = profiles[:PROFILES_PER_RUN]
    print("InstagramAPI scanning:", ", ".join("@" + u for u in selected))
    found = []
    for u in selected:
        try:
            payload = ig_get("/profile/reels", {"handle": u})
            data = payload.get("data") or {}
            items = (data.get("items") if isinstance(data, dict) else []) or []
            count = 0
            for item in items:
                if count >= REELS_PER_PROFILE:
                    break
                code = str(item.get("shortcode") or "").strip()
                reel_url = str(item.get("url") or "").strip() or (f"https://www.instagram.com/reel/{code}/" if code else "")
                if not reel_url or reel_url in seen:
                    continue
                found.append({
                    "url": reel_url,
                    "caption": str(item.get("caption") or ""),
                    "video_url": str(item.get("video_url") or "").strip(),
                    "taken_at": str(item.get("taken_at") or ""),
                    "origin": f"instagram:@{u}",
                })
                count += 1
            print(f"@{u}: {count} unseen candidate(s)")
        except Exception as exc:
            print(f"Instagram source @{u} skipped: {exc}")
    found.sort(key=lambda x: x.get("taken_at", ""), reverse=True)
    return found


def pinterest_candidates(seen: set[str]) -> list[dict]:
    urls = [u for u in read_urls(PINTEREST_FILE) if u not in seen]
    random.shuffle(urls)
    out = [{"url": u, "caption": "", "video_url": "", "taken_at": "", "origin": "pinterest"} for u in urls]
    print(f"Pinterest pool: {len(out)} unseen approved pin(s)")
    return out


def direct_candidates(seen: set[str]) -> list[dict]:
    out = []
    for line in read_urls(SOURCES_FILE):
        parts = [p.strip() for p in line.split("|", 1)]
        if parts[0] not in seen:
            out.append({"url": parts[0], "caption": parts[1] if len(parts) > 1 else "", "video_url": "", "taken_at": "", "origin": "direct"})
    return out


def mixed_candidates(seen: set[str]) -> list[dict]:
    direct = direct_candidates(seen)
    ig = instagram_candidates(seen)
    pin = pinterest_candidates(seen)
    mixed = direct + ig + pin
    random.shuffle(mixed)
    return mixed


def instagram_video_url(item: dict) -> str:
    video = str(item.get("video_url") or "").strip()
    if not video.startswith("https://"):
        payload = ig_get("/post", {"url": item["url"]})
        data = payload.get("data") or {}
        video = str(data.get("video_url") or "").strip()
    if not video.startswith("https://"):
        raise RuntimeError("InstagramAPI did not return an HTTPS video URL.")
    return video


def download_http_video(url: str, output: Path) -> None:
    with requests.get(url, headers={"User-Agent": UA}, timeout=90, stream=True, allow_redirects=True) as r:
        if not r.ok:
            raise RuntimeError(f"Source video download failed with HTTP {r.status_code}.")
        with output.open("wb") as f:
            total = 0
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
                    if total > 250 * 1024 * 1024:
                        raise RuntimeError("Source video larger than 250 MB.")
    if not output.exists() or output.stat().st_size < 10_000:
        raise RuntimeError("Downloaded source is not a valid video.")


def download_pinterest(url: str, output: Path) -> None:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bv*+ba/best",
        "merge_output_format": "mp4",
        "outtmpl": str(output),
        "socket_timeout": 60,
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    if not output.exists() or output.stat().st_size < 10_000:
        alt = list(output.parent.glob("source.*"))
        if alt:
            alt[0].replace(output)
    if not output.exists() or output.stat().st_size < 10_000:
        raise RuntimeError("Pinterest pin did not produce a usable video.")


def download_candidate(item: dict, output: Path) -> None:
    if item.get("origin") == "pinterest" or "pin.it/" in item["url"] or "pinterest." in item["url"]:
        download_pinterest(item["url"], output)
    elif item.get("origin", "").startswith("instagram") or "instagram.com/" in item["url"]:
        download_http_video(instagram_video_url(item), output)
    else:
        download_http_video(item["url"], output)
    print(f"Downloaded candidate: {output.stat().st_size // 1024} KB")


def face_heavy(video_path: Path) -> bool:
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("Face filter could not inspect the video.")
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sample_count = 12
    hits = 0
    checked = 0
    for i in range(sample_count):
        if frames > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((frames - 1) * i / max(1, sample_count - 1)))
        ok, frame = cap.read()
        if not ok:
            continue
        checked += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        area = frame.shape[0] * frame.shape[1]
        prominent = any((w * h) / max(1, area) >= 0.035 for (_, _, w, h) in faces)
        if prominent:
            hits += 1
    cap.release()
    ratio = hits / max(1, checked)
    print(f"Face filter: {hits}/{checked} sampled frames prominent-face ({ratio:.0%})")
    return checked >= 4 and ratio >= 0.40


def normalize_video(source: Path, output: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?",
        "-vf", "scale='min(1080,iw)':-2:force_original_aspect_ratio=decrease,fps=30,format=yuv420p",
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-preset", "fast",
        "-crf", "23", "-maxrate", "5M", "-bufsize", "10M",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", str(output),
    ]
    subprocess.run(cmd, check=True, timeout=240)
    if not output.exists() or output.stat().st_size < 10_000:
        raise RuntimeError("Normalized MP4 was not created correctly.")


def host_on_cloudinary(video_path: Path) -> str:
    if not CLOUDINARY_URL:
        raise RuntimeError("CLOUDINARY_URL GitHub secret is missing.")
    cloudinary.config(secure=True)
    result = cloudinary.uploader.upload_large(
        str(video_path), resource_type="video", folder="trade-with-ruchi/reels",
        use_filename=False, unique_filename=True, overwrite=False, chunk_size=6_000_000,
    )
    secure_url = str(result.get("secure_url") or "").strip()
    if not secure_url.startswith("https://res.cloudinary.com/"):
        raise RuntimeError("Cloudinary did not return a stable HTTPS URL.")
    print("Stable Cloudinary media URL ready for Buffer.")
    return secure_url


def prepare_candidate(item: dict) -> str | None:
    with tempfile.TemporaryDirectory(prefix="ruchi-reel-") as tmp:
        tmpdir = Path(tmp)
        source = tmpdir / "source.mp4"
        normalized = tmpdir / "instagram-ready.mp4"
        download_candidate(item, source)
        if face_heavy(source):
            print(f"SKIP FACE-HEAVY: {item['url']}")
            return None
        normalize_video(source, normalized)
        return host_on_cloudinary(normalized)


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
        json={"query": query, "variables": variables or {}}, timeout=45,
    )
    payload = r.json()
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
        id status sentAt externalLink
        error { message rawError supportUrl }
      }
    }
    """
    return (buffer_graphql(query, {"id": post_id}).get("post") or {})


def buffer_error_text(post: dict) -> str:
    err = post.get("error") or {}
    return " | ".join(str(err.get(k)) for k in ("message", "rawError", "supportUrl") if err.get(k)) or "Buffer publishing error"


def create_buffer_reel(channel_id: str, caption: str, video_url: str) -> str:
    mutation = """
    mutation CreateInstagramReel($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id status sentAt externalLink error { message rawError supportUrl } } }
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
    result = (buffer_graphql(mutation, variables).get("createPost") or {})
    if result.get("message"):
        raise RuntimeError("Buffer rejected Reel: " + str(result["message"]))
    post = result.get("post") or {}
    post_id = str(post.get("id") or "").strip()
    if not post_id:
        raise RuntimeError(f"Buffer did not return post id: {result}")
    status = str(post.get("status") or "").lower()
    print(f"BUFFER POST CREATED | id={post_id} | status={status or 'unknown'}")
    if status == "error":
        raise RuntimeError("Buffer publishing failed: " + buffer_error_text(post))
    if status == "sent":
        return post_id
    for attempt in range(1, BUFFER_MAX_CHECKS + 1):
        time.sleep(BUFFER_POLL_SECONDS)
        post = buffer_post_status(post_id)
        status = str(post.get("status") or "").lower()
        print(f"Buffer publish check {attempt}/{BUFFER_MAX_CHECKS} | id={post_id} | status={status or 'unknown'}")
        if status == "sent":
            print("BUFFER PUBLISH CONFIRMED |", post.get("externalLink") or "link not returned")
            return post_id
        if status == "error":
            raise RuntimeError("Buffer publishing failed: " + buffer_error_text(post))
    raise RuntimeError(f"Buffer publish not confirmed within {BUFFER_MAX_CHECKS * BUFFER_POLL_SECONDS} seconds for post {post_id}.")


def main() -> int:
    channel_id = "" if DRY_RUN else resolve_instagram_channel()
    seen = load_history()
    candidates = mixed_candidates(seen)
    if not candidates:
        raise RuntimeError("No unseen approved Instagram/Pinterest candidate found.")

    if DRY_RUN:
        print(f"DRY RUN candidates available: {len(candidates)}")
        return 0

    tested = 0
    errors = []
    for picked in candidates:
        if tested >= MAX_CANDIDATES_TO_TEST:
            break
        tested += 1
        print(f"Testing candidate {tested}: {picked['url']} from {picked['origin']}")
        try:
            stable_video_url = prepare_candidate(picked)
            if not stable_video_url:
                continue
            create_buffer_reel(channel_id, build_caption(picked.get("caption", "")), stable_video_url)
            append_history(picked["url"])
            print("UPLOAD CONFIRMED ON INSTAGRAM VIA BUFFER AND HISTORY RECORDED")
            return 0
        except Exception as exc:
            errors.append(f"{picked['url']}: {exc}")
            print("Candidate failed, trying next:", exc)

    raise RuntimeError("No suitable non-face-heavy candidate could be published. " + " | ".join(errors[-3:]))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise
