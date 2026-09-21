"""컷 안에서 태깅에 쓸 대표 프레임을 고른다 (긴 컨텍스트 방지)."""
from pathlib import Path

from pipeline.cut_analysis import _build_frame_map, _get_cut_frames
from pipeline.cuts import Cut

FrameList = list[tuple[float, Path]]


def load_frame_map(frames_dir: Path) -> dict[int, Path]:
    """전처리가 만든 fps=2 프레임을 {프레임 번호: 경로} 로 로드한다."""
    return _build_frame_map(frames_dir)


def select_cut_frames(frame_map: dict[int, Path], cut: Cut, max_frames: int) -> FrameList:
    """컷 구간 프레임을 시간순으로 모은 뒤 처음·끝을 포함해 max_frames 장으로 균등 샘플링한다."""
    frames = _get_cut_frames(frame_map, cut)
    return _even_sample(frames, max_frames)


def _even_sample(frames: FrameList, max_n: int) -> FrameList:
    if len(frames) <= max_n:
        return frames
    if max_n == 1:
        return [frames[len(frames) // 2]]
    last = len(frames) - 1
    return [frames[round(i * last / (max_n - 1))] for i in range(max_n)]
