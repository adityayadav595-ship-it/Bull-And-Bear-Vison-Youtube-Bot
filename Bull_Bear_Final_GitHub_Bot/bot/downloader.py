from __future__ import annotations
from pathlib import Path
import hashlib, yt_dlp
VIDEO_EXTS={"mp4","mov","mkv","webm","m4v"}

def source_key(url,item_id=""):
    return hashlib.sha256(f"{item_id}|{url}".encode()).hexdigest()

def read_sources(path):
    p=Path(path)
    if not p.exists(): return []
    return [s for s in (x.strip() for x in p.read_text(encoding="utf-8").splitlines()) if s and not s.startswith("#")]

def _opts(cfg,download=False):
    o={"quiet":True,"no_warnings":True,"ignoreerrors":True,"noplaylist":False}
    if cfg.get("cookies_file"): o["cookiefile"]=cfg["cookies_file"]
    if download:
        d=Path(cfg.get("downloads_dir","downloads")); d.mkdir(parents=True,exist_ok=True)
        o.update({"format":"bv*+ba/b","merge_output_format":"mp4","outtmpl":str(d/"%(extractor)s-%(id)s.%(ext)s"),"restrictfilenames":True})
    else: o["extract_flat"]="in_playlist"
    return o

def discover_from_source(source_url,cfg):
    with yt_dlp.YoutubeDL(_opts(cfg,False)) as ydl: info=ydl.extract_info(source_url,download=False)
    if not info: return []
    entries=info.get("entries") or [info]; out=[]
    for e in entries:
        if not e: continue
        url=e.get("webpage_url") or e.get("url")
        if not url: continue
        out.append({"url":url,"id":str(e.get("id") or ""),"title":(e.get("title") or e.get("description") or "Trading Short").strip(),"description":(e.get("description") or "").strip(),"duration":e.get("duration"),"timestamp":e.get("timestamp") or e.get("release_timestamp") or 0,"view_count":e.get("view_count") or 0,"like_count":e.get("like_count") or 0})
    return out[:int(cfg.get("discovery",{}).get("max_candidates_per_source",40))]

def download_candidate(item,cfg):
    with yt_dlp.YoutubeDL(_opts(cfg,True)) as ydl:
        info=ydl.extract_info(item["url"],download=True)
        if not info: raise RuntimeError("Could not extract/download this Pinterest item.")
        p=Path(ydl.prepare_filename(info))
        if not p.exists():
            stem=p.with_suffix("")
            matches=[m for m in stem.parent.glob(stem.name+".*") if m.suffix.lower().lstrip(".") in VIDEO_EXTS]
            if not matches: raise FileNotFoundError("Downloaded media file not found.")
            p=matches[0]
        meta={"url":info.get("webpage_url") or item["url"],"id":str(info.get("id") or item.get("id") or ""),"title":(info.get("title") or item.get("title") or "Trading Short").strip(),"description":(info.get("description") or item.get("description") or "").strip(),"duration":info.get("duration") or item.get("duration"),"view_count":info.get("view_count") or item.get("view_count") or 0,"like_count":info.get("like_count") or item.get("like_count") or 0}
        return str(p),meta
