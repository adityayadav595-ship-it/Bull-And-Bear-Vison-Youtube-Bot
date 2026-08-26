from __future__ import annotations

import random


def choose_random(candidates: list[dict], pool_size: int = 8) -> dict | None:
    if not candidates:
        return None

    # Personal/approved sources: view count does NOT affect eligibility.
    # Pick randomly from all unseen usable candidates so higher-view
    # and unknown-view videos can be uploaded too.
    picked = random.choice(candidates)

    print("Random unseen video selected")
    print("Views:", picked.get("view_count", "unknown"))
    print("Title:", picked.get("title", ""))
    print("URL:", picked.get("url", ""))

    return picked
