from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
SCOPES=["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube(cfg):
    for k in ("client_id","client_secret","refresh_token"):
        if not cfg.get(k): raise RuntimeError(f"Missing {k}")
    creds=Credentials(token=None,refresh_token=cfg["refresh_token"],token_uri="https://oauth2.googleapis.com/token",client_id=cfg["client_id"],client_secret=cfg["client_secret"],scopes=SCOPES)
    return build("youtube","v3",credentials=creds)

def upload_video(youtube,file_path,meta,cfg):
    yt=cfg["youtube"]; body={"snippet":{"title":meta["title"],"description":meta["description"],"tags":meta["tags"],"categoryId":meta["category_id"],"defaultLanguage":yt.get("language","en")},"status":{"privacyStatus":yt.get("privacy","public"),"selfDeclaredMadeForKids":bool(yt.get("made_for_kids",False)),"containsSyntheticMedia":bool(yt.get("contains_synthetic_media",False))}}
    media=MediaFileUpload(file_path,chunksize=8*1024*1024,resumable=True)
    req=youtube.videos().insert(part="snippet,status",body=body,media_body=media); response=None
    while response is None:
        status,response=req.next_chunk()
        if status: print(f"Upload progress: {int(status.progress()*100)}%")
    return response["id"]
