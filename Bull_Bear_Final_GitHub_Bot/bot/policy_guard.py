from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
from pathlib import Path
import re

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _lines(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    return [
        line.strip()
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def approval_tokens(path: str) -> set[str]:
    tokens: set[str] = set()
    for line in _lines(path):
        # Human-readable notes may follow a pipe; the exact URL/key is first.
        token = line.split("|", 1)[0].strip()
        if token:
            tokens.add(token)
    return tokens


def item_is_manually_approved(item: dict, cfg: dict) -> bool:
    safety = cfg.get("safety", {})
    if not bool(safety.get("manual_approval_required", True)):
        return True

    approvals = approval_tokens(safety.get("approvals_file", "approved_uploads.txt"))
    if not approvals:
        return False

    item_url = str(item.get("url") or "").strip()
    item_key = str(item.get("_history_key") or "").strip()
    return item_url in approvals or item_key in approvals


def channel_allows_upload(cfg: dict) -> tuple[bool, str]:
    safety = cfg.get("safety", {})
    state = str(safety.get("channel_state", "suspended")).strip().lower()
    mode = str(safety.get("run_mode", "review")).strip().lower()

    if state != "active":
        return False, f"channel_state={state!r}; upload locked"
    if mode != "upload":
        return False, f"run_mode={mode!r}; review-only"
    if str(cfg.get("youtube", {}).get("privacy", "private")).lower() != "private":
        return False, "automatic uploads must remain private"
    return True, "ok"


def write_review_queue(ranked: list[dict], cfg: dict) -> None:
    safety = cfg.get("safety", {})
    path = Path(safety.get("review_queue_file", "review_queue.jsonl"))
    limit = int(safety.get("review_queue_size", 10) or 10)
    now = datetime.now(timezone.utc).isoformat()

    rows = []
    for item in ranked[:limit]:
        rows.append(
            {
                "generated_at": now,
                "url": item.get("url", ""),
                "source_key": item.get("_history_key", ""),
                "title": item.get("title", ""),
                "duration": item.get("duration"),
                "score": item.get("_smart_score"),
                "reasons": item.get("_smart_reasons") or [],
                "human_action": "Review content + reuse rights, then copy URL or source_key into approved_uploads.txt",
            }
        )

    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"Review queue updated: {path} ({len(rows)} candidates)")


def _history_rows(path: str) -> list[dict]:
    rows: list[dict] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows

    for line in file_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def cooldown_reason(cfg: dict) -> str | None:
    safety = cfg.get("safety", {})
    min_hours = float(safety.get("min_hours_between_uploads", 12) or 0)
    if min_hours <= 0:
        return None

    path = safety.get("metadata_history_file", "metadata_history.jsonl")
    rows = _history_rows(path)
    if not rows:
        return None

    timestamp = rows[-1].get("uploaded_at")
    if not timestamp:
        return None

    try:
        last = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    elapsed_hours = (datetime.now(timezone.utc) - last.astimezone(timezone.utc)).total_seconds() / 3600
    if elapsed_hours < min_hours:
        remaining = min_hours - elapsed_hours
        return f"cooldown active; wait another {remaining:.1f}h"
    return None


def _normalize(value: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def metadata_risk_reason(meta: dict, cfg: dict) -> str | None:
    title = str(meta.get("title") or "")
    description = str(meta.get("description") or "")
    tags = [str(tag) for tag in (meta.get("tags") or [])]
    safety = cfg.get("safety", {})

    if URL_RE.search(title) or URL_RE.search(description):
        return "external URLs are blocked from automated metadata"

    if len(tags) > int(cfg.get("metadata", {}).get("max_tags", 6) or 6):
        return "too many tags"

    hashtags = re.findall(r"#[A-Za-z0-9_]+", f"{title} {description}")
    if len(hashtags) > int(safety.get("max_hashtags", 3) or 3):
        return "too many hashtags"

    history_path = safety.get("metadata_history_file", "metadata_history.jsonl")
    threshold = float(safety.get("metadata_similarity_threshold", 0.82) or 0.82)
    normalized_title = _normalize(title)

    for row in _history_rows(history_path)[-50:]:
        previous = _normalize(str(row.get("title") or ""))
        if not previous or not normalized_title:
            continue
        score = SequenceMatcher(None, previous, normalized_title).ratio()
        if score >= threshold:
            return f"title too similar to previous upload ({score:.2f} >= {threshold:.2f})"

    return None


def append_metadata_history(meta: dict, item: dict, video_id: str, cfg: dict) -> None:
    safety = cfg.get("safety", {})
    path = Path(safety.get("metadata_history_file", "metadata_history.jsonl"))
    row = {
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "video_id": video_id,
        "source_url": item.get("url", ""),
        "source_key": item.get("_history_key", ""),
        "title": meta.get("title", ""),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
