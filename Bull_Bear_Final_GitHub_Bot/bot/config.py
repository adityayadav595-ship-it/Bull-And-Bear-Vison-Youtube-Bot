from __future__ import annotations

import os
import yaml
from dotenv import load_dotenv

load_dotenv()


def env_bool(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}

    cfg.setdefault("youtube", {})
    cfg.setdefault("metadata", {})
    cfg.setdefault("discovery", {})
    cfg.setdefault("safety", {})

    cfg["client_id"] = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    cfg["client_secret"] = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    cfg["refresh_token"] = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()
    cfg["cookies_file"] = os.getenv("PINTEREST_COOKIES_FILE", "").strip() or None
    cfg["brand"] = os.getenv("CHANNEL_BRAND", "Bull & Bear Vision").strip()

    # Legacy blanket rights flag is retained only for backwards compatibility.
    # Upload eligibility is additionally gated per item by approved_uploads.txt.
    cfg["rights_confirmed"] = env_bool("I_HAVE_RIGHTS_TO_REPOST", False)

    yt = cfg["youtube"]
    yt["privacy"] = os.getenv("YOUTUBE_PRIVACY", yt.get("privacy", "private")).strip().lower()
    yt["made_for_kids"] = env_bool("MADE_FOR_KIDS", bool(yt.get("made_for_kids", False)))
    yt["contains_synthetic_media"] = env_bool(
        "CONTAINS_SYNTHETIC_MEDIA",
        bool(yt.get("contains_synthetic_media", False)),
    )

    safety = cfg["safety"]
    safety["channel_state"] = os.getenv(
        "CHANNEL_STATE", safety.get("channel_state", "suspended")
    ).strip().lower()
    safety["run_mode"] = os.getenv(
        "BOT_RUN_MODE", safety.get("run_mode", "review")
    ).strip().lower()
    safety["manual_approval_required"] = env_bool(
        "MANUAL_APPROVAL_REQUIRED",
        bool(safety.get("manual_approval_required", True)),
    )

    return cfg
