from __future__ import annotations

import re
from pathlib import Path

import cv2
import pytesseract


def _clean_line(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"[^A-Za-z0-9%$+&:,.!?()'\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -|:,. ")


def extract_visual_context(video_path: str, max_frames: int = 8) -> str:
    """Sample frames and OCR visible text so metadata reflects the actual clip.

    This intentionally reads only on-screen text; it does not infer guaranteed
    outcomes or financial claims from imagery.
    """
    path = Path(video_path)
    if not path.exists():
        return ""

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return ""

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if total <= 0:
        cap.release()
        return ""

    # Bias toward early/middle frames where Shorts usually place the hook text.
    ratios = [0.05, 0.12, 0.22, 0.35, 0.50, 0.66, 0.82, 0.94][:max_frames]
    seen = set()
    lines = []

    for ratio in ratios:
        idx = min(total - 1, max(0, int(total * ratio)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue

        h, w = frame.shape[:2]
        if w > 1080:
            scale = 1080.0 / w
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.convertScaleAbs(gray, alpha=1.35, beta=0)

        try:
            raw = pytesseract.image_to_string(gray, config="--oem 3 --psm 6")
        except Exception:
            continue

        for part in re.split(r"[\n\r]+", raw):
            line = _clean_line(part)
            key = re.sub(r"[^a-z0-9]+", "", line.lower())
            if len(line) < 4 or len(key) < 4 or key in seen:
                continue
            seen.add(key)
            lines.append(line)
            if len(lines) >= 14:
                break
        if len(lines) >= 14:
            break

    cap.release()

    # Keep metadata input compact and useful.
    context = " | ".join(lines)
    context = re.sub(r"\s+", " ", context).strip()
    if context:
        print("Visual context detected:", context[:500])
    else:
        duration = (total / fps) if fps > 0 else 0
        print(f"Visual context: no reliable OCR text found ({duration:.1f}s clip).")
    return context[:900]
