from __future__ import annotations

from pathlib import Path

import cv2


def video_contains_face(video_path: str, cfg: dict) -> bool:
    """Return True when a clear human face is detected in sampled video frames.

    This is intentionally conservative for Instagram: any detected human face
    causes the reel to be skipped. It does not identify a specific person.
    """
    face_cfg = cfg.get("face_filter", {})
    if not face_cfg.get("enabled", True):
        return False

    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Face-filter video not found: {video_path}")

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("OpenCV face detector could not be loaded.")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("Could not open video for face filtering.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if frame_count > 0 and fps > 0 else 0

    sample_every = float(face_cfg.get("sample_every_seconds", 1.0) or 1.0)
    max_samples = int(face_cfg.get("max_samples", 24) or 24)
    min_face_size = int(face_cfg.get("min_face_size_px", 42) or 42)

    timestamps = []
    if duration > 0:
        t = 0.0
        while t <= duration and len(timestamps) < max_samples:
            timestamps.append(t)
            t += sample_every
    else:
        timestamps = [i * sample_every for i in range(max_samples)]

    try:
        for t in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(min_face_size, min_face_size),
            )
            if len(faces) > 0:
                return True
    finally:
        cap.release()

    return False
