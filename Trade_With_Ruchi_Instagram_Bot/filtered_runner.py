from __future__ import annotations

import re
import tempfile
from pathlib import Path

import cv2
import pytesseract

import app

# Text patterns that strongly suggest another trading page/profile is branded in the video.
PROFILE_PATTERNS = [
    re.compile(r"@[a-z0-9_.]{3,}", re.I),
    re.compile(r"\btrade\s*with\s+[a-z0-9_.]{2,}", re.I),
    re.compile(r"\btrading\s*(?:room|official|signals?|academy|channel|club|king|queen|pro)\b", re.I),
    re.compile(r"\b[a-z0-9_.]{3,}\s*(?:trader|trading)\b", re.I),
]

# Platform/profile UI words strengthen the decision when paired with trading/profile text.
PROFILE_UI_WORDS = ("instagram", "follow", "followers", "following", "profile", "telegram", "youtube")
TRADING_WORDS = ("trade", "trader", "trading", "forex", "quotex", "binary", "signals")


def frame_has_foreign_profile_text(frame) -> tuple[bool, str]:
    # Upscale and increase contrast so small watermarks/handles are easier to read.
    h, w = frame.shape[:2]
    scale = 1.5 if max(h, w) < 1600 else 1.0
    if scale != 1.0:
        frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    text = pytesseract.image_to_string(gray, config="--psm 11", timeout=8)
    clean = " ".join(text.lower().split())
    if not clean:
        return False, ""

    for pattern in PROFILE_PATTERNS:
        match = pattern.search(clean)
        if match:
            return True, match.group(0)[:80]

    has_trade = any(word in clean for word in TRADING_WORDS)
    has_profile_ui = any(word in clean for word in PROFILE_UI_WORDS)
    if has_trade and has_profile_ui:
        return True, clean[:120]
    return False, ""


def branded_trading_profile(video_path: Path) -> bool:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("OCR filter could not inspect video; candidate skipped for safety.")
        return True

    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sample_count = 10
    hits = 0
    checked = 0
    examples: list[str] = []

    for i in range(sample_count):
        if frames > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((frames - 1) * i / max(1, sample_count - 1)))
        ok, frame = cap.read()
        if not ok:
            continue
        checked += 1
        try:
            hit, example = frame_has_foreign_profile_text(frame)
        except Exception as exc:
            print(f"OCR frame {i + 1} warning: {exc}")
            continue
        if hit:
            hits += 1
            if example and example not in examples:
                examples.append(example)

    cap.release()
    ratio = hits / max(1, checked)
    # Persistent branding usually appears on several sampled frames. A single very
    # explicit @handle is also enough to reject because user wants profile names avoided.
    reject = hits >= 2 or (hits >= 1 and any(x.startswith("@") for x in examples))
    print(f"Trading-profile OCR filter: {hits}/{checked} frame(s) matched ({ratio:.0%}) | {'SKIP' if reject else 'ALLOW'}")
    if examples:
        print("OCR matched branding:", " | ".join(examples[:3]))
    return reject


def filtered_prepare_candidate(item: dict) -> str | None:
    with tempfile.TemporaryDirectory(prefix="ruchi-filtered-reel-") as tmp:
        tmpdir = Path(tmp)
        source = tmpdir / "source.mp4"
        normalized = tmpdir / "instagram-ready.mp4"
        app.download_candidate(item, source)

        if app.face_heavy(source):
            print(f"SKIP FACE-HEAVY: {item['url']}")
            return None
        if branded_trading_profile(source):
            print(f"SKIP TRADING PROFILE/WATERMARK: {item['url']}")
            return None

        app.normalize_video(source, normalized)
        return app.host_on_cloudinary(normalized)


# Keep the existing bot logic intact; only replace candidate preparation with
# face + OCR filtering before anything is uploaded to Cloudinary/Buffer.
app.prepare_candidate = filtered_prepare_candidate

if __name__ == "__main__":
    try:
        raise SystemExit(app.main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise
