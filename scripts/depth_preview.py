#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from camera.config import DEPTH_FPS, DEPTH_HEIGHT, DEPTH_WIDTH
from camera.depth import center_roi, summarize_center_depth
from camera.errors import CameraDepthError
from camera.provider import DepthAICameraProvider


_latest_jpeg: bytes | None = None
_latest_jpeg_lock = threading.Lock()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a live OAK-D depth preview with center ROI.")
    parser.add_argument("--fps", type=int, default=DEPTH_FPS, help="Depth preview FPS.")
    parser.add_argument("--width", type=int, default=DEPTH_WIDTH, help="Requested mono/depth width.")
    parser.add_argument("--height", type=int, default=DEPTH_HEIGHT, help="Requested mono/depth height.")
    parser.add_argument("--window", default="Hexapod OAK-D depth preview", help="Preview window title.")
    parser.add_argument(
        "--preview",
        choices=("auto", "window", "browser"),
        default="auto",
        help="Preview mode. auto tries an OpenCV window, then falls back to browser MJPEG.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Browser preview host.")
    parser.add_argument("--port", type=int, default=8088, help="Browser preview port.")
    return parser.parse_args()


class _PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"""<!doctype html>
<html>
<head><title>Hexapod depth preview</title></head>
<body style="margin:0;background:#111;color:#eee;font-family:sans-serif">
<div style="padding:8px 10px">Hexapod OAK-D depth preview. Stop with Ctrl+C in the terminal.</div>
<img src="/stream.mjpg" style="display:block;width:100%;max-width:960px;height:auto" />
</body>
</html>"""
            )
            return

        if self.path != "/stream.mjpg":
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        while True:
            with _latest_jpeg_lock:
                frame = _latest_jpeg
            if frame is None:
                time.sleep(0.05)
                continue
            try:
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                time.sleep(0.03)
            except (BrokenPipeError, ConnectionResetError):
                return

    def log_message(self, format: str, *args) -> None:
        return


def _start_browser_preview(host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), _PreviewHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Browser preview: http://{host}:{port}")
    print("Stop the preview with Ctrl+C in this terminal.")
    return server


def _publish_browser_frame(image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        return
    with _latest_jpeg_lock:
        global _latest_jpeg
        _latest_jpeg = encoded.tobytes()


def _colorize_depth(depth_mm: np.ndarray) -> np.ndarray:
    valid = depth_mm[(depth_mm > 0) & np.isfinite(depth_mm)]
    if valid.size == 0:
        scaled = np.zeros(depth_mm.shape, dtype=np.uint8)
    else:
        near = max(200, int(np.percentile(valid, 5)))
        far = min(3000, int(np.percentile(valid, 95)))
        if far <= near:
            far = near + 1
        clipped = np.clip(depth_mm, near, far)
        scaled = cv2.convertScaleAbs(clipped, alpha=255.0 / (far - near), beta=-near * 255.0 / (far - near))
        scaled[depth_mm == 0] = 0
    return cv2.applyColorMap(255 - scaled, cv2.COLORMAP_JET)


def _draw_overlay(image: np.ndarray, depth_mm: np.ndarray, frame_age_ms: int) -> np.ndarray:
    roi = center_roi(depth_mm.shape[1], depth_mm.shape[0])
    cv2.rectangle(image, (roi.x_min, roi.y_min), (roi.x_max, roi.y_max), (255, 255, 255), 1)

    try:
        summary = summarize_center_depth(depth_mm, frame_age_ms=frame_age_ms)
        lines = [
            f"center: {summary.distance_m:.3f} m",
            f"nearest: {summary.nearest_distance_m:.3f} m",
            f"valid: {summary.valid_ratio:.3f} ({summary.valid_samples})",
        ]
        color = (255, 255, 255)
    except CameraDepthError as exc:
        lines = [
            "center: unavailable",
            f"valid: {exc.data.get('valid_ratio', 0.0):.3f} ({exc.data.get('valid_samples', 0)})",
            "move a textured matte target into the box",
        ]
        color = (255, 255, 255)

    y = 22
    for line in lines:
        cv2.putText(image, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        y += 20
    return image


def main() -> int:
    args = _parse_args()
    dai = DepthAICameraProvider._import_depthai()
    browser_server: ThreadingHTTPServer | None = None

    device = dai.Device()
    with dai.Pipeline(device) as pipeline:
        left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
        right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
        left_out = left.requestOutput((args.width, args.height), dai.ImgFrame.Type.NV12, fps=args.fps)
        right_out = right.requestOutput((args.width, args.height), dai.ImgFrame.Type.NV12, fps=args.fps)

        stereo = pipeline.create(dai.node.StereoDepth).build(
            left=left_out,
            right=right_out,
            presetMode=dai.node.StereoDepth.PresetMode.DEFAULT,
        )
        stereo.initialConfig.setMedianFilter(dai.MedianFilter.MEDIAN_OFF)
        stereo.setRectification(True)
        stereo.setExtendedDisparity(True)
        stereo.setLeftRightCheck(True)

        queue = stereo.depth.createOutputQueue(maxSize=1, blocking=False)
        pipeline.start()

        preview_mode = args.preview
        if preview_mode == "auto":
            try:
                cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
                preview_mode = "window"
            except cv2.error:
                preview_mode = "browser"
                browser_server = _start_browser_preview(args.host, args.port)
        elif preview_mode == "window":
            cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
        else:
            browser_server = _start_browser_preview(args.host, args.port)

        last_print_s = 0.0
        try:
            while pipeline.isRunning():
                message = queue.get()
                depth_mm = message.getFrame()
                preview = _colorize_depth(depth_mm)
                preview = _draw_overlay(preview, depth_mm, frame_age_ms=0)

                if preview_mode == "window":
                    cv2.imshow(args.window, preview)
                else:
                    _publish_browser_frame(preview)

                now_s = time.monotonic()
                if now_s - last_print_s >= 1.0:
                    last_print_s = now_s
                    try:
                        summary = summarize_center_depth(depth_mm, frame_age_ms=0)
                        print(
                            f"distance_m={summary.distance_m:.3f} "
                            f"nearest_m={summary.nearest_distance_m:.3f} "
                            f"valid_ratio={summary.valid_ratio:.3f} "
                            f"size={summary.depth_width}x{summary.depth_height}"
                        )
                    except CameraDepthError as exc:
                        print(f"depth_unavailable data={exc.data}")

                if preview_mode == "window":
                    key = cv2.waitKey(1) & 0xFF
                    if key in {ord("q"), 27}:
                        break
                else:
                    time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            if browser_server is not None:
                browser_server.shutdown()
                browser_server.server_close()
            if preview_mode == "window":
                cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
