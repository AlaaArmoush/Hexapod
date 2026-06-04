from __future__ import annotations

import numpy as np


def _nms(dets: np.ndarray, nms_thresh: float = 0.5) -> list[int]:
    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]
    scores = dets[:, 4]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        overlap = inter / (areas[i] + areas[order[1:]] - inter)
        indexes = np.where(overlap <= nms_thresh)[0]
        order = order[indexes + 1]
    return keep


def _xywh_to_xyxy(bboxes: np.ndarray) -> np.ndarray:
    xyxy_bboxes = np.zeros_like(bboxes)
    xyxy_bboxes[:, 0] = bboxes[:, 0] - bboxes[:, 2] / 2
    xyxy_bboxes[:, 1] = bboxes[:, 1] - bboxes[:, 3] / 2
    xyxy_bboxes[:, 2] = bboxes[:, 0] + bboxes[:, 2] / 2
    xyxy_bboxes[:, 3] = bboxes[:, 1] + bboxes[:, 3] / 2
    return xyxy_bboxes


def _make_grid(ny: int, nx: int, na: int) -> np.ndarray:
    yv, xv = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
    return np.stack((xv, yv), 2).reshape(1, na, ny, nx, 2)


def _parse_output(output: np.ndarray, stride: int, num_outputs: int) -> np.ndarray:
    batch_size, _, ny, nx = output.shape
    grid = _make_grid(ny, nx, 1)
    parsed = output.reshape(batch_size, 1, num_outputs, ny, nx).transpose((0, 1, 3, 4, 2))
    x1y1 = grid - parsed[..., 0:2] + 0.5
    x2y2 = grid + parsed[..., 2:4] + 0.5
    center_xy = (x1y1 + x2y2) / 2
    width_height = x2y2 - x1y1
    parsed[..., 0:2] = center_xy * stride
    parsed[..., 2:4] = width_height * stride
    return parsed.reshape(batch_size, -1, num_outputs)


def decode_yolov6_outputs(
    outputs: list[np.ndarray],
    *,
    strides: list[int] | None = None,
    confidence_threshold: float = 0.45,
    iou_threshold: float = 0.45,
    num_classes: int = 80,
) -> np.ndarray:
    strides = strides or [8, 16, 32]
    num_outputs = num_classes + 5
    parsed = None
    for output, stride in zip(outputs, strides):
        parsed_output = _parse_output(output, stride, num_outputs)
        parsed = parsed_output if parsed is None else np.concatenate((parsed, parsed_output), axis=1)
    if parsed is None:
        return np.zeros((0, 6))

    candidates = parsed[0][parsed[0][..., 4] > confidence_threshold]
    if candidates.size == 0:
        return np.zeros((0, 6))

    boxes = _xywh_to_xyxy(candidates[:, :4])
    class_scores = candidates[:, 5 : 5 + num_classes]
    class_ids = np.expand_dims(class_scores.argmax(1), 1)
    confidences = class_scores.max(1, keepdims=True)
    detections = np.concatenate((boxes, confidences, class_ids), 1)
    detections = detections[confidences.flatten() > confidence_threshold]
    if detections.size == 0:
        return np.zeros((0, 6))

    class_offset = detections[:, 5:6] * 7680
    keep = _nms(
        np.hstack((detections[:, :4] + class_offset, detections[:, 4][..., np.newaxis])).astype(
            np.float32,
            copy=False,
        ),
        iou_threshold,
    )
    return detections[np.array(keep)]
