from pathlib import Path
from bot.config import load_config
from bot.history import load_history, append_history
from bot.downloader import read_sources, discover_from_source, download_candidate, source_key
from bot.ranker import choose_random_from_best, candidate_score
from bot.metadata import build_metadata
from bot.youtube import get_youtube, upload_video
CFG=load_config()

def collect_unseen():
    seen=load_history(CFG.get("history_file","uploaded_ids.txt")); sources=read_sources(CFG.get("sources_file","pinterest_sources.txt"))
    if not sources: raise RuntimeError("No approved Pinterest sources configured.")
    out=[]
    for source in sources:
        print("Checking source:",source)
        try: items=discover_from_source(source,CFG)
        except Exception as e: print("Discovery failed:",e); continue
        for item in items:
            k=source_key(item["url"],item.get("id",""))
            if k in seen: continue
            item["_key"]=k; item["_score"]=candidate_score(item,CFG); out.append(item)
    return out

def main():
    if not CFG.get("rights_confirmed"): raise RuntimeError("I_HAVE_RIGHTS_TO_REPOST must be true for approved/licensed sources.")
    candidates=collect_unseen()
    if not candidates: print("No unseen eligible video found."); return
    picked=choose_random_from_best(candidates,CFG); print("Picked:",picked.get("title"),"Score:",picked.get("_score"),"URL:",picked["url"])
    file_path=None
    try:
        file_path,full=download_candidate(picked,CFG); meta=build_metadata(full,CFG); youtube=get_youtube(CFG); video_id=upload_video(youtube,file_path,meta,CFG); print("SUCCESS:",video_id)
        append_history(CFG.get("history_file","uploaded_ids.txt"),picked["_key"]); print("Saved duplicate history.")
    finally:
        if file_path and Path(file_path).exists():
            try: Path(file_path).unlink()
            except OSError: pass
if __name__=="__main__": main()
