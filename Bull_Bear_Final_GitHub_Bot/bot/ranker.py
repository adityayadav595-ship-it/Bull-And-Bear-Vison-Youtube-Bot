from __future__ import annotations

import random


def choose_random(candidates: list[dict], pool_size: int = 8) -> dict | None:
    if not candidates:
        return None

    # Lower-view videos first.
    # If Pinterest doesn't provide views, view_count = 0.
    ranked = sorted(
        candidates,
        key=lambda x: int(x.get("view_count") or 0)
    )

    # Random pick among lowest-view candidates
    pool = ranked[:max(1, min(pool_size, len(ranked)))]

    picked = random.choice(pool)

    print("Random low-view video selected")
    print("Views:", picked.get("view_count", 0))
    print("Title:", picked.get("title", ""))
    print("URL:", picked.get("url", ""))

    return picked
