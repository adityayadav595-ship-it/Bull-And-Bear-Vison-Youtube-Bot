from __future__ import annotations

import random
import re
import tempfile
from pathlib import Path

import cv2
import pytesseract
from yt_dlp import YoutubeDL

import app

app.PROFILES_PER_RUN = max(app.PROFILES_PER_RUN, 5)
app.REELS_PER_PROFILE = max(app.REELS_PER_PROFILE, 4)

PRIORITY_PROFILE = "sonamrajpoot932"

PROFILE_PATTERNS = [
    re.compile(r"@[a-z0-9_.]{3,}", re.I),
    re.compile(r"\btrade\s*with\s+[a-z0-9_.]{2,}", re.I),
    re.compile(r"\btrading\s*(?:room|official|signals?|academy|channel|club|king|queen|pro)\b", re.I),
]
PROFILE_UI_WORDS = ("instagram", "follow", "followers", "following", "profile", "telegram", "youtube")
TRADING_WORDS = ("trade", "trader", "trading", "forex", "quotex", "binary", "signals")


def free_profile_candidates(handle: str, seen: set[str]) -> list[dict]:
    profile_url = f"https://www.instagram.com/{handle}/reels/"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlistend": max(8, app.REELS_PER_PROFILE * 3),
        "socket_timeout": 35,
        "http_headers": {"User-Agent": app.UA},
    }
    out: list[dict] = []
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)
        for entry in (info or {}).get("entries") or []:
            if len(out) >= app.REELS_PER_PROFILE:
                break
            if not isinstance(entry, dict):
                continue
            code = str(entry.get("id") or "").strip()
            reel_url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
            if reel_url and not reel_url.startswith("http"):
                reel_url = ""
            if not reel_url and code:
                reel_url = f"https://www.instagram.com/reel/{code}/"
            if not reel_url or reel_url in seen:
                continue
            out.append({
                "url": reel_url,
                "caption": str(entry.get("title") or entry.get("description") or ""),
                "video_url": "",
                "taken_at": str(entry.get("timestamp") or entry.get("upload_date") or ""),
                "origin": f"instagram-free:@{handle}",
                "priority": handle.lower() == PRIORITY_PROFILE,
            })
    except Exception as exc:
        print(f"Free Instagram discovery @{handle} failed: {exc}")
    print(f"@{handle}: {len(out)} free Instagram candidate(s)")
    return out


def priority_instagram_candidates(seen: set[str]) -> list[dict]:
    profiles = [app.username(x) for x in app.read_urls(app.PROFILES_FILE)]
    profiles = [x for x in profiles if x]
    priority = next((x for x in profiles if x.lower() == PRIORITY_PROFILE), None)
    others = [x for x in profiles if x.lower() != PRIORITY_PROFILE]
    random.shuffle(others)
    selected = ([priority] if priority else []) + others[: max(0, app.PROFILES_PER_RUN - (1 if priority else 0))]
    print("Instagram scanning (priority first):", ", ".join("@" + u for u in selected))

    found: list[dict] = []
    for u in selected:
        api_ok = False
        try:
            payload = app.ig_get("/profile/reels", {"handle": u})
            data = payload.get("data") or {}
            items = (data.get("items") if isinstance(data, dict) else []) or []
            count = 0
            for item in items:
                if count >= app.REELS_PER_PROFILE:
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
                    "priority": u.lower() == PRIORITY_PROFILE,
                })
                count += 1
            api_ok = True
            print(f"@{u}: {count} API candidate(s)")
        except Exception as exc:
            print(f"Instagram API @{u} unavailable; switching to free fallback: {exc}")
        if not api_ok:
            found.extend(free_profile_candidates(u, seen))

    dedup: dict[str, dict] = {}
    for item in found:
        dedup.setdefault(item["url"], item)
    found = list(dedup.values())
    found.sort(key=lambda x: (bool(x.get("priority")), x.get("taken_at", "")), reverse=True)
    return found


