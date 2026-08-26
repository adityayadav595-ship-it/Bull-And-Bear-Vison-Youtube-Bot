from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube(cfg: dict):
    if not cfg.get("client_id"):
        raise RuntimeError("Missing YOUTUBE_CLIENT_ID")
    if not cfg.get("client_secret"):
        raise RuntimeError("Missing YOUTUBE_CLIENT_SECRET")
    if not cfg.get("refresh_token"):
        raise RuntimeError("Missing YOUTUBE_REFRESH_TOKEN")

    creds = Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )

    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path: str, meta: dict, cfg: dict) -> str:
    privacy = cfg.get("privacy", "public")
    if privacy not in {"public", "private", "unlisted"}:
        privacy = "public"

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["category_id"],
            "defaultLanguage": cfg.get("youtube", {}).get("language", "en"),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": bool(cfg.get("made_for_kids", False)),
            "embeddable": bool(cfg.get("youtube", {}).get("embeddable", True)),
            "publicStatsViewable": bool(
                cfg.get("youtube", {}).get("public_stats_viewable", True)
            ),
            "containsSyntheticMedia": bool(
                cfg.get("contains_synthetic_media", False)
            ),
        },
    }

    media = MediaFileUpload(
        file_path,
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=True,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    return response["id"]
