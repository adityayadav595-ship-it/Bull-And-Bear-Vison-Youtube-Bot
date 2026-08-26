\
from __future__ import annotations
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()

def env_bool(name: str, default: bool=False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1","true","yes","y","on"}

def load_config(path: str="config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    cfg.setdefault("youtube", {})
    cfg.setdefault("metadata", {})
    cfg.setdefault("discovery", {})

    cfg["rights_confirmed"] = env_bool("I_HAVE_RIGHTS_TO_REPOST", False)
    cfg["cookies_file"] = os.getenv("PINTEREST_COOKIES_FILE", "").strip() or None
    cfg["client_secret"] = os.getenv("YOUTUBE_CLIENT_SECRET", "client_secret.json")
    cfg["token_file"] = os.getenv("YOUTUBE_TOKEN_FILE", "token.json")
    cfg["post_every_hours"] = max(1, int(os.getenv("POST_EVERY_HOURS", "3")))
    cfg["run_on_start"] = env_bool("RUN_ON_START", True)
    cfg["privacy"] = os.getenv("YOUTUBE_PRIVACY", "public").strip().lower()
    cfg["made_for_kids"] = env_bool("MADE_FOR_KIDS", False)
    cfg["contains_synthetic_media"] = env_bool("CONTAINS_SYNTHETIC_MEDIA", False)
    cfg["brand"] = os.getenv("CHANNEL_BRAND", "Bull & Bear Vision").strip()
    cfg["keep_downloads"] = env_bool("KEEP_DOWNLOADS", False)

    return cfg
