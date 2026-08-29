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
    re.compile(r'"id"\s*:\s*"([0-9]{12,})"', re.I),
]
INSTAGRAM_ITEM_PATTERNS = [
    re.compile(r'https?://(?:www\.)?instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]+)', re.I),
    re.compile(r'/(?:reel|reels|p)/([A-Za-z0-9_-]+)', re.I),
]


def source_key(url, item_id=""):
    return hashlib.sha256(f"{item_id}|{url}".encode("utf-8")).hexdigest()


def read_sources(path):
    p = Path(path)
    if not p.exists():
        return []
    return [s for s in (x.strip() for x in p.read_text(encoding="utf-8").splitlines()) if s and not s.startswith("#")]


def _opts(cfg, download=False, allow_playlist=False):
    opts = {"quiet": True, "no_warnings": True, "ignoreerrors": True, "noplaylist": not allow_playlist, "socket_timeout": 25}
    if cfg.get("cookies_file"):
        opts["cookiefile"] = cfg["cookies_file"]
    if download:
        d = Path(cfg.get("downloads_dir", "downloads")); d.mkdir(parents=True, exist_ok=True)
        opts.update({"format": "bv*+ba/b", "merge_output_format": "mp4", "outtmpl": str(d / "%(extractor)s-%(id)s.%(ext)s"), "restrictfilenames": True})
    return opts


def _resolve_short_url(url):
    if "pin.it/" not in url.lower(): return url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"})
        with urllib.request.urlopen(req, timeout=20) as response: resolved = response.geturl()
        print("Resolved Pinterest share URL:", url, "->", resolved); return resolved
    except Exception as e:
        print("Could not resolve Pinterest share URL:", url, e); return url


def _is_pin(url): return bool(re.search(r"https?://(?:www\.|in\.)?pinterest\.com/pin/[0-9]{6,}(?:/|\?|$)", url, re.I))
def _is_instagram(url): return bool(re.search(r"https?://(?:www\.)?instagram\.com/", url, re.I))
def _is_instagram_item(url): return bool(re.search(r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p)/[^/?#]+", url, re.I))


def _fetch_profile_html(url, mobile=False):
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1" if mobile else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36")
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=25) as response: return response.read().decode("utf-8", errors="ignore")


def _extract_pin_ids(page):
    page = html.unescape(page).replace("\\/", "/").replace("\\u002F", "/")
    ids=[]
    for pattern in PIN_PATTERNS: ids.extend(m.group(1) for m in pattern.finditer(page))
    return ids


def _get_profile_pin_urls(profile_url, cfg):
    print("Scanning Pinterest profile/board:", profile_url); base=profile_url.rstrip("/")+"/"; pages=[base]
    for host in ("www.pinterest.com","in.pinterest.com","pinterest.com"):
        variant=re.sub(r"https?://[^/]+",f"https://{host}",base)
        if variant not in pages: pages.append(variant)
    pin_ids,seen=[],set()
    for url in pages:
        for mobile in (False,True):
            try: page=_fetch_profile_html(url,mobile=mobile)
            except Exception as e: print("Profile page fetch failed:",url,e); continue
            for pin_id in _extract_pin_ids(page):
                if pin_id not in seen: seen.add(pin_id); pin_ids.append(pin_id)
    random.shuffle(pin_ids); max_items=int(cfg.get("discovery",{}).get("max_candidates_per_source",10))
    return [f"https://www.pinterest.com/pin/{x}/" for x in pin_ids[:max_items]]


def _item_from_info(info,fallback_url,platform):
    if not info: return None
    ext=(info.get("ext") or "").lower(); formats=info.get("formats") or []
    has_video=ext in VIDEO_EXTS or any((f.get("vcodec") not in (None,"none")) for f in formats)
    if not has_video and info.get("_type") not in ("url","url_transparent"): return None
    return {"url":info.get("webpage_url") or info.get("url") or fallback_url,"id":str(info.get("id") or ""),"title":(info.get("title") or info.get("description") or "Trading Short").strip(),"description":(info.get("description") or "").strip(),"duration":info.get("duration"),"timestamp":info.get("timestamp") or info.get("release_timestamp") or 0,"view_count":info.get("view_count") or 0,"like_count":info.get("like_count") or 0,"platform":platform}


def _probe_pin(pin_url,cfg):
    try:
        with yt_dlp.YoutubeDL(_opts(cfg,False)) as ydl: info=ydl.extract_info(pin_url,download=False)
    except Exception as e: print("Skipping non-video/unavailable pin:",pin_url,e); return None
    return _item_from_info(info,pin_url,"pinterest")


def _fastdl_url(instagram_url):
    # FastDL documents this address-bar shortcut for public Instagram item URLs.
    return "https://f-d.app/" + instagram_url


