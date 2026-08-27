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
    description = re.sub(r"[ \t]+", " ", description)
    description = re.sub(r"\n{3,}", "\n\n", description).strip()
    if not description:
        description = (
            "Educational trading content only. No financial advice or guaranteed outcomes. "
            "Trading involves risk. #Shorts #TradingEducation"
        )
    return description[:2000]


def _retry_delay(attempt: int) -> float:
    return min(30.0, (2 ** attempt) + random.uniform(0.5, 1.5))


def upload_video(youtube, file_path, meta, cfg):
    yt = cfg["youtube"]
    title = _safe_title(meta.get("title"))
    description = _safe_description(meta.get("description"))
    tags = []
    for item in (meta.get("tags") or []):
        tag = _remove_blocked_promo(str(item))[:100].strip()
        if tag and tag not in tags:
            tags.append(tag)
    tags = tags[:8]

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
            "privacyStatus": yt.get("privacy", "public"),
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
