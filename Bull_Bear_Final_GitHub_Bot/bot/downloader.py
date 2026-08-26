from __future__ import annotations

from pathlib import Path
import hashlib
import html
import random
import re
import urllib.request

import yt_dlp

VIDEO_EXTS = {"mp4", "mov", "mkv", "webm", "m4v"}
PIN_PATTERNS = [
    re.compile(r"/pin/([0-9]{6,})", re.I),
    re.compile(r'"pin_id"\s*:\s*"?([0-9]{6,})"?', re.I),
    re.compile(r'"pinId"\s*:\s*"?([0-9]{6,})"?', re.I),
]


def source_key(url, item_id=""):
    return hashlib.sha256(f"{item_id}|{url}".encode("utf-8")).hexdigest()


def read_sources(path):
    p = Path(path)
    if not p.exists():
        return []
    return [
        s for s in (x.strip() for x in p.read_text(encoding="utf-8").splitlines())
        if s and not s.startswith("#")
    ]


def _opts(cfg, download=False):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "noplaylist": False,
        "socket_timeout": 20,
    }
    if cfg.get("cookies_file"):
        opts["cookiefile"] = cfg["cookies_file"]

    if download:
        d = Path(cfg.get("downloads_dir", "downloads"))
        d.mkdir(parents=True, exist_ok=True)
        opts.update({
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(d / "%(extractor)s-%(id)s.%(ext)s"),
            "restrictfilenames": True,
        })
    else:
        opts["extract_flat"] = "in_playlist"
    return opts


def _resolve_short_url(url):
    if "pin.it/" not in url.lower():
        return url
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            resolved = response.geturl()
        print("Resolved Pinterest share URL:", url, "->", resolved)
        return resolved
    except Exception as e:
        print("Could not resolve Pinterest share URL:", url, e)
        return url


def _is_pin(url):
    return "/pin/" in url.lower()


def _fetch_profile_html(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def _get_profile_pin_urls(profile_url, cfg):
    print("Scanning Pinterest profile/board:", profile_url)
    pages = [profile_url]

    if "in.pinterest.com" in profile_url:
        pages.append(profile_url.replace("in.pinterest.com", "www.pinterest.com"))

    pin_ids = []
    seen = set()

    for url in pages:
        try:
            page = _fetch_profile_html(url)
        except Exception as e:
            print("Profile page fetch failed:", url, e)
            continue

        page = html.unescape(page).replace("\\/", "/")
        for pattern in PIN_PATTERNS:
            for match in pattern.finditer(page):
                pin_id = match.group(1)
                if pin_id not in seen:
                    seen.add(pin_id)
                    pin_ids.append(pin_id)

    random.shuffle(pin_ids)
    max_items = int(cfg.get("discovery", {}).get("max_candidates_per_source", 40))
    urls = [f"https://www.pinterest.com/pin/{pin_id}/" for pin_id in pin_ids[:max_items]]
    print("Pin IDs discovered from profile/board:", len(pin_ids), "| probing:", len(urls))
    return urls


def _probe_pin(pin_url, cfg):
    try:
        with yt_dlp.YoutubeDL(_opts(cfg, False)) as ydl:
            info = ydl.extract_info(pin_url, download=False)
    except Exception as e:
        print("Skipping non-video/unavailable pin:", pin_url, e)
        return None

    if not info:
        return None

    ext = (info.get("ext") or "").lower()
    formats = info.get("formats") or []
    has_video = ext in VIDEO_EXTS or any((f.get("vcodec") not in (None, "none")) for f in formats)
    if not has_video:
        return None

    return {
        "url": info.get("webpage_url") or pin_url,
        "id": str(info.get("id") or ""),
        "title": (info.get("title") or info.get("description") or "Trading Short").strip(),
        "description": (info.get("description") or "").strip(),
        "duration": info.get("duration"),
        "timestamp": info.get("timestamp") or info.get("release_timestamp") or 0,
        "view_count": info.get("view_count") or 0,
        "like_count": info.get("like_count") or 0,
    }


def discover_from_source(source_url, cfg):
    source_url = _resolve_short_url(source_url)

    if _is_pin(source_url):
        item = _probe_pin(source_url, cfg)
        return [item] if item else []

    pin_urls = _get_profile_pin_urls(source_url, cfg)
    candidates = []
    for pin_url in pin_urls:
        item = _probe_pin(pin_url, cfg)
        if item:
            candidates.append(item)

    print("Usable video candidates from source:", len(candidates))
    return candidates


def download_candidate(item, cfg):
    with yt_dlp.YoutubeDL(_opts(cfg, True)) as ydl:
        info = ydl.extract_info(item["url"], download=True)
        if not info:
            raise RuntimeError("Could not download Pinterest video.")

        p = Path(ydl.prepare_filename(info))
        if not p.exists():
            stem = p.with_suffix("")
            matches = [
                m for m in stem.parent.glob(stem.name + ".*")
                if m.suffix.lower().lstrip(".") in VIDEO_EXTS
            ]
            if not matches:
                raise FileNotFoundError("Downloaded video file not found.")
            p = matches[0]

        meta = {
            "url": info.get("webpage_url") or item["url"],
            "id": str(info.get("id") or item.get("id") or ""),
            "title": (info.get("title") or item.get("title") or "Trading Short").strip(),
            "description": (info.get("description") or item.get("description") or "").strip(),
            "duration": info.get("duration") or item.get("duration"),
            "view_count": info.get("view_count") or item.get("view_count") or 0,
            "like_count": info.get("like_count") or item.get("like_count") or 0,
        }
        return str(p), meta
