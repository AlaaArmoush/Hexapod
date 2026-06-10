#!/usr/bin/env python3
"""
Live tracking preview.
Shows YOLO detections + EMA-smoothed crosshair for the closest person.

  python3 scripts/tracking_preview.py           # try OAK-D, fall back to webcam
  python3 scripts/tracking_preview.py --webcam  # force webcam index 0

Press 'q' to quit.
"""

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cv2
import numpy as np

EMA_ALPHA = 0.4


def _draw_crosshair(frame: np.ndarray, x_norm: float, y_norm: float) -> None:
    h, w = frame.shape[:2]
    cx = int((x_norm + 1) / 2 * w)
    cy = int((y_norm + 1) / 2 * h)
    cv2.line(frame, (cx - 24, cy), (cx + 24, cy), (0, 255, 0), 2)
    cv2.line(frame, (cx, cy - 24), (cx, cy + 24), (0, 255, 0), 2)
    cv2.circle(frame, (cx, cy), 10, (0, 255, 0), 2)


def _try_oak_d():
    """Return a started DepthAICameraProvider, or None if unavailable."""
    try:
        from camera.provider import DepthAICameraProvider
        p = DepthAICameraProvider()
        p.start()
        time.sleep(0.6)              # let first frames arrive
        if p.grab_frame() is not None:
            print("Camera: OAK-D")
            return p
        p.stop()
        print("OAK-D started but grab_frame() returned None — no frames arriving")
    except Exception:
        import traceback
        traceback.print_exc()
        print("OAK-D unavailable (see traceback above)")
    return None


def _grab_oak(provider) -> np.ndarray | None:
    for _ in range(10):
        frame = provider.grab_frame()
        if frame is not None:
            return frame
        time.sleep(0.02)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webcam", action="store_true", help="Force webcam instead of OAK-D")
    args = parser.parse_args()

    # ── Open camera ──────────────────────────────────────────────────────────
    provider = None
    cap = None

    if not args.webcam:
        provider = _try_oak_d()

    if provider is None:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("No camera found. Connect OAK-D or a webcam and retry.")
            sys.exit(1)
        print("Camera: webcam index 0")

    # ── Load YOLO (one instance, used for both annotation and EMA) ────────────
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics not installed — run: pip install ultralytics")
        sys.exit(1)

    model = YOLO("yolov8n.pt")
    print("YOLOv8n loaded. Press 'q' to quit.")

    ema_x, ema_y = 0.0, 0.0
    has_target = False

    try:
        while True:
            # ── Grab frame ───────────────────────────────────────────────────
            if provider is not None:
                frame = _grab_oak(provider)
                if frame is None:
                    time.sleep(0.02)
                    continue
            else:
                ret, frame = cap.read()
                if not ret:
                    break

            # ── Detect ───────────────────────────────────────────────────────
            results = model(frame, verbose=False)[0]
            annotated = results.plot()        # YOLO draws its own boxes + labels

            # Extract person detections from the same results (no double inference)
            names = results.names
            persons = [
                (box.xyxy[0].tolist(), float(box.conf[0]))
                for box, cls_id in zip(results.boxes, results.boxes.cls.int().tolist())
                if names[cls_id] == "person" and float(box.conf[0]) >= 0.45
            ]

            # ── Update EMA (largest bbox = closest without depth) ─────────────
            if persons:
                # pick largest box by area
                def _area(xyxy):
                    x1, y1, x2, y2 = xyxy
                    return (x2 - x1) * (y2 - y1)

                best_xyxy, best_conf = max(persons, key=lambda p: _area(p[0]))
                x1, y1, x2, y2 = best_xyxy
                h, w = frame.shape[:2]
                cx_norm = ((x1 + x2) / 2 / w - 0.5) * 2
                cy_norm = ((y1 + y2) / 2 / h - 0.5) * 2
                area_norm = (x2 - x1) * (y2 - y1) / (w * h)

                if not has_target:
                    ema_x, ema_y = cx_norm, cy_norm
                    has_target = True
                else:
                    ema_x = EMA_ALPHA * cx_norm + (1 - EMA_ALPHA) * ema_x
                    ema_y = EMA_ALPHA * cy_norm + (1 - EMA_ALPHA) * ema_y

                _draw_crosshair(annotated, ema_x, ema_y)
                cv2.putText(
                    annotated,
                    f"EMA ({ema_x:+.2f}, {ema_y:+.2f})  area={area_norm:.2f}  conf={best_conf:.2f}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2,
                )
            else:
                has_target = False
                cv2.putText(
                    annotated, "No person",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2,
                )

            cv2.imshow("Hexapod Tracker Preview", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cv2.destroyAllWindows()
        if provider is not None:
            provider.stop()
        if cap is not None:
            cap.release()


if __name__ == "__main__":
    main()
