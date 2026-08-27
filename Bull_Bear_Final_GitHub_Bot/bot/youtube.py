import re
import unicodedata

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES=["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube(cfg):
    for k in ("client_id","client_secret","refresh_token"):
        if not cfg.get(k):
            raise RuntimeError(f"Missing {k}")
    creds=Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )
    return build("youtube","v3",credentials=creds)


def _safe_title(value):
    title = unicodedata.normalize("NFKC", str(value or ""))
    # Strip control/invisible characters and emoji/symbol characters that can occasionally
    # trigger YouTube metadata validation problems in automated uploads.
    title = "".join(ch for ch in title if unicodedata.category(ch)[0] not in {"C", "S"})
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        title = "Trading Setup Explained Fast #shorts"
    return title[:95]


def upload_video(youtube,file_path,meta,cfg):
    yt=cfg["youtube"]
    title=_safe_title(meta.get("title"))
    print("Validated YouTube title:", title)
    body={
        "snippet":{
            "title":title,
            "description":str(meta.get("description") or "Trading education short.")[:4900],
            "tags":[str(t)[:100] for t in (meta.get("tags") or []) if str(t).strip()],
            "categoryId":str(meta.get("category_id") or "22"),
            "defaultLanguage":yt.get("language","en"),
        },
        "status":{
            "privacyStatus":yt.get("privacy","public"),
            "selfDeclaredMadeForKids":bool(yt.get("made_for_kids",False)),
            "containsSyntheticMedia":bool(yt.get("contains_synthetic_media",False)),
        },
    }
    media=MediaFileUpload(file_path,chunksize=8*1024*1024,resumable=True)
    req=youtube.videos().insert(part="snippet,status",body=body,media_body=media)
    response=None
    while response is None:
        status,response=req.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress()*100)}%")
    return response["id"]
