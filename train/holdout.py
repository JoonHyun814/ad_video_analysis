"""video_id 기준으로 학습/홀드아웃 세트를 나누고 매니페스트로 저장한다.

dataset_builder.build_all() 은 기본적으로 data_dirs 내 모든 video_id 를 학습 데이터로
쓴다. 파인튜닝 전후 품질을 비교할 대조군이 없다는 뜻이다. 이 모듈로 일부 video_id 를
미리 떼어내 매니페스트에 기록해두면, 학습에는 쓰지 않고 나중에 before/after 비교에만
쓸 수 있다.
"""

import json
import random
from pathlib import Path


def list_video_ids(data_dirs: list[Path]) -> list[str]:
    """data_dirs 전체에서 중복 제거된 video_id 목록을 정렬해 반환한다."""
    ids: set[str] = set()
    for data_dir in data_dirs:
        for p in data_dir.iterdir():
            if p.is_dir() and p.name.isdigit():
                ids.add(p.name)
    return sorted(ids, key=int)


def select_holdout(video_ids: list[str], ratio: float, seed: int) -> set[str]:
    """video_id 목록에서 ratio 비율만큼 홀드아웃 집합을 무작위로 뽑는다 (seed 고정 시 재현 가능)."""
    if not (0.0 < ratio < 1.0):
        raise ValueError(f"ratio는 0과 1 사이여야 합니다: {ratio}")
    n = max(1, round(len(video_ids) * ratio))
    rng = random.Random(seed)
    return set(rng.sample(video_ids, n))


def save_manifest(holdout_ids: set[str], path: Path, seed: int, ratio: float) -> None:
    """홀드아웃 video_id 목록을 재현 정보(seed·ratio)와 함께 JSON으로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seed": seed, "ratio": ratio, "holdout_ids": sorted(holdout_ids, key=int)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(path: Path) -> set[str]:
    """저장된 홀드아웃 매니페스트에서 video_id 집합을 읽어온다."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return set(payload["holdout_ids"])
