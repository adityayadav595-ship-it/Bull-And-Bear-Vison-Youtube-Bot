from pathlib import Path
import hashlib


def load_history(path):
    p = Path(path)
    if not p.exists():
        return set()
    return {x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()}


def append_history(path, key):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(key + "\n")


def file_sha256(path, chunk_size=1024 * 1024):
    """Return a stable SHA-256 fingerprint for a downloaded video file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
