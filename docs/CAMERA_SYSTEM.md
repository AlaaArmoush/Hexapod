# Camera System

## Scope

This document covers the OAK-D depth camera pipeline: frame capture, object
detection, person tracking, approach control, and object search.

## Hardware

The OAK-D Lite provides an RGB sensor (1920×1080) and stereo IR cameras for
depth (640×400). It is driven by the DepthAI host SDK. The camera is mounted
on a pan servo controlled by the firmware `camera_pan` command.

## Provider

File: `camera/provider.py`

`DepthAICameraProvider` is the single entry point for all camera access.

```text
capture_image()      → CaptureResult(frame_bgr, timestamp)
detect_objects()     → list[ObjectDetection]
depth_probe()        → DepthProbeResult(distance_m, confidence, roi)
```

The device is exclusive — only one open handle at a time. Tool executor
functions open and close their own handle for one-shot use. Persistent
tracking sessions hold the handle open via `start()` / `stop()`.

Detection runs at 2 FPS on-device (YOLOv6 nano ONNX, 80 COCO classes).
`DETECTION_CONFIDENCE_THRESHOLD = 0.45`.

## Host Detector Fallback

File: `camera/host_detector.py`

`HostDetector` runs YOLOv8n on the host CPU via `ultralytics` when the OAK-D
on-device model is unavailable. It produces the same `ObjectDetection` schema
via `detection_from_yolo_box()` and `normalize_object_name()` from
`camera/yolo_decode.py`.

## Detection Schema

File: `camera/detection.py`

```python
@dataclass
class ObjectDetection:
    label: str           # normalized COCO name
    confidence: float    # 0–1
    bbox: tuple          # (x1, y1, x2, y2) normalized 0–1
    distance_m: float | None
    bbox_area: float     # normalized 0–1, used as depth fallback
```

`normalize_object_name()` maps raw COCO labels to consistent lowercase names
(e.g. `"person"`, `"chair"`, `"bottle"`).

## Depth

File: `camera/depth.py`

`summarize_center_depth()` reads the 20% center ROI from the depth map and
returns a `DepthProbeResult(distance_m, confidence, roi)`. Valid range is
0.2 m – 30 m.

## Clearance

File: `camera/clearance.py`

`check_clearance()` returns a `ClearanceResult` indicating whether an obstacle
is within `OBSTACLE_STOP_THRESHOLD_M = 0.5 m` of the robot. Used by the agent
before walk or approach commands.

## Person Tracker

File: `camera/tracker.py`

`PersonTracker` runs a background thread at ~5 FPS:

```text
grab_frame()
  → detect_objects() (filter for "person")
  → EMA-smooth position (alpha=0.4)
  → update target / lost_ms
```

`target: TrackedPerson | None` is the smoothed detection. `lost_ms` counts
milliseconds since the last detection.

```python
@dataclass
class TrackedPerson:
    frame_position_x: float   # -1.0 (far left) to +1.0 (far right)
    distance_m: float | None
    bbox_area: float
    confidence: float
```

Closeness is determined by `distance_m` when available, falling back to
`bbox_area`.

`tracker.reset()` clears the EMA so a fresh body alignment doesn't carry over
smoothed values from the previous angle.

## Approach Controller

File: `camera/approach.py`

`ApproachController` is a blocking loop. It is called from `pipeline.py` after
the body has been aligned to face the person.

```text
loop (timeout 60 s):
  if no target and lost_ms > 2000 ms → LOST
  if distance_m <= 0.9 m            → ARRIVED
  if |frame_position_x| > 0.5       → rotate 1 cycle toward person
  else                               → walk forward 3 steps
  sleep 1.2 s
```

The center threshold (`0.5`) is intentionally wide. The minimum firmware
rotation is 30°, which overshoots small corrections and causes oscillation.
Only large lateral offsets trigger a rotation.

Returns `ApproachResult`: `ARRIVED | LOST | TIMEOUT`.

## Object Searcher

File: `camera/search.py`

`ObjectSearcher` scans fixed pan positions and returns the first detection of
a named label.

```text
pan positions (in order): left → front_left → center → front_right → right
  for each position:
    send camera_pan command
    wait for frame
    detect objects
    if target label found → record result
return to center
return SearchResult(found, position, confidence, distance_m)
```

The searcher is triggered by `search_intent.py` before the LLM is invoked.
`match_search_intent(text)` matches phrases like `"find the bottle"`,
`"search for a person"`, and `"where is the chair"`.

## Config

File: `camera/config.py`

| Parameter | Value |
|-----------|-------|
| Capture resolution | 1920×1080 @ 5 FPS |
| Depth resolution | 640×400 @ 5 FPS |
| Detection rate | 2 FPS (on-device) |
| Confidence threshold | 0.45 |
| Depth range | 200–30 000 mm |
| Approach threshold | 0.9 m |
| Clearance stop distance | 0.5 m |
| Tracker EMA alpha | 0.4 |
| Tracker FPS | ~5 |

## Debug Tool

`scripts/tracking_preview.py` opens a live OpenCV window showing the camera
feed, detected bounding boxes, the smoothed crosshair position, and
distance/area values. Run with:

```bash
python scripts/tracking_preview.py
```
