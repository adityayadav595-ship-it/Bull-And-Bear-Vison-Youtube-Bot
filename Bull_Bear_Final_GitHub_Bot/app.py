from __future__ import annotations

from pathlib import Path
import random
import sitecustomize

from bot.config import load_config
from bot.downloader import read_sources, discover_from_source, download_candidate, source_key
from bot.face_filter import video_contains_face
from bot.history import load_history, append_history, file_sha256
from bot.ranker import rank_candidates
from bot.metadata import build_metadata
from bot.policy_guard import append_metadata_history, channel_allows_upload, cooldown_reason, item_is_manually_approved, metadata_risk_reason, write_review_queue
from bot.youtube import get_youtube, upload_video, publish_private_video_after_delay

CFG = load_config()


def _duration_allowed(item: dict) -> bool:
    discovery = CFG.get("discovery", {})
    min_s = float(discovery.get("min_duration_seconds", 8) or 0)
    max_s = float(discovery.get("max_duration_seconds", 60) or 0)
    duration = item.get("duration")
    if duration in (None, "", 0): return True
    try: seconds = float(duration)
    except (TypeError, ValueError): return True
    if min_s and seconds < min_s:
        print(f"Skipping too-short candidate ({seconds:.1f}s):", item.get("url", "")); return False
    if max_s and seconds > max_s:
        print(f"Skipping too-long candidate ({seconds:.1f}s):", item.get("url", "")); return False
    return True


def _preferred_source(source: str) -> bool:
    preferred = CFG.get("discovery", {}).get("preferred_sources", []) or []
    return source.strip().rstrip("/") in {str(x).strip().rstrip("/") for x in preferred}


def _metadata_input(info: dict) -> dict:
    # Source captions are discovery context only. Never republish promotional/
    # guarantee wording from them; generate neutral Quotex-focused metadata.
    clean = dict(info)
    clean["title"] = "Quotex trading setup"
    clean["description"] = "Quotex trading setup and technical analysis example"
    return clean


def collect_candidates():
    sources = read_sources(CFG.get("sources_file", "approved_sources.txt"))
    if not sources:
        print("No approved sources configured. Safe no-op; nothing will be uploaded."); return []
    history_path = CFG.get("history_file", "uploaded_ids.txt")
    seen = load_history(history_path); candidates = []; discovered_this_run = set()
    random.shuffle(sources); sources.sort(key=lambda s: 0 if _preferred_source(s) else 1)
    for source in sources:
        preferred = _preferred_source(source)
        print("Checking approved source:", source, "[TOP PRIORITY]" if preferred else "")
        try: items = discover_from_source(source, CFG)
        except Exception as exc:
            print("Source discovery failed:", exc); continue
        for item in items:
            if not item or not item.get("url"): continue
            key = source_key(item["url"], item.get("id", ""))
            if key in seen or key in discovered_this_run:
                print("Already uploaded/discovered, skipping:", item["url"]); continue
            if not _duration_allowed(item): continue
            item["_history_key"] = key; item["_source_origin"] = source
            if preferred: item["_source_priority_bonus"] = float(CFG.get("discovery", {}).get("preferred_source_bonus", 14.0) or 0)
            candidates.append(item); discovered_this_run.add(key)
    print("Total unseen approved video candidates:", len(candidates)); return candidates


def _cleanup(file_path):
    if file_path and Path(file_path).exists():
        try: Path(file_path).unlink(); print("Temporary video deleted.")
        except OSError: pass


def main():
    candidates = collect_candidates()
    if not candidates: print("No approved video found this cycle."); return
    discovery_cfg = CFG.get("discovery", {}); pool_size = int(discovery_cfg.get("smart_pool_size", 8) or 8)
    ranked = rank_candidates(candidates, pool_size=pool_size)
    if not ranked: print("Nothing selected."); return
    write_review_queue(ranked, CFG)
    allowed, reason = channel_allows_upload(CFG)
    if not allowed:
        print("UPLOAD LOCKED:", reason); print("Review queue generated only; no YouTube API upload was attempted."); return
    if not CFG.get("rights_confirmed"):
        print("UPLOAD LOCKED: I_HAVE_RIGHTS_TO_REPOST is not true."); return
    wait_reason = cooldown_reason(CFG)
    if wait_reason: print("UPLOAD LOCKED:", wait_reason); return
    approved_ranked = [item for item in ranked if item_is_manually_approved(item, CFG)]
    if not approved_ranked:
        print("UPLOAD LOCKED: no candidate in this queue has explicit human approval."); return
    hash_history_path = CFG.get("hash_history_file", "uploaded_hashes.txt"); uploaded_hashes = load_history(hash_history_path)
    history_path = CFG.get("history_file", "uploaded_ids.txt"); youtube = None
    max_attempts = min(len(approved_ranked), int(discovery_cfg.get("max_candidate_attempts_per_run", 3) or 3))
    for attempt, picked in enumerate(approved_ranked[:max_attempts], start=1):
        file_path = None; stage = "prepare"
        print(f"Approved candidate attempt {attempt}/{max_attempts} | score={picked.get('_smart_score', 'n/a')} | reasons={','.join(picked.get('_smart_reasons') or [])}")
        try:
            print("Downloading approved video..."); file_path, full_info = download_candidate(picked, CFG)
            full_info["_source_origin"] = picked.get("_source_origin", "")
            full_info["_preferred_source"] = bool(picked.get("_source_priority_bonus"))
            print("Downloaded:", file_path)
            if not _duration_allowed(full_info): append_history(history_path, picked["_history_key"]); continue
            if full_info.get("platform") == "instagram" and CFG.get("face_filter", {}).get("instagram_skip_any_face", True):
                if video_contains_face(file_path, CFG): append_history(history_path, picked["_history_key"]); continue
            video_hash = file_sha256(file_path)
            if video_hash in uploaded_hashes: append_history(history_path, picked["_history_key"]); continue
            meta = build_metadata(_metadata_input(full_info), CFG)
            meta_risk = metadata_risk_reason(meta, CFG)
            if meta_risk:
                print("UPLOAD BLOCKED by generated-metadata guard:", meta_risk); continue
            print("YouTube title:", meta["title"]); stage = "upload"
            if youtube is None: youtube = get_youtube(CFG)
            video_id = upload_video(youtube, file_path, meta, CFG); print("PRIVATE UPLOAD SUCCESSFUL", video_id)
            append_history(history_path, picked["_history_key"]); append_history(hash_history_path, video_hash); append_metadata_history(meta, picked, video_id, CFG)
            publish_private_video_after_delay(youtube, video_id, CFG); return
        except Exception as exc:
            print(f"Candidate attempt failed: {type(exc).__name__}: {exc}")
            if stage == "upload" or attempt >= max_attempts: raise
        finally: _cleanup(file_path)
    print("No candidate passed all upload, duration, duplicate, and generated-metadata checks this cycle.")


if __name__ == "__main__": main()
