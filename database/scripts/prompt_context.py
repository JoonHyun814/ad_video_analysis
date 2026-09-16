"""compare_scenario.py 와 advanced_metrics.py 가 공통으로 쓰는 스토리보드 프롬프트 포맷터.

claude -p 에 넘길 스토리보드 씬 목록 텍스트 블록을 만드는 로직은 두 판정 모두 동일하므로
여기서 한 번만 구현한다.
"""
from pathlib import Path

from matching import MatchedUnit


def format_storyboard_block(unit: MatchedUnit, images_dir: Path) -> str:
    """스토리보드 씬 목록을 'Scene N (time): brief=... | ...' 형식의 텍스트 블록으로 변환한다."""
    lines = []
    for scene in unit.scenes:
        img_path = images_dir / f"scene{scene.get('no')}.png"
        shot_count = len(scene.get("shots") or []) or 1
        lines.append(
            f"- Scene {scene.get('no')} ({scene.get('time')}): brief={scene.get('brief')} | "
            f"visual={scene.get('visual')} | audio={scene.get('audio')} | overlay={scene.get('overlay')} | "
            f"shots={shot_count}개 | 이미지파일={img_path}"
        )
    return "\n".join(lines)
