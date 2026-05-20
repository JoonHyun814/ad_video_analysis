from pathlib import Path

import cv2

from pipeline.cuts import Cut


def extract_keyframes(video_path: Path, cuts: list[Cut], output_dir: Path) -> list[Path]:
    """각 컷의 중간 프레임을 keyframe으로 추출해 output_dir에 저장하고 경로 리스트를 반환한다."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    saved: list[Path] = []

    try:
        for cut in cuts:
            path = _save_frame(cap, cut, output_dir)
            if path:
                saved.append(path)
    finally:
        cap.release()

    return saved


def _save_frame(cap: cv2.VideoCapture, cut: Cut, output_dir: Path) -> Path | None:
    mid_frame = (cut.start_frame + cut.end_frame) // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
    ret, frame = cap.read()
    if not ret:
        return None
    path = output_dir / f"cut_{cut.index:03d}_frame_{mid_frame:05d}.jpg"
    cv2.imwrite(str(path), frame)
    return path
