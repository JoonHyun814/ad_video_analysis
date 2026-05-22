from pathlib import Path

import cv2
import numpy as np

_CASCADE_FILES = [
    "haarcascade_frontalface_alt2.xml",
    "haarcascade_profileface.xml",
]
_cascades: list[cv2.CascadeClassifier] | None = None


def _get_cascades() -> list[cv2.CascadeClassifier]:
    global _cascades
    if _cascades is None:
        _cascades = [
            cv2.CascadeClassifier(cv2.data.haarcascades + f)
            for f in _CASCADE_FILES
        ]
    return _cascades


def detect_faces_batch(frames: list[Path]) -> dict[str, list[dict]]:
    """전체 프레임에서 얼굴을 감지하고 {파일명: [face 리스트]} 를 반환한다."""
    cascades = _get_cascades()
    return {p.name: _detect_one(p, cascades) for p in frames}


def _detect_one(
    image_path: Path,
    cascades: list[cv2.CascadeClassifier],
) -> list[dict]:
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    h_img, w_img = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    boxes: list[list[int]] = []
    for cascade in cascades:
        detected = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
        )
        if len(detected):
            boxes.extend(detected.tolist())

    # 좌우 반전 이미지로 profile cascade 한 번 더 (반대 방향 얼굴 포착)
    gray_flip = cv2.flip(gray, 1)
    detected = cascades[1].detectMultiScale(
        gray_flip, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
    )
    if len(detected):
        for x, y, w, h in detected:
            boxes.append([w_img - x - w, y, w, h])

    if not boxes:
        return []

    boxes = _nms(boxes, iou_threshold=0.3)
    return [
        {
            "bbox": box,
            "area_ratio": round(box[2] * box[3] / (w_img * h_img), 4),
        }
        for box in boxes
    ]


def _nms(boxes: list[list[int]], iou_threshold: float) -> list[list[int]]:
    """IoU 기반 Non-Maximum Suppression으로 중복 bbox를 제거한다."""
    if not boxes:
        return []
    arr = np.array(boxes, dtype=float)
    x1, y1 = arr[:, 0], arr[:, 1]
    x2, y2 = arr[:, 0] + arr[:, 2], arr[:, 1] + arr[:, 3]
    areas = arr[:, 2] * arr[:, 3]
    order = areas.argsort()[::-1]

    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        ix1 = np.maximum(x1[i], x1[rest])
        iy1 = np.maximum(y1[i], y1[rest])
        ix2 = np.minimum(x2[i], x2[rest])
        iy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0, ix2 - ix1) * np.maximum(0, iy2 - iy1)
        iou = inter / (areas[i] + areas[rest] - inter)
        order = rest[iou < iou_threshold]

    return [[int(v) for v in arr[i]] for i in keep]
