from __future__ import annotations

import random
import app

PRIORITY_PROFILE = "sonamrajpoot932"


def priority_instagram_candidates(seen: set[str]) -> list[dict]:
    profiles = [app.username(x) for x in app.read_urls(app.PROFILES_FILE)]
    profiles = [x for x in profiles if x]

    priority = next((x for x in profiles if x.lower() == PRIORITY_PROFILE), None)
    others = [x for x in profiles if x.lower() != PRIORITY_PROFILE]
    random.shuffle(others)

    selected: list[str] = []
    if priority:
        selected.append(priority)
    selected.extend(others[: max(0, app.PROFILES_PER_RUN - len(selected))])

    print("InstagramAPI scanning (priority first):", ", ".join("@" + u for u in selected))
    found: list[dict] = []
    for u in selected:
        try:
            payload = app.ig_get("/profile/reels", {"handle": u})
            data = payload.get("data") or {}
            items = (data.get("items") if isinstance(data, dict) else []) or []
            count = 0
            for item in items:
                if count >= app.REELS_PER_PROFILE:
                    break
                code = str(item.get("shortcode") or "").strip()
                reel_url = str(item.get("url") or "").strip() or (f"https://www.instagram.com/reel/{code}/" if code else "")
                if not reel_url or reel_url in seen:
                    continue
                found.append({
                    "url": reel_url,
                    "caption": str(item.get("caption") or ""),
                    "video_url": str(item.get("video_url") or "").strip(),
                    "taken_at": str(item.get("taken_at") or ""),
                    "origin": f"instagram:@{u}",
                    "priority": u.lower() == PRIORITY_PROFILE,
                })
                count += 1
            print(f"@{u}: {count} unseen candidate(s)")
        except Exception as exc:
            print(f"Instagram source @{u} skipped: {exc}")

    # Priority profile candidates always come first; within each group prefer newer posts.
    found.sort(key=lambda x: (bool(x.get("priority")), x.get("taken_at", "")), reverse=True)
    return found


def priority_mixed_candidates(seen: set[str]) -> list[dict]:
    ig = priority_instagram_candidates(seen)
    priority_ig = [x for x in ig if x.get("priority")]
    other_ig = [x for x in ig if not x.get("priority")]
    rest = app.direct_candidates(seen) + other_ig + app.pinterest_candidates(seen)
    random.shuffle(rest)
    return priority_ig + rest


app.instagram_candidates = priority_instagram_candidates
app.mixed_candidates = priority_mixed_candidates

if __name__ == "__main__":
    try:
        raise SystemExit(app.main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise
