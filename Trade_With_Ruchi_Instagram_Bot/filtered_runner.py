from __future__ import annotations

import random
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import cv2
import pytesseract
import requests
from yt_dlp import YoutubeDL

import app

# Keep the priority source first, but avoid repeatedly hitting Instagram profile
# endpoints from GitHub-hosted runners. Discovery is done through public web
# search results; Instagram itself is contacted only when an individual Reel is
# selected for download.
app.PROFILES_PER_RUN = 2
app.REELS_PER_PROFILE = max(app.REELS_PER_PROFILE, 3)
app.MAX_CANDIDATES_TO_TEST = max(app.MAX_CANDIDATES_TO_TEST, 12)
PRIORITY_PROFILE = "sonamrajpoot932"
BROWSER_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1"
)

PROFILE_PATTERNS = [
    re.compile(r"@[a-z0-9_.]{3,}", re.I),
    re.compile(r"\btrade\s*with\s+[a-z0-9_.]{2,}", re.I),
    re.compile(r"\btrading\s*(?:room|official|signals?|academy|channel|club|king|queen|pro)\b", re.I),
]
PROFILE_UI_WORDS = ("instagram", "follow", "followers", "following", "profile", "telegram", "youtube")
TRADING_WORDS = ("trade", "trader", "trading", "forex", "quotex", "binary", "signals")


def _clean_search_href(href: str) -> str:
    href = unquote(str(href or "").strip())
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc:
        target = (parse_qs(parsed.query).get("uddg") or [""])[0]
        if target:
            href = unquote(target)
    return href


def web_search_urls(query: str, required_fragment: str, limit: int = 8) -> list[str]:
    """Best-effort keyless discovery through DuckDuckGo HTML results."""
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=25,
        )
        if not r.ok:
            print(f"Search discovery HTTP {r.status_code} for: {query}")
            return []
        links = re.findall(r'href=["\']([^"\']+)["\']', r.text, flags=re.I)
        out: list[str] = []
        for raw in links:
            url = _clean_search_href(raw)
            if required_fragment.lower() not in url.lower():
                continue
            url = url.split("?")[0]
            if url not in out:
                out.append(url)
            if len(out) >= limit:
                break
        return out
    except Exception as exc:
        print(f"Search discovery failed for {query}: {exc}")
        return []


def free_profile_candidates(handle: str, seen: set[str]) -> list[dict]:
    queries = [
        f'site:instagram.com/reel/ "{handle}"',
        f'site:instagram.com/reels/ "{handle}"',
    ]
    urls: list[str] = []
    for query in queries:
        for url in web_search_urls(query, "instagram.com/reel/", limit=app.REELS_PER_PROFILE * 2):
            if url not in urls:
                urls.append(url)
        if len(urls) >= app.REELS_PER_PROFILE:
            break

    out: list[dict] = []
    for reel_url in urls:
        if reel_url in seen:
            continue
        out.append({
            "url": reel_url,
            "caption": "",
            "video_url": "",
            "taken_at": "",
            "origin": f"instagram-search:@{handle}",
            "priority": handle.lower() == PRIORITY_PROFILE,
        })
        if len(out) >= app.REELS_PER_PROFILE:
            break
    print(f"@{handle}: {len(out)} search-discovered Instagram candidate(s)")
    return out


def priority_instagram_candidates(seen: set[str]) -> list[dict]:
    profiles = [app.username(x) for x in app.read_urls(app.PROFILES_FILE)]
    profiles = [x for x in profiles if x]
    priority = next((x for x in profiles if x.lower() == PRIORITY_PROFILE), None)
    others = [x for x in profiles if x.lower() != PRIORITY_PROFILE]
    random.shuffle(others)
    selected = ([priority] if priority else []) + others[:1]
    print("Instagram search discovery (priority first):", ", ".join("@" + u for u in selected))

    found: list[dict] = []
    for u in selected:
        found.extend(free_profile_candidates(u, seen))

    dedup: dict[str, dict] = {}
    for item in found:
        dedup.setdefault(item["url"], item)
    found = list(dedup.values())
    found.sort(key=lambda x: bool(x.get("priority")), reverse=True)
    return found


def _pinterest_username_from_url(url: str) -> str:
    try:
        p = urlparse(url)
        parts = [x for x in p.path.split("/") if x]
        if not parts or parts[0].lower() in {"pin", "ideas", "search"}:
            return ""
        return parts[0]
    except Exception:
        return ""


def resilient_pinterest_candidates(seen: set[str]) -> list[dict]:
    out: list[dict] = []
    headers = {"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"}

    for source in app.read_urls(app.PINTEREST_FILE):
        if len(out) >= 16:
            break
        final_url = source
        try:
            r = requests.get(source, headers=headers, timeout=20, allow_redirects=True)
            final_url = str(r.url or source)
        except Exception as exc:
            print(f"Pinterest source resolve warning: {source} | {exc}")

        if "/pin/" in final_url.lower():
            pin = final_url.split("?")[0]
            if pin not in seen and all(x["url"] != pin for x in out):
                out.append({"url": pin, "caption": "", "video_url": "", "taken_at": "", "origin": "pinterest"})
            continue

        username = _pinterest_username_from_url(final_url)
        if not username:
            continue
        queries = [
            f'site:pinterest.com/pin/ "{username}"',
            f'site:pinterest.com/pin/ {username} trading',
        ]
        for query in queries:
            pins = web_search_urls(query, "pinterest.com/pin/", limit=4)
            for pin in pins:
                pin = pin.split("?")[0]
                if pin in seen or any(x["url"] == pin for x in out):
                    continue
                out.append({"url": pin, "caption": "", "video_url": "", "taken_at": "", "origin": "pinterest"})
                if len(out) >= 16:
                    break
            if pins:
                break

    print(f"Pinterest resolved/search pool: {len(out)} candidate(s)")
    return out


def priority_mixed_candidates(seen: set[str]) -> list[dict]:
    ig = priority_instagram_candidates(seen)
    priority = [x for x in ig if x.get("priority")]
    other_ig = [x for x in ig if not x.get("priority")]
    direct = app.direct_candidates(seen)
    pinterest = resilient_pinterest_candidates(seen)
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
        "socket_timeout": 35,
        "retries": 1,
        "fragment_retries": 1,
        "http_headers": {"User-Agent": BROWSER_UA, "Referer": "https://www.instagram.com/"},
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
    direct = str(item.get("video_url") or "").strip()
    if direct.startswith("https://"):
        return direct
    # Skip the exhausted paid discovery path for search-discovered Reels.
    if str(item.get("origin") or "").startswith("instagram-search"):
        return free_instagram_video_url(item)
    try:
        return app._original_instagram_video_url(item)
    except Exception as exc:
        print(f"Instagram API media lookup unavailable; using free media fallback: {exc}")
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
app.pinterest_candidates = resilient_pinterest_candidates
app.mixed_candidates = priority_mixed_candidates
app.prepare_candidate = filtered_prepare_candidate

if __name__ == "__main__":
    try:
        raise SystemExit(app.main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise
