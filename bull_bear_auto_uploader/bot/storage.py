\
from __future__ import annotations
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_items (
    source_key TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    title TEXT,
    discovered_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'seen'
);
CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT UNIQUE NOT NULL,
    source_url TEXT NOT NULL,
    youtube_video_id TEXT,
    title TEXT,
    file_sha256 TEXT,
    uploaded_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT
);
"""

class Storage:
    def __init__(self, path: str):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.db.commit()

    @staticmethod
    def source_key(url: str, extractor_id: str|None=None) -> str:
        raw = f"{extractor_id or ''}|{url}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def sha256_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def already_uploaded(self, key: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM uploads WHERE source_key=? AND status='uploaded' LIMIT 1",
            (key,)
        ).fetchone()
        return bool(row)

    def mark_upload(self, *, key: str, source_url: str, youtube_video_id: str|None,
                    title: str, file_sha256: str|None, status: str, error: str|None=None):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """INSERT INTO uploads(source_key,source_url,youtube_video_id,title,file_sha256,uploaded_at,status,error)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(source_key) DO UPDATE SET
                 youtube_video_id=excluded.youtube_video_id,
                 title=excluded.title,
                 file_sha256=excluded.file_sha256,
                 uploaded_at=excluded.uploaded_at,
                 status=excluded.status,
                 error=excluded.error""",
            (key, source_url, youtube_video_id, title, file_sha256, now, status, error)
        )
        self.db.commit()
