from __future__ import annotations
import random


def choose_random_unseen(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None

    # Pure random pick from unseen eligible videos
    return random.choice(candidates)
