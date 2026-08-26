\
from __future__ import annotations
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube(cfg: dict):
    token_path = Path(cfg["token_file"])
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        secret = Path(cfg["client_secret"])
        if not secret.exists():
            raise FileNotFoundError(
                f"Missing {secret}. Download an OAuth Desktop App client_secret.json "
                "from Google Cloud and place it beside app.py."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)

def upload_video(youtube, file_path: str, meta: dict, cfg: dict) -> str:
    privacy = cfg.get("privacy","public")
    if privacy not in {"public","private","unlisted"}:
        privacy = "public"

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["category_id"],
            "defaultLanguage": cfg.get("youtube",{}).get("language","en"),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": bool(cfg.get("made_for_kids", False)),
            "embeddable": bool(cfg.get("youtube",{}).get("embeddable", True)),
            "publicStatsViewable": bool(cfg.get("youtube",{}).get("public_stats_viewable", True)),
            "containsSyntheticMedia": bool(cfg.get("contains_synthetic_media", False)),
        },
    }

    media = MediaFileUpload(file_path, chunksize=8*1024*1024, resumable=True)
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
            print(f"Upload progress: {int(status.progress()*100)}%")

    return response["id"]
