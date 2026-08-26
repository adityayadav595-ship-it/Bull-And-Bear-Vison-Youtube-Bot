from __future__ import annotations

import traceback
from pathlib import Path

from bot.config import load_config
from bot.storage import Storage
from bot.downloader import read_sources, discover_from_source, download_candidate
from bot.metadata import build_metadata
from bot.youtube import get_youtube, upload_video


CFG = load_config()
STORE = Storage(CFG.get("database_file", "bot_state.sqlite3"))


def choose_candidate():
    sources = read_sources(CFG.get("sources_file", "pinterest_sources.txt"))

    if not sources:
        print("No Pinterest sources found in pinterest_sources.txt")
        return None

    for source in sources:
        print(f"Checking source: {source}")

        try:
            candidates = discover_from_source(source, CFG)
        except Exception as e:
            print(f"Discovery failed for {source}: {e}")
            continue

        for candidate in candidates:
            key = STORE.source_key(
                candidate["url"],
                candidate.get("id")
            )

            if not STORE.already_uploaded(key):
                candidate["_key"] = key
                return candidate

    return None


def run_once():
    print("=== Bull & Bear Auto Uploader ===")

    if not CFG.get("rights_confirmed"):
        raise RuntimeError(
            "I_HAVE_RIGHTS_TO_REPOST must be true for approved/licensed sources."
        )

    candidate = choose_candidate()

    if not candidate:
        print("No new unseen video found.")
        return

    file_path = None

    try:
        print(
            f"Selected: {candidate.get('title')} | "
            f"{candidate['url']}"
        )

        print("Downloading Pinterest video...")
        file_path, full_info = download_candidate(candidate, CFG)
        print(f"Download complete: {file_path}")

        print("Calculating file hash...")
        sha = STORE.sha256_file(file_path)

        print("Generating YouTube metadata...")
        meta = build_metadata(full_info, CFG)

        print("Generated metadata:")
        print("Title:", meta["title"])
        print("Category:", meta["category_id"])
        print("Tags:", ", ".join(meta["tags"]))

        print("Connecting to YouTube...")
        youtube = get_youtube(CFG)

        print("Starting YouTube upload...")
        video_id = upload_video(
            youtube,
            file_path,
            meta,
            CFG
        )

        STORE.mark_upload(
            key=candidate["_key"],
            source_url=candidate["url"],
            youtube_video_id=video_id,
            title=meta["title"],
            file_sha256=sha,
            status="uploaded",
        )

        print(f"SUCCESS: YouTube video ID = {video_id}")

    except Exception as e:
        print("UPLOAD FAILED")
        traceback.print_exc()

        STORE.mark_upload(
            key=candidate["_key"],
            source_url=candidate["url"],
            youtube_video_id=None,
            title=candidate.get("title", ""),
            file_sha256=(
                STORE.sha256_file(file_path)
                if file_path and Path(file_path).exists()
                else None
            ),
            status="failed",
            error=str(e),
        )

        raise

    finally:
        if file_path and Path(file_path).exists():
            if not CFG.get("keep_downloads", False):
                try:
                    Path(file_path).unlink()
                    print("Temporary download deleted.")
                except OSError:
                    pass


def main():
    run_once()
    print("Bot cycle finished. Exiting.")


if __name__ == "__main__":
    main()
