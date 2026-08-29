from __future__ import annotations

import re
from pathlib import Path

import cv2
import pytesseract

TRADING_WORDS = {
    "trade", "trading", "trader", "chart", "candle", "candlestick", "entry", "buy", "sell",
    "rsi", "macd", "ema", "aroon", "bollinger", "support", "resistance", "breakout", "trend",
    "price", "market", "risk", "reward", "profit", "loss", "discipline", "patience", "psychology",
    "pov", "strategy", "signal", "indicator", "forex", "quotex"
}
NOISE_WORDS = {"like", "follow", "subscribe", "share", "comment", "instagram", "pinterest", "telegram"}


def _clean_line(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"[^A-Za-z0-9%$+&:,.!?()'\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -|:,. ")
    return text


def _line_score(line: str, frame_weight: float = 1.0) -> float:
    low = line.lower()
    words = re.findall(r"[a-z0-9]+", low)
    if not words:
        return -99
    score = min(4.0, len(words) * 0.35)
    score += sum(1.8 for w in TRADING_WORDS if w in low)
    score -= sum(2.0 for w in NOISE_WORDS if w in low)
    if "pov" in low: score += 3.0
    if "?" in line: score += 1.5
    if 5 <= len(words) <= 14: score += 2.0
    if len(line) > 120: score -= 2.0
    return score * frame_weight


def _ocr_variants(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    contrast = cv2.convertScaleAbs(gray, alpha=1.45, beta=0)
    adaptive = cv2.adaptiveThreshold(contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 9)
    return (contrast, adaptive)


def extract_visual_context(video_path: str, max_frames: int = 10) -> str:
    """Read actual on-screen text and return the strongest metadata context.

    Multiple frames and OCR variants are scored so persistent hooks/topics beat
    random UI text. This is content understanding for metadata, not an outcome
    or profit predictor.
    """
    path = Path(video_path)
    if not path.exists(): return ""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened(): return ""
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if total <= 0:
        cap.release(); return ""

    ratios = [0.03, 0.08, 0.14, 0.22, 0.32, 0.45, 0.58, 0.70, 0.83, 0.94][:max_frames]
    candidates = {}
    occurrences = {}

    for pos, ratio in enumerate(ratios):
        idx = min(total - 1, max(0, int(total * ratio)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok or frame is None: continue
        h, w = frame.shape[:2]
        if w > 1080:
            scale = 1080.0 / w
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        # Early frames get a mild boost because Shorts hooks usually appear there.
        frame_weight = 1.15 if pos <= 3 else 1.0
        for variant in _ocr_variants(frame):
            for psm in (6, 11):
                try: raw = pytesseract.image_to_string(variant, config=f"--oem 3 --psm {psm}")
                except Exception: continue
                for part in re.split(r"[\n\r]+", raw):
                    line = _clean_line(part)
                    key = re.sub(r"[^a-z0-9]+", "", line.lower())
                    if len(line) < 5 or len(key) < 5: continue
                    score = _line_score(line, frame_weight)
                    if score < 1.0: continue
                    occurrences[key] = occurrences.get(key, 0) + 1
                    old = candidates.get(key)
                    if old is None or score > old[0]: candidates[key] = (score, line)

    cap.release()
    ranked = []
    for key, (score, line) in candidates.items():
        repeat_bonus = min(5.0, max(0, occurrences.get(key, 1) - 1) * 0.8)
        ranked.append((score + repeat_bonus, line))
    ranked.sort(key=lambda x: (-x[0], len(x[1])))

    selected = []
    selected_keys = []
    for score, line in ranked:
        key = re.sub(r"[^a-z0-9]+", "", line.lower())
        # Suppress near-duplicate OCR versions of the same persistent overlay.
        if any(key in k or k in key for k in selected_keys): continue
        selected.append(line); selected_keys.append(key)
        if len(selected) >= 6: break

    context = " | ".join(selected)
    context = re.sub(r"\s+", " ", context).strip()
    duration = (total / fps) if fps > 0 else 0
    if context:
        print("Visual context detected:", context[:500])
        print("Visual intelligence: ranked", len(ranked), "OCR candidates from", len(ratios), "sampled frames")
    else:
        print(f"Visual context: no reliable OCR text found ({duration:.1f}s clip).")
    return context[:900]
