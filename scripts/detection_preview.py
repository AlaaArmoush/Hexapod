#!/usr/bin/env python3
from __future__ import annotations

import argparse
import select
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2

from camera.config import (
    DETECTION_DEVICE_RETRIES,
    DETECTION_FPS,
    DETECTION_MODEL_YAML,
    DETECTION_RETRY_DELAY_S,
)
from camera.detection import detection_from_yolo_box, filter_detections, normalize_object_name
from camera.provider import DepthAICameraProvider
from camera.yolo_decode import decode_yolov6_outputs


_latest_jpeg: bytes | None = None
_latest_jpeg_lock = threading.Lock()


class _PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"""<!doctype html>
<html>
<head><title>Hexapod detection preview</title></head>
<body style="margin:0;background:#111;color:#eee;font-family:sans-serif">
<div style="padding:8px 10px">Hexapod OAK-D detection preview. Stop with Ctrl+C in the terminal.</div>
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a persistent OAK-D detection preview.")
    parser.add_argument("--fps", type=int, default=DETECTION_FPS, help="Detector FPS.")
    parser.add_argument("--threshold", type=float, default=0.45, help="Minimum confidence.")
    parser.add_argument("--target", default="", help="Optional COCO class to show, e.g. person or bottle.")
    parser.add_argument("--host", default="127.0.0.1", help="Browser preview host.")
    parser.add_argument("--port", type=int, default=8089, help="Browser preview port.")
    return parser.parse_args()


def _start_browser_preview(host: str, port: int) -> ThreadingHTTPServer:
    last_error = None
    for candidate_port in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((host, candidate_port), _PreviewHandler)
            break
        except OSError as exc:
            last_error = exc
    else:
        raise OSError(f"Could not bind preview server near port {port}: {last_error}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    actual_host, actual_port = server.server_address
    print(f"Browser preview: http://{actual_host}:{actual_port}")
    print("Press Enter in this terminal to stop cleanly. Use Ctrl+C only as an emergency abort.")
    return server


def _publish_frame(frame) -> None:
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return
    with _latest_jpeg_lock:
        global _latest_jpeg
        _latest_jpeg = encoded.tobytes()


def _open_device_with_retries(dai):
    last_exc = None
    for attempt in range(DETECTION_DEVICE_RETRIES):
        try:
            return dai.Device()
        except Exception as exc:
            last_exc = exc
            remaining = DETECTION_DEVICE_RETRIES - attempt - 1
            if remaining:
                print(
                    f"Could not open OAK-D yet ({exc}). "
                    f"Retrying in {DETECTION_RETRY_DELAY_S:.1f}s..."
                )
                time.sleep(DETECTION_RETRY_DELAY_S)
    raise last_exc


def _draw_detections(frame, detections, frame_width: int, frame_height: int):
    for detection in detections:
        x = int((detection.frame_position_x + 1.0) * 0.5 * frame_width)
        y = int((detection.frame_position_y + 1.0) * 0.5 * frame_height)
        text = f"{detection.label} {detection.confidence:.2f}"
        if detection.distance_m is not None:
            text += f" {detection.distance_m:.2f}m"
        cv2.circle(frame, (x, y), 6, (255, 255, 255), -1)
        cv2.putText(frame, text, (max(5, x - 60), max(20, y - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, text, (max(5, x - 60), max(20, y - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def main() -> int:
    args = _parse_args()
    target = normalize_object_name(args.target) if args.target.strip() else None
    dai = DepthAICameraProvider._import_depthai()
    server = None

    device = _open_device_with_retries(dai)
    platform = device.getPlatform().name
    if platform != "RVC2":
        print(f"Unsupported platform for this detector: {platform}")
        return 2
    frame_type = dai.ImgFrame.Type.BGR888p

    try:
        with dai.Pipeline(device) as pipeline:
            model_description = dai.NNModelDescription.fromYamlFile(str(DETECTION_MODEL_YAML))
            nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
            classes = nn_archive.getConfig().model.heads[0].metadata.classes
            nn_size = nn_archive.getInputSize()

            color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
            preview = color.requestOutput(nn_size, type=frame_type, fps=args.fps)
            manip = pipeline.create(dai.node.ImageManip)
            manip.initialConfig.setOutputSize(*nn_size)
            manip.initialConfig.setFrameType(frame_type)
            manip.setMaxOutputFrameSize(nn_size[0] * nn_size[1] * 3)
            preview.link(manip.inputImage)
            network = pipeline.create(dai.node.NeuralNetwork).build(manip.out, nn_archive)

            preview_queue = preview.createOutputQueue(maxSize=1, blocking=False)
            detection_queue = network.out.createOutputQueue(maxSize=1, blocking=False)

            try:
                pipeline.start()
            except RuntimeError as exc:
                print("Detector pipeline failed to start.")
                print(f"DepthAI error: {exc}")
                print("")
                print("This usually means the OAK-D neural pipeline crashed during model asset transfer")
                print("or the device is still recovering from a previous neural run.")
                print("Wait 10 seconds and retry. If it repeats, power-cycle the OAK-D and test again.")
                return 2

            server = _start_browser_preview(args.host, args.port)
            last_detections = []
            last_print_s = 0.0
            while pipeline.isRunning():
                readable, _, _ = select.select([sys.stdin], [], [], 0)
                if readable:
                    sys.stdin.readline()
                    break
                try:
                    preview_msg = preview_queue.get()
                except KeyboardInterrupt:
                    break
                frame = preview_msg.getCvFrame()
                nn_msg = detection_queue.tryGet()
                if nn_msg is not None:
                    tensors = [
                        nn_msg.getTensor(
                            tensor_name,
                            dequantize=True,
                            storageOrder=dai.TensorInfo.StorageOrder.NCHW,
                        )
                        for tensor_name in ["output1_yolov6r2", "output2_yolov6r2", "output3_yolov6r2"]
                    ]
                    decoded = decode_yolov6_outputs(
                        tensors,
                        confidence_threshold=args.threshold,
                        iou_threshold=0.45,
                        num_classes=len(classes),
                    )
                    detections = []
                    for box in decoded:
                        label_index = int(box[5])
                        if 0 <= label_index < len(classes):
                            detections.append(detection_from_yolo_box(box, str(classes[label_index]), nn_size))
                    last_detections = filter_detections(
                        detections,
                        target_label=target,
                        confidence_threshold=args.threshold,
                        max_results=10,
                    )

                frame = _draw_detections(frame, last_detections, frame.shape[1], frame.shape[0])
                _publish_frame(frame)

                now_s = time.monotonic()
                if now_s - last_print_s >= 1.0:
                    last_print_s = now_s
                    summary = ", ".join(
                        f"{item.label}:{item.confidence:.2f}"
                        + (f":{item.distance_m:.2f}m" if item.distance_m is not None else "")
                        for item in last_detections
                    )
                    print(summary or "no detections", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        print("Detection preview stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
