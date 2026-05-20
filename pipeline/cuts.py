from dataclasses import dataclass
from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video


@dataclass
class Cut:
    index: int
    start_frame: int
    end_frame: int
    start_sec: float
    end_sec: float


def detect_cuts(video_path: Path, threshold: float = 27.0) -> list[Cut]:
    """ContentDetector로 컷 경계를 감지하고 Cut 리스트를 반환한다.

    threshold: 낮을수록 민감하게 감지 (기본 27.0)
    """
    video = open_video(str(video_path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video)

    scenes = manager.get_scene_list()
    return [
        Cut(
            index=i + 1,
            start_frame=s[0].get_frames(),
            end_frame=s[1].get_frames() - 1,
            start_sec=round(s[0].get_seconds(), 3),
            end_sec=round(s[1].get_seconds(), 3),
        )
        for i, s in enumerate(scenes)
    ]
