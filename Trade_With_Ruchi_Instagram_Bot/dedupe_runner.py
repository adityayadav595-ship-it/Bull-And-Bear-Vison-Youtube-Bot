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
    # Ignore common top/bottom overlays and small crops before hashing.
    h, w = gray.shape[:2]
    y1, y2 = int(h * 0.12), int(h * 0.88)
    x1, x2 = int(w * 0.06), int(w * 0.94)
    gray = gray[y1:y2, x1:x2]
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bool(bit))
    return value


def video_hashes(path: Path) -> list[int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("Duplicate checker could not inspect the video.")
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    hashes: list[int] = []
    # More samples makes reposts with trims/intros much harder to slip through.
    for i in range(16):
        if frames > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((frames - 1) * i / 15))
        ok, frame = cap.read()
        if ok:
            hashes.append(_dhash(frame))
    cap.release()
    if len(hashes) < 6:
        raise RuntimeError("Duplicate checker could not sample enough frames.")
    return hashes


def video_fingerprint(path: Path) -> str:
    return ",".join(f"{h:016x}" for h in video_hashes(path))


def _parse_fp(value: str) -> list[int]:
    value = value.strip().lower()
    try:
        if "," in value:
            return [int(x, 16) for x in value.split(",") if x]
        # Backward compatibility with old 8-frame concatenated fingerprints.
        if len(value) % 16 == 0:
            return [int(value[i:i + 16], 16) for i in range(0, len(value), 16)]
    except ValueError:
        pass
    return []


def _load_fingerprints() -> list[list[int]]:
    if not FINGERPRINT_FILE.exists():
        return []
    out = []
    for line in FINGERPRINT_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fp = _parse_fp(line)
        if fp:
            out.append(fp)
    return out


def _ham(a: int, b: int) -> float:
    return (a ^ b).bit_count() / 64.0


def _similarity(new: list[int], old: list[int]) -> float:
    if not new or not old:
        return 0.0
    # Sequence-independent matching catches the same clip after trimming,
    # different frame rate, minor crop, compression or added intro/outro.
    matches = 0
    for h in new:
        if min(_ham(h, x) for x in old) <= 0.16:
            matches += 1
    return matches / len(new)


def is_duplicate(fp: str) -> tuple[bool, float]:
    new = _parse_fp(fp)
    best = 0.0
    for old in _load_fingerprints():
        score = _similarity(new, old)
        best = max(best, score)
        if score >= 0.50:
            return True, score
    return False, best


def dedupe_prepare_candidate(item: dict) -> str | None:
    global _pending_fingerprint
    _pending_fingerprint = None
    with tempfile.TemporaryDirectory(prefix="ruchi-dedupe-reel-") as tmp:
        source = Path(tmp) / "source.mp4"
        normalized = Path(tmp) / "instagram-ready.mp4"
        app.download_candidate(item, source)

        fp = video_fingerprint(source)
        duplicate, similarity = is_duplicate(fp)
        if duplicate:
            print(f"SKIP DUPLICATE VIDEO: {item['url']} | visual similarity={similarity:.0%}")
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