def priority_mixed_candidates(seen: set[str]) -> list[dict]:
    ig = priority_instagram_candidates(seen)
    priority = [x for x in ig if x.get("priority")]
    other_ig = [x for x in ig if not x.get("priority")]
    direct = app.direct_candidates(seen)
    pinterest = app.pinterest_candidates(seen)
    rest = direct + other_ig + pinterest
    random.shuffle(rest)
    print(f"Candidate pool | priority={len(priority)} | other_ig={len(other_ig)} | direct={len(direct)} | pinterest={len(pinterest)}")
    return priority + rest


def free_instagram_video_url(item: dict) -> str:
    direct = str(item.get("video_url") or "").strip()
    if direct.startswith("https://"):
        return direct
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "best[ext=mp4]/best",
        "socket_timeout": 45,
        "http_headers": {"User-Agent": app.UA},
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(item["url"], download=False)
    video = str((info or {}).get("url") or "").strip()
    if not video.startswith("https://"):
        for fmt in reversed((info or {}).get("formats") or []):
            candidate = str(fmt.get("url") or "").strip()
            if candidate.startswith("https://") and str(fmt.get("vcodec") or "none") != "none":
                video = candidate
                break
    if not video.startswith("https://"):
        raise RuntimeError("Free Instagram fetcher did not return a usable video URL.")
    return video


def instagram_video_url_with_fallback(item: dict) -> str:
    try:
        return app._original_instagram_video_url(item)
    except Exception as exc:
        print(f"Instagram API media lookup unavailable; using free yt-dlp fallback: {exc}")
        return free_instagram_video_url(item)


def frame_has_foreign_profile_text(frame) -> tuple[bool, str]:
    h, w = frame.shape[:2]
    scale = 1.5 if max(h, w) < 1600 else 1.0
    if scale != 1.0:
        frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    text = pytesseract.image_to_string(gray, config="--psm 11", timeout=8)
    clean = " ".join(text.lower().split())
    if not clean:
        return False, ""
    for pattern in PROFILE_PATTERNS:
        match = pattern.search(clean)
        if match:
            return True, match.group(0)[:80]
    if any(word in clean for word in TRADING_WORDS) and any(word in clean for word in PROFILE_UI_WORDS):
        return True, clean[:120]
    return False, ""


def branded_trading_profile(video_path: Path) -> bool:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("OCR filter could not inspect video; candidate skipped for safety.")
        return True
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    hits = 0
    checked = 0
    examples = []
    for i in range(10):
        if frames > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((frames - 1) * i / 9))
        ok, frame = cap.read()
        if not ok:
            continue
        checked += 1
        try:
            hit, example = frame_has_foreign_profile_text(frame)
        except Exception as exc:
            print(f"OCR frame {i + 1} warning: {exc}")
            continue
        if hit:
            hits += 1
            if example and example not in examples:
                examples.append(example)
    cap.release()
    reject = hits >= 2 or (hits >= 1 and any(x.startswith("@") for x in examples))
    print(f"Trading-profile OCR filter: {hits}/{checked} frame(s) matched | {'SKIP' if reject else 'ALLOW'}")
    return reject


def filtered_prepare_candidate(item: dict) -> str | None:
    with tempfile.TemporaryDirectory(prefix="ruchi-filtered-reel-") as tmp:
        source = Path(tmp) / "source.mp4"
        normalized = Path(tmp) / "instagram-ready.mp4"
        app.download_candidate(item, source)
        if app.face_heavy(source):
            print(f"SKIP FACE-HEAVY: {item['url']}")
            return None
        if branded_trading_profile(source):
            print(f"SKIP TRADING PROFILE/WATERMARK: {item['url']}")
            return None
        app.normalize_video(source, normalized)
        return app.host_on_cloudinary(normalized)


app._original_instagram_video_url = app.instagram_video_url
app.instagram_video_url = instagram_video_url_with_fallback
app.instagram_candidates = priority_instagram_candidates
app.mixed_candidates = priority_mixed_candidates
app.prepare_candidate = filtered_prepare_candidate

if __name__ == "__main__":
    try:
        raise SystemExit(app.main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise
