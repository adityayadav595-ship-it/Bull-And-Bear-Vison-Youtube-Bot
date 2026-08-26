from __future__ import annotations

from pathlib import Path
import random

from bot.config import load_config
from bot.downloader import (
    read_sources,
    discover_from_source,
    download_candidate,
)
from bot.ranker import choose_random
from bot.metadata import build_metadata
from bot.youtube import get_youtube, upload_video


CFG = load_config()


def collect_candidates():
    sources = read_sources(
        CFG.get(
            "sources_file",
            "pinterest_sources.txt"
        )
    )

    if not sources:
        raise RuntimeError(
            "No Pinterest sources configured."
        )

    candidates = []

    # Shuffle source order too
    random.shuffle(sources)

    for source in sources:

        print("Checking source:", source)

        try:
            items = discover_from_source(
                source,
                CFG
            )

        except Exception as e:
            print("Source discovery failed:", e)
            continue

        for item in items:

            if not item.get("url"):
                continue

            candidates.append(item)

    print(
        "Total video candidates:",
        len(candidates)
    )

    return candidates


def main():

    if not CFG.get("rights_confirmed"):
        raise RuntimeError(
            "I_HAVE_RIGHTS_TO_REPOST must be true."
        )

    candidates = collect_candidates()

    if not candidates:
        print(
            "No usable Pinterest video found."
        )
        return

    # Prefer lower-view videos,
    # random among best low-view pool.
    picked = choose_random(
        candidates,
        pool_size=8
    )

    if not picked:
        print("Nothing selected.")
        return

    file_path = None

    try:

        print("Downloading video...")

        file_path, full_info = download_candidate(
            picked,
            CFG
        )

        print(
            "Downloaded:",
            file_path
        )

        print(
            "Creating YouTube metadata..."
        )

        meta = build_metadata(
            full_info,
            CFG
        )

        print(
            "YouTube title:",
            meta["title"]
        )

        print(
            "Connecting to YouTube..."
        )

        youtube = get_youtube(
            CFG
        )

        print(
            "Uploading directly to YouTube..."
        )

        video_id = upload_video(
            youtube,
            file_path,
            meta,
            CFG
        )

        print(
            "UPLOAD SUCCESSFUL"
        )

        print(
            "YouTube video ID:",
            video_id
        )

    finally:

        if (
            file_path
            and Path(file_path).exists()
        ):

            try:
                Path(file_path).unlink()
                print(
                    "Temporary video deleted."
                )

            except OSError:
                pass


if __name__ == "__main__":
    main()
