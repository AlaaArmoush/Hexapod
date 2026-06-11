#!/usr/bin/env python3
"""
Live tracking preview.
Saves annotated frames to /tmp/hexapod_preview.jpg every ~5 frames.
Prints detection info to stdout. Press Ctrl-C to quit.

  python3 scripts/tracking_preview.py           # try OAK-D, fall back to webcam
  python3 scripts/tracking_preview.py --webcam  # force webcam index 0
  python3 scripts/tracking_preview.py --show    # open GUI window (needs display)
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


def _draw_detections(frame: np.ndarray, result) -> None:
    """Draw bounding boxes + labels using only OpenCV (no ultralytics needed)."""
    h, w = frame.shape[:2]
    for det in result.detections:
        # Convert normalised -1..+1 centre back to pixel bbox using bbox_area
        cx = int((det.frame_position_x + 1) / 2 * w)
        cy = int((det.frame_position_y + 1) / 2 * h)
        side = int((det.bbox_area ** 0.5) * min(w, h))
        x1, y1 = max(0, cx - side // 2), max(0, cy - side // 2)
        x2, y2 = min(w, cx + side // 2), min(h, cy + side // 2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
        cv2.putText(frame, f"{det.label} {det.confidence:.2f}",
                    (x1, max(y1 - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)


def _try_oak_d():
    try:
        from camera.provider import DepthAICameraProvider
        p = DepthAICameraProvider()
        p.start()
        time.sleep(0.6)
        if p.grab_frame() is not None:
            print("Camera: OAK-D")
            return p
        p.stop()
        print("OAK-D started but grab_frame() returned None")
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
    parser.add_argument("--show", action="store_true", help="Open GUI window (requires display)")
    args = parser.parse_args()

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

    from camera.host_detector import HostDetector
    detector = HostDetector()
    mode = "GUI window" if args.show else "saving to /tmp/hexapod_preview.jpg"
    print(f"Detector: {detector._source}. Output: {mode}. Ctrl-C to quit.")

    ema_x, ema_y = 0.0, 0.0
    has_target = False
    frame_count = 0

    try:
        while True:
            if provider is not None:
                frame = _grab_oak(provider)
                if frame is None:
                    time.sleep(0.02)
                    continue
            else:
                ret, frame = cap.read()
                if not ret:
                    break

            result = detector.detect(frame)
            annotated = frame.copy()
            _draw_detections(annotated, result)

            persons = [d for d in result.detections if d.label == "person"]

            if persons:
                best = max(persons, key=lambda d: d.bbox_area)
                if not has_target:
                    ema_x, ema_y = best.frame_position_x, best.frame_position_y
                    has_target = True
                else:
                    ema_x = EMA_ALPHA * best.frame_position_x + (1 - EMA_ALPHA) * ema_x
                    ema_y = EMA_ALPHA * best.frame_position_y + (1 - EMA_ALPHA) * ema_y

                _draw_crosshair(annotated, ema_x, ema_y)
                label = f"EMA ({ema_x:+.2f}, {ema_y:+.2f})  area={best.bbox_area:.3f}  conf={best.confidence:.2f}"
                cv2.putText(annotated, label, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                print(f"\r[person] {label}", end="", flush=True)
            else:
                has_target = False
                cv2.putText(annotated, "No person", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
                print("\r[no person]         ", end="", flush=True)

            frame_count += 1
            if args.show:
                cv2.imshow("Hexapod Tracker Preview", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            elif frame_count % 5 == 0:
                cv2.imwrite("/tmp/hexapod_preview.jpg", annotated)

    finally:
        print()
        if args.show:
            cv2.destroyAllWindows()
        if provider is not None:
            provider.stop()
        if cap is not None:
            cap.release()


if __name__ == "__main__":
    main()
