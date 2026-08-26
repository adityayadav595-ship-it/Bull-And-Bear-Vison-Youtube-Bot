from __future__ import annotations
from pathlib import Path

from bot.config import load_config
from bot.history import load_history, append_history
from bot.downloader import (
    read_sources,
    discover_from_source,
    download_candidate,
    source_key,
)
from bot.ranker import choose_random
from bot.metadata import build_metadata
from bot.youtube import get_youtube, upload_video


CFG = load_config()


def collect_candidates():
    history_path = CFG.get("history_file", "uploaded_ids.txt")
    seen = load_history(history_path)

    sources = read_sources(
        CFG.get("sources_file", "pinterest_sources.txt")
    )

    if not sources:
        raise RuntimeError(
            "No approved Pinterest sources configured."
        )

    unseen = []

    for source in sources:
        print("Checking source:", source)

        try:
            items = discover_from_source(
                source,
                CFG
            )
        except Exception as e:
            print("Discovery failed:", e)
            continue

        for item in items:
            key = source_key(
                item["url"],
                item.get("id", "")
            )

            if key in seen:
                print("Already uploaded, skipping:", item["url"])
                continue

            item["_key"] = key
            unseen.append(item)

    print("Total videos found:", len(seen))
    return seen


def main():
    if not CFG.get("rights_confirmed"):
        raise RuntimeError(
            "I_HAVE_RIGHTS_TO_REPOST must be true."
        )

    candidates = collect_candidates()

    if not candidates:
        print("No seen eligible video found.")
        return

    picked = choose_random_unseen(candidates)

    print("Random video selected:")
    print("Title:", picked.get("title"))
    print("URL:", picked["url"])

    file_path = None

    try:
        print("Downloading selected video...")
        file_path, full_info = download_candidate(
            picked,
            CFG
        )

        print("Generating metadata...")
        meta = build_metadata(
            full_info,
            CFG
        )

        print("Connecting to YouTube...")
        youtube = get_youtube(CFG)

        print("Uploading to YouTube...")
        video_id = upload_video(
            youtube,
            file_path,
            meta,
            CFG
        )

        print("SUCCESS:", video_id)

        append_history(
            CFG.get("history_file", "uploaded_ids.txt"),
            picked["_key"]
        )

        print("Saved to upload history.")

    finally:
        if file_path and Path(file_path).exists():
            try:
                Path(file_path).unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
