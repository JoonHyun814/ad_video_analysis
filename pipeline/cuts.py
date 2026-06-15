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


def merge_to_max_cuts(cuts: list[Cut], max_cuts: int) -> list[Cut]:
    """컷 수가 max_cuts 초과이면 가장 짧은 컷을 이웃 중 더 짧은 쪽에 반복 병합한다."""
    result = list(cuts)
    while len(result) > max_cuts:
        durations = [c.end_frame - c.start_frame for c in result]
        shortest = min(range(len(result)), key=lambda i: durations[i])

        has_prev = shortest > 0
        has_next = shortest < len(result) - 1

        if has_prev and has_next:
            neighbor = shortest - 1 if durations[shortest - 1] <= durations[shortest + 1] else shortest + 1
        elif has_prev:
            neighbor = shortest - 1
        else:
            neighbor = shortest + 1

        lo, hi = min(shortest, neighbor), max(shortest, neighbor)
        merged = Cut(
            index=result[lo].index,
            start_frame=result[lo].start_frame,
            end_frame=result[hi].end_frame,
            start_sec=result[lo].start_sec,
            end_sec=result[hi].end_sec,
        )
        result = result[:lo] + [merged] + result[hi + 1:]

    return [
        Cut(index=i + 1, start_frame=c.start_frame, end_frame=c.end_frame,
            start_sec=c.start_sec, end_sec=c.end_sec)
        for i, c in enumerate(result)
    ]


def detect_cuts(video_path: Path, threshold: float = 27.0) -> list[Cut]:
    """ContentDetector로 컷 경계를 감지하고 Cut 리스트를 반환한다.

    threshold: 낮을수록 민감하게 감지 (기본 27.0)
    씬 변화가 없어 0컷이 감지되면 영상 전체를 단일 컷으로 반환한다.
    """
    video = open_video(str(video_path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video)

    scenes = manager.get_scene_list()
    if scenes:
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

    duration = video.duration
    end_frame = (duration.get_frames() - 1) if duration else 0
    end_sec = round(duration.get_seconds(), 3) if duration else 0.0
    return [Cut(index=1, start_frame=0, end_frame=end_frame, start_sec=0.0, end_sec=end_sec)]
