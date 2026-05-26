import os
from pathlib import Path

import cv2

from pipeline.cuts import Cut


def detect_cuts_transnetv2(
    video_path: Path,
    threshold: float = 0.3,
    min_scene_sec: float = 0.5,
) -> list[Cut]:
    """TransNetV2로 컷 경계를 감지하고 Cut 리스트를 반환한다.

    threshold: 장면 전환 감지 임계값 (0.0~1.0, 낮을수록 민감, 기본 0.3)
    min_scene_sec: 최소 컷 길이(초) 미만은 제거한다.
    """
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    # TF 기본 동작은 GPU 전체 메모리를 선점. 이후 단계(OCR 등)를 위해 필요한 만큼만 할당하도록 설정.
    os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
    from transnetv2 import TransNetV2

    model = TransNetV2()
    fps = _get_fps(video_path)
    _, predictions, _ = model.predict_video(str(video_path))
    scenes = model.predictions_to_scenes(predictions, threshold=threshold)

    min_frames = int(fps * min_scene_sec)
    filtered = [(sf, ef) for sf, ef in scenes if (ef - sf) >= min_frames]

    return [
        Cut(
            index=i + 1,
            start_frame=int(sf),
            end_frame=int(ef),
            start_sec=round(int(sf) / fps, 3),
            end_sec=round(int(ef) / fps, 3),
        )
        for i, (sf, ef) in enumerate(filtered)
    ]



def _get_fps(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    return fps
