\
from __future__ import annotations
from pathlib import Path
from typing import Iterable
import yt_dlp

VIDEO_EXTS = {"mp4","mov","mkv","webm","m4v"}

def _ydl_opts(cfg: dict, download: bool=False) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "noplaylist": False,
    }
    if cfg.get("cookies_file"):
        opts["cookiefile"] = cfg["cookies_file"]
    if download:
        Path(cfg["downloads_dir"]).mkdir(parents=True, exist_ok=True)
        opts.update({
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(Path(cfg["downloads_dir"]) / "%(extractor)s-%(id)s.%(ext)s"),
            "restrictfilenames": True,
        })
    else:
        opts["extract_flat"] = "in_playlist"
    return opts

def read_sources(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out

def discover_from_source(source_url: str, cfg: dict) -> list[dict]:
    max_candidates = int(cfg.get("discovery",{}).get("max_candidates_per_source",30))
    with yt_dlp.YoutubeDL(_ydl_opts(cfg, download=False)) as ydl:
        info = ydl.extract_info(source_url, download=False)

    if not info:
        return []

    entries = info.get("entries")
    if entries is None:
        entries = [info]

    candidates = []
    for e in entries:
        if not e:
            continue
        url = e.get("webpage_url") or e.get("url")
        if not url:
            continue
        candidates.append({
            "url": url,
            "id": str(e.get("id") or ""),
            "title": (e.get("title") or e.get("description") or "Trading Short").strip(),
            "description": (e.get("description") or "").strip(),
            "timestamp": e.get("timestamp") or e.get("release_timestamp") or 0,
        })

    if cfg.get("discovery",{}).get("newest_first", True):
        candidates.sort(key=lambda x: x.get("timestamp") or 0, reverse=True)
    return candidates[:max_candidates]

def download_candidate(candidate: dict, cfg: dict) -> tuple[str, dict]:
    url = candidate["url"]
    with yt_dlp.YoutubeDL(_ydl_opts(cfg, download=True)) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("yt-dlp could not extract this Pinterest video.")
        filename = ydl.prepare_filename(info)
        p = Path(filename)

        # yt-dlp may merge to mp4 even when prepare_filename reports another ext.
        if not p.exists():
            stem = p.with_suffix("")
            matches = sorted(stem.parent.glob(stem.name + ".*"))
            matches = [m for m in matches if m.suffix.lower().lstrip(".") in VIDEO_EXTS]
            if not matches:
                raise FileNotFoundError(f"Downloaded media file not found for {url}")
            p = matches[0]

        merged = {
            "url": info.get("webpage_url") or url,
            "id": str(info.get("id") or candidate.get("id") or ""),
            "title": (info.get("title") or candidate.get("title") or "Trading Short").strip(),
            "description": (info.get("description") or candidate.get("description") or "").strip(),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
        }
        return str(p), merged