def _probe_fastdl(instagram_url,cfg):
    try:
        fast_url=_fastdl_url(instagram_url)
        with yt_dlp.YoutubeDL(_opts(cfg,False)) as ydl: info=ydl.extract_info(fast_url,download=False)
        item=_item_from_info(info,instagram_url,"instagram")
        if item:
            item["url"]=instagram_url; item["download_url"]=fast_url
            print("FastDL fallback accepted Instagram item:",instagram_url)
        return item
    except Exception as e:
        print("FastDL probe failed:",instagram_url,e); return None


def _probe_instagram_item(url,cfg):
    try:
        with yt_dlp.YoutubeDL(_opts(cfg,False)) as ydl: info=ydl.extract_info(url,download=False)
        item=_item_from_info(info,url,"instagram")
        if item: return item
    except Exception as e: print("Direct Instagram probe failed; trying FastDL:",url,e)
    return _probe_fastdl(url,cfg)


def _instagram_profile_html_urls(profile_url,cfg):
    max_items=int(cfg.get("discovery",{}).get("max_candidates_per_source",10)); found,seen=[],set()
    for mobile in (False,True):
        try: page=_fetch_profile_html(profile_url,mobile=mobile)
        except Exception as exc: print("Instagram HTML fallback fetch failed:",exc); continue
        normalized=html.unescape(page).replace("\\/","/").replace("\\u002F","/")
        for pattern in INSTAGRAM_ITEM_PATTERNS:
            for match in pattern.finditer(normalized):
                url=f"https://www.instagram.com/reel/{match.group(1)}/"
                if url not in seen: seen.add(url); found.append(url)
    random.shuffle(found); return found[:max_items*2]


def _discover_instagram_profile(profile_url,cfg):
    max_items=int(cfg.get("discovery",{}).get("max_candidates_per_source",10)); print("Scanning approved Instagram profile:",profile_url); urls,seen=[],set()
    opts=_opts(cfg,False,allow_playlist=True); opts.update({"extract_flat":True,"playlistend":max_items*2})
    try:
        with yt_dlp.YoutubeDL(opts) as ydl: info=ydl.extract_info(profile_url,download=False)
        for entry in (info or {}).get("entries") or []:
            if not entry: continue
            candidate_url=entry.get("webpage_url") or entry.get("url")
            if candidate_url and candidate_url not in seen: seen.add(candidate_url); urls.append(candidate_url)
    except Exception as e: print("Instagram profile yt-dlp discovery failed; trying HTML fallback:",e)
    if not urls:
        for candidate_url in _instagram_profile_html_urls(profile_url,cfg):
            if candidate_url not in seen: seen.add(candidate_url); urls.append(candidate_url)
    random.shuffle(urls); candidates=[]
    for url in urls[:max_items]:
        item=_probe_instagram_item(url,cfg)
        if item: candidates.append(item)
    if not candidates: print("No usable public Instagram Reel discovered from profile this cycle.")
    return candidates


def discover_from_source(source_url,cfg):
    source_url=_resolve_short_url(source_url)
    if _is_instagram(source_url):
        if _is_instagram_item(source_url):
            item=_probe_instagram_item(source_url,cfg); return [item] if item else []
        return _discover_instagram_profile(source_url,cfg)
    if cfg.get("discovery",{}).get("exact_pin_sources_only",True) and not _is_pin(source_url): print("Rejected unsupported/non-individual source:",source_url); return []
    if _is_pin(source_url):
        item=_probe_pin(source_url,cfg); return [item] if item else []
    candidates=[]
    for pin_url in _get_profile_pin_urls(source_url,cfg):
        item=_probe_pin(pin_url,cfg)
        if item: candidates.append(item)
    return candidates


def _download_with_ydl(target_url,cfg):
    with yt_dlp.YoutubeDL(_opts(cfg,True)) as ydl:
        info=ydl.extract_info(target_url,download=True)
        if not info: raise RuntimeError("Could not download source video.")
        p=Path(ydl.prepare_filename(info))
        if not p.exists():
            stem=p.with_suffix(""); matches=[m for m in stem.parent.glob(stem.name+".*") if m.suffix.lower().lstrip(".") in VIDEO_EXTS]
            if not matches: raise FileNotFoundError("Downloaded video file not found.")
            p=matches[0]
        return str(p),info


def download_candidate(item,cfg):
    target=item.get("download_url") or item["url"]
    try:
        p,info=_download_with_ydl(target,cfg)
    except Exception as direct_error:
        if item.get("platform")=="instagram" and not item.get("download_url"):
            print("Direct Instagram download failed; trying FastDL fallback:",direct_error)
            p,info=_download_with_ydl(_fastdl_url(item["url"]),cfg)
        else: raise
    meta={"url":item["url"],"id":str(info.get("id") or item.get("id") or ""),"title":(info.get("title") or item.get("title") or "Trading Short").strip(),"description":(info.get("description") or item.get("description") or "").strip(),"duration":info.get("duration") or item.get("duration"),"view_count":info.get("view_count") or item.get("view_count") or 0,"like_count":info.get("like_count") or item.get("like_count") or 0,"platform":item.get("platform") or ("instagram" if _is_instagram(item["url"]) else "pinterest")}
    return p,meta
