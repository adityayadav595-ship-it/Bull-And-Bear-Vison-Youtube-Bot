\
from __future__ import annotations
import os
import sys
import time
import traceback
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

from bot.config import load_config
from bot.storage import Storage
from bot.downloader import read_sources, discover_from_source, download_candidate
from bot.metadata import build_metadata
from bot.youtube import get_youtube, upload_video

CFG = load_config()
STORE = Storage(CFG.get("database_file","bot_state.sqlite3"))

def choose_candidate():
    sources = read_sources(CFG.get("sources_file","pinterest_sources.txt"))
    if not sources:
        print("No sources found. Add Pinterest URLs to pinterest_sources.txt")
        return None

    for source in sources:
        print(f"Checking: {source}")
        try:
            candidates = discover_from_source(source, CFG)
        except Exception as e:
            print(f"  Discovery failed: {e}")
            continue

        for c in candidates:
            key = STORE.source_key(c["url"], c.get("id"))
            if not STORE.already_uploaded(key):
                c["_key"] = key
                return c
    return None

def run_once():
    print("\n=== Bull & Bear Auto Uploader cycle ===")
    if not CFG.get("rights_confirmed"):
        print(
            "STOPPED: set I_HAVE_RIGHTS_TO_REPOST=true in .env only for sources "
            "you own or are licensed/authorized to repost."
        )
        return

    candidate = choose_candidate()
    if not candidate:
        print("No new unseen video found.")
        return

    file_path = None
    try:
        print(f"Selected: {candidate.get('title')} | {candidate['url']}")
        file_path, full_info = download_candidate(candidate, CFG)
        sha = STORE.sha256_file(file_path)
        meta = build_metadata(full_info, CFG)

        print("Generated metadata:")
        print("  Title:", meta["title"])
        print("  Category:", meta["category_id"])
        print("  Tags:", ", ".join(meta["tags"]))

        youtube = get_youtube(CFG)
        video_id = upload_video(youtube, file_path, meta, CFG)

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
        traceback.print_exc()
        STORE.mark_upload(
            key=candidate["_key"],
            source_url=candidate["url"],
            youtube_video_id=None,
            title=candidate.get("title",""),
            file_sha256=STORE.sha256_file(file_path) if file_path and Path(file_path).exists() else None,
            status="failed",
            error=str(e),
        )
    finally:
        if file_path and Path(file_path).exists() and not CFG.get("keep_downloads", False):
            try:
                Path(file_path).unlink()
            except OSError:
                pass

def main():
    if "--once" in sys.argv:
        run_once()
        return

    hours = int(CFG.get("post_every_hours",3))
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_once,
        "interval",
        hours=hours,
        max_instances=1,
        coalesce=True,
        id="youtube_short_upload",
    )

    if CFG.get("run_on_start", True):
        run_once()

    print(f"Scheduler running: one cycle every {hours} hour(s). Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
