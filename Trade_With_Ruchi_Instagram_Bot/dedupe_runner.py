from __future__ import annotations

import tempfile
from pathlib import Path

import cv2

import app
import filtered_runner as fr

FINGERPRINT_FILE = Path(__file__).resolve().parent / "uploaded_fingerprints.txt"
_pending_fingerprint: str | None = None
_original_append_history = app.append_history


def _dhash(frame) -> int:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bool(bit))
    return value


def video_fingerprint(path: Path) -> str:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("Duplicate checker could not inspect the video.")
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    hashes: list[int] = []
    for i in range(8):
        if frames > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((frames - 1) * i / 7))
        ok, frame = cap.read()
        if ok:
            hashes.append(_dhash(frame))
    cap.release()
    if len(hashes) < 4:
        raise RuntimeError("Duplicate checker could not sample enough frames.")
    return "".join(f"{h:016x}" for h in hashes)


def _load_fingerprints() -> list[str]:
    if not FINGERPRINT_FILE.exists():
        return []
    return [
        line.strip().lower()
        for line in FINGERPRINT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _distance_ratio(a: str, b: str) -> float:
    if len(a) != len(b):
        return 1.0
    try:
        x = int(a, 16) ^ int(b, 16)
    except ValueError:
        return 1.0
    return x.bit_count() / max(1, len(a) * 4)


def is_duplicate(fp: str) -> tuple[bool, float]:
    best = 1.0
    for old in _load_fingerprints():
        d = _distance_ratio(fp, old)
        best = min(best, d)
        if d <= 0.12:
            return True, d
    return False, best


def dedupe_prepare_candidate(item: dict) -> str | None:
    global _pending_fingerprint
    _pending_fingerprint = None
    with tempfile.TemporaryDirectory(prefix="ruchi-dedupe-reel-") as tmp:
        source = Path(tmp) / "source.mp4"
        normalized = Path(tmp) / "instagram-ready.mp4"
        app.download_candidate(item, source)

        fp = video_fingerprint(source)
        duplicate, distance = is_duplicate(fp)
        if duplicate:
            print(f"SKIP DUPLICATE VIDEO: {item['url']} | perceptual distance={distance:.3f}")
            return None

        if app.face_heavy(source):
            print(f"SKIP FACE-HEAVY: {item['url']}")
            return None
        if fr.branded_trading_profile(source):
            print(f"SKIP TRADING PROFILE/WATERMARK: {item['url']}")
            return None

        app.normalize_video(source, normalized)
        stable_url = app.host_on_cloudinary(normalized)
        _pending_fingerprint = fp
        return stable_url


def append_history_and_fingerprint(url: str) -> None:
    global _pending_fingerprint
    _original_append_history(url)
    if _pending_fingerprint:
        with FINGERPRINT_FILE.open("a", encoding="utf-8") as f:
            f.write(_pending_fingerprint + "\n")
        print("Video fingerprint saved for cross-source duplicate prevention.")
        _pending_fingerprint = None


app.prepare_candidate = dedupe_prepare_candidate
app.append_history = append_history_and_fingerprint

if __name__ == "__main__":
    try:
        raise SystemExit(app.main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise
