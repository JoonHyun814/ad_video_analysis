from pathlib import Path

import cv2


def extract_frames_at_fps(
    video_path: Path,
    output_dir: Path,
    fps: float = 2.0,
) -> list[Path]:
    """영상 전체에서 지정된 fps로 프레임을 추출해 output_dir에 저장하고 경로 리스트를 반환한다."""
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = src_fps / fps  # 몇 프레임마다 1장 저장할지

    saved: list[Path] = []
    frame_idx = 0
    saved_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx >= round(saved_idx * frame_interval):
                path = output_dir / f"frame_{frame_idx:06d}.jpg"
                cv2.imwrite(str(path), frame)
                saved.append(path)
                saved_idx += 1
            frame_idx += 1
    finally:
        cap.release()

    return saved
