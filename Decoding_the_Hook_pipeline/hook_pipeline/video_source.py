"""video_id → 영상 경로·제목 조회. 기존 pipeline/video_loader.get_video_info 를 그대로 사용한다."""
from dataclasses import dataclass
from pathlib import Path

from hook_pipeline.config import ensure_legacy_on_path


@dataclass
class VideoSource:
    key: str  # 출력 폴더명 (video_id 또는 파일 stem)
    video_id: int | None
    path: Path
    title: str  # 논문 프롬프트의 {ad title text}


def from_video_id(video_id: int) -> VideoSource:
    """DB(video_uploads)에서 영상 파일을 찾는다. 제목은 original_filename 의 확장자를 뗀 값."""
    ensure_legacy_on_path()
    from pipeline.video_loader import get_video_info

    path, row = get_video_info(video_id)
    title = Path(row.get("original_filename") or path.name).stem
    return VideoSource(key=str(video_id), video_id=video_id, path=path, title=title)


def from_path(path: Path) -> VideoSource:
    """DB 조회 없이 파일 경로로 직접 지정한다."""
    if not path.exists():
        raise FileNotFoundError(f"영상 파일 없음: {path}")
    return VideoSource(key=path.stem, video_id=None, path=path, title=path.stem)


def expand_id_range(spec: str) -> list[int]:
    """'1-5,7,9-12' 형식을 정수 목록으로 변환한다 (기존 cli 와 동일 문법)."""
    ids: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            ids.extend(range(int(a), int(b) + 1))
        elif part:
            ids.append(int(part))
    return ids
