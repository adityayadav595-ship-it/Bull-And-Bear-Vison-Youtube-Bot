import random
import re
import time
import unicodedata

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

BLOCKED_PROMO_PATTERNS = [
    r"\b100\s*%\b",
    r"\bguaranteed?\b",
    r"\bsure\s*shot\b",
    r"\bno\s*risk\b",
    r"\beasy\s*money\b",
    r"\binstant\s*profit\b",
    r"\bguaranteed\s*profit\b",
    r"\bget\s*rich\b",
    r"\bdouble\s+your\s+money\b",
    r"\brisk[-\s]*free\b",
    r"\bwin\s*rate\b",
    r"\bprofit\s+guarantee\b",
    r"\bguaranteed\s+returns?\b",
    r"\bwithdrawal\s*proof\b",
    r"\bprofit\s*proof\b",
    r"\bvip\s*signals?\b",
    r"\bpromo\s*code\b",
    r"\bdeposit\s*bonus\b",
]

RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
MAX_UPLOAD_RETRIES = 5


def get_youtube(cfg):
    for key in ("client_id", "client_secret", "refresh_token"):
        if not cfg.get(key):
            raise RuntimeError(f"Missing {key}")
    creds = Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def _remove_blocked_promo(value: str) -> str:
    text = str(value or "")
    for pattern in BLOCKED_PROMO_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"[ \t]+", " ", text).strip()


def _safe_title(value):
    title = unicodedata.normalize("NFKC", _remove_blocked_promo(value))
    title = "".join(ch for ch in title if unicodedata.category(ch)[0] not in {"C", "S"})
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        title = "Trading Education Lesson #Shorts"
    return title[:95]


def _safe_description(value):
    description = unicodedata.normalize("NFKC", _remove_blocked_promo(value))
    description = "".join(ch for ch in description if unicodedata.category(ch)[0] != "C" or ch in "\n\t")
    description = re.sub(r"https?://\S+", " ", description)
    description = re.sub(r"[ \t]+", " ", description)
    description = re.sub(r"\n{3,}", "\n\n", description).strip()

    disclosure = (
        "Educational content only. Not financial advice. Trading involves risk; "
        "results are not guaranteed."
    )
    if disclosure.lower() not in description.lower():
        description = (description + "\n\n" + disclosure).strip()

    if not description:
        description = disclosure + " #Shorts #TradingEducation"
    return description[:2000]


def _retry_delay(attempt: int) -> float:
    return min(30.0, (2 ** attempt) + random.uniform(0.5, 1.5))


def upload_video(youtube, file_path, meta, cfg):
    yt = cfg["youtube"]
    privacy = str(yt.get("privacy", "private")).lower().strip()
    if privacy != "private":
        raise RuntimeError("Safety lock: initial automated uploads must be PRIVATE.")

    title = _safe_title(meta.get("title"))
    description = _safe_description(meta.get("description"))
    tags = []
    max_tags = int(cfg.get("metadata", {}).get("max_tags", 6) or 6)
    for item in (meta.get("tags") or []):
        tag = _remove_blocked_promo(str(item))[:100].strip()
        if tag and tag not in tags:
            tags.append(tag)
    tags = tags[:max_tags]

    print("Validated YouTube title:", title)
    print("Validated YouTube tags:", tags)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": str(meta.get("category_id") or "27"),
            "defaultLanguage": yt.get("language", "en"),
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": bool(yt.get("made_for_kids", False)),
            "containsSyntheticMedia": bool(yt.get("contains_synthetic_media", False)),
        },
    }

    media = MediaFileUpload(file_path, chunksize=8 * 1024 * 1024, resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retries = 0
    while response is None:
        try:
            status, response = req.next_chunk()
            retries = 0
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")
        except HttpError as exc:
            http_status = getattr(exc.resp, "status", None)
            if http_status not in RETRYABLE_HTTP_STATUS or retries >= MAX_UPLOAD_RETRIES:
                raise
            retries += 1
            delay = _retry_delay(retries)
            print(f"Temporary YouTube API error {http_status}; retrying in {delay:.1f}s...")
            time.sleep(delay)

    return response["id"]


def publish_private_video_after_delay(youtube, video_id, cfg):
    """Keep the upload private for a configured delay, then publish only if YouTube reports it ready."""
    yt = cfg.get("youtube", {})
    if not bool(yt.get("auto_publish_enabled", False)):
        print("Auto-publish disabled; video remains PRIVATE.")
        return False

    delay_minutes = max(0, int(yt.get("auto_publish_after_minutes", 10) or 10))
    print(f"Keeping video PRIVATE for {delay_minutes} minute(s) before publish check...")
    time.sleep(delay_minutes * 60)

    response = youtube.videos().list(
        part="status,processingDetails",
        id=video_id,
    ).execute()
    items = response.get("items") or []
    if not items:
        print("AUTO-PUBLISH BLOCKED: uploaded video could not be re-read from YouTube.")
        return False

    item = items[0]
    status = item.get("status") or {}
    processing = item.get("processingDetails") or {}
    upload_status = str(status.get("uploadStatus") or "").lower()
    processing_status = str(processing.get("processingStatus") or "").lower()
    failure_reason = str(processing.get("processingFailureReason") or "").strip()
    rejection_reason = str(status.get("rejectionReason") or "").strip()

    print(
        "Pre-publish YouTube check:",
        f"uploadStatus={upload_status or 'unknown'},",
        f"processingStatus={processing_status or 'unknown'}",
    )

    if failure_reason or rejection_reason:
        print(
            "AUTO-PUBLISH BLOCKED:",
            failure_reason or rejection_reason,
            "Video remains PRIVATE.",
        )
        return False

    if upload_status not in {"uploaded", "processed"}:
        print(f"AUTO-PUBLISH BLOCKED: uploadStatus={upload_status or 'unknown'}. Video remains PRIVATE.")
        return False

    if processing_status != "succeeded":
        print(f"AUTO-PUBLISH BLOCKED: processingStatus={processing_status or 'unknown'}. Video remains PRIVATE.")
        return False

    update_body = {
        "id": video_id,
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": bool(yt.get("made_for_kids", False)),
            "containsSyntheticMedia": bool(yt.get("contains_synthetic_media", False)),
        },
    }
    youtube.videos().update(part="status", body=update_body).execute()
    print("AUTO-PUBLISH SUCCESS: video is now PUBLIC.")
    return True
