from __future__ import annotations

from pathlib import Path
import hashlib
import html
import re
import urllib.request

import yt_dlp

VIDEO_EXTS = {"mp4", "mov", "mkv", "webm", "m4v"}
PIN_RE = re.compile(r"/pin/([0-9]{6,})", re.I)


def source_key(url, item_id=""):
    return hashlib.sha256(
        f"{item_id}|{url}".encode()
    ).hexdigest()


def read_sources(path):
    p = Path(path)

    if not p.exists():
        return []

    return [
        s
        for s in (
            x.strip()
            for x in p.read_text(
                encoding="utf-8"
            ).splitlines()
        )
        if s and not s.startswith("#")
    ]


def _opts(cfg, download=False):

    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "noplaylist": False,
    }

    if cfg.get("cookies_file"):
        opts["cookiefile"] = cfg["cookies_file"]

    if download:

        d = Path(
            cfg.get(
                "downloads_dir",
                "downloads"
            )
        )

        d.mkdir(
            parents=True,
            exist_ok=True
        )

        opts.update({
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(
                d / "%(extractor)s-%(id)s.%(ext)s"
            ),
            "restrictfilenames": True,
        })

    else:

        opts["extract_flat"] = "in_playlist"

    return opts


def _is_pin(url):

    return "/pin/" in url.lower()


def _get_profile_pin_urls(profile_url, cfg):

    print(
        "Scanning Pinterest profile:",
        profile_url
    )

    request = urllib.request.Request(
        profile_url,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
        }
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=20
        ) as response:

            page = response.read().decode(
                "utf-8",
                errors="ignore"
            )

    except Exception as e:

        print(
            "Profile scan failed:",
            e
        )

        return []

    page = html.unescape(
        page
    ).replace("\\/", "/")

    pin_ids = []
    seen = set()

    for match in PIN_RE.finditer(page):

        pin_id = match.group(1)

        if pin_id in seen:
            continue

        seen.add(pin_id)
        pin_ids.append(pin_id)

    max_items = int(
        cfg.get(
            "discovery",
            {}
        ).get(
            "max_candidates_per_source",
            40
        )
    )

    urls = [
        f"https://www.pinterest.com/pin/{x}/"
        for x in pin_ids[:max_items]
    ]

    print(
        "Pins found from profile:",
        len(urls)
    )

    return urls


def _probe_pin(pin_url, cfg):

    try:

        with yt_dlp.YoutubeDL(
            _opts(cfg, False)
        ) as ydl:

            info = ydl.extract_info(
                pin_url,
                download=False
            )

    except Exception as e:

        print(
            "Skipping pin:",
            pin_url,
            e
        )

        return None

    if not info:
        return None

    return {
        "url":
            info.get("webpage_url")
            or pin_url,

        "id":
            str(
                info.get("id")
                or ""
            ),

        "title":
            (
                info.get("title")
                or info.get("description")
                or "Trading Short"
            ).strip(),

        "description":
            (
                info.get("description")
                or ""
            ).strip(),

        "duration":
            info.get("duration"),

        "timestamp":
            info.get("timestamp")
            or info.get("release_timestamp")
            or 0,

        "view_count":
            info.get("view_count")
            or 0,

        "like_count":
            info.get("like_count")
            or 0,
    }


def discover_from_source(source_url, cfg):

    # Direct Pin URL
    if _is_pin(source_url):

        item = _probe_pin(
            source_url,
            cfg
        )

        return [item] if item else []

    # Pinterest profile / board
    pin_urls = _get_profile_pin_urls(
        source_url,
        cfg
    )

    candidates = []

    for pin_url in pin_urls:

        item = _probe_pin(
            pin_url,
            cfg
        )

        if item:
            candidates.append(item)

    print(
        "Usable video candidates:",
        len(candidates)
    )

    return candidates


def download_candidate(item, cfg):

    with yt_dlp.YoutubeDL(
        _opts(cfg, True)
    ) as ydl:

        info = ydl.extract_info(
            item["url"],
            download=True
        )

        if not info:

            raise RuntimeError(
                "Could not download Pinterest video."
            )

        filename = ydl.prepare_filename(
            info
        )

        p = Path(filename)

        if not p.exists():

            stem = p.with_suffix("")

            matches = [
                m
                for m in stem.parent.glob(
                    stem.name + ".*"
                )
                if (
                    m.suffix
                    .lower()
                    .lstrip(".")
                    in VIDEO_EXTS
                )
            ]

            if not matches:

                raise FileNotFoundError(
                    "Downloaded video file not found."
                )

            p = matches[0]

        meta = {
            "url":
                info.get("webpage_url")
                or item["url"],

            "id":
                str(
                    info.get("id")
                    or item.get("id")
                    or ""
                ),

            "title":
                (
                    info.get("title")
                    or item.get("title")
                    or "Trading Short"
                ).strip(),

            "description":
                (
                    info.get("description")
                    or item.get("description")
                    or ""
                ).strip(),

            "duration":
                info.get("duration")
                or item.get("duration"),

            "view_count":
                info.get("view_count")
                or item.get("view_count")
                or 0,

            "like_count":
                info.get("like_count")
                or item.get("like_count")
                or 0,
        }

        return str(p), meta
