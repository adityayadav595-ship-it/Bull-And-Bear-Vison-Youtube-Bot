from __future__ import annotations
import os, yaml
from dotenv import load_dotenv
load_dotenv()

def env_bool(name, default=False):
    v=os.getenv(name)
    return default if v is None else v.strip().lower() in {"1","true","yes","y","on"}

def load_config(path="config.yaml"):
    with open(path,"r",encoding="utf-8") as f:
        cfg=yaml.safe_load(f) or {}
    cfg.setdefault("youtube",{}); cfg.setdefault("metadata",{}); cfg.setdefault("discovery",{})
    cfg["client_id"]=os.getenv("YOUTUBE_CLIENT_ID","").strip()
    cfg["client_secret"]=os.getenv("YOUTUBE_CLIENT_SECRET","").strip()
    cfg["refresh_token"]=os.getenv("YOUTUBE_REFRESH_TOKEN","").strip()
    cfg["rights_confirmed"]=env_bool("I_HAVE_RIGHTS_TO_REPOST",False)
    cfg["cookies_file"]=os.getenv("PINTEREST_COOKIES_FILE","").strip() or None
    cfg["brand"]=os.getenv("CHANNEL_BRAND","Bull & Bear Vision").strip()
    yt=cfg["youtube"]
    yt["privacy"]=os.getenv("YOUTUBE_PRIVACY",yt.get("privacy","public"))
    yt["made_for_kids"]=env_bool("MADE_FOR_KIDS",bool(yt.get("made_for_kids",False)))
    yt["contains_synthetic_media"]=env_bool("CONTAINS_SYNTHETIC_MEDIA",bool(yt.get("contains_synthetic_media",False)))
    return cfg
