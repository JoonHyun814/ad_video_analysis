"""prompt·스토리보드 이미지·영상이 모두 존재하는 (run, video, storyboard) 매칭 단위 조회.

v5videos 1건은 v5storyboards 1건(storyboardid)에서 나온 프롬프트로 생성된다. 셋 다 있어야
scenario_analysis 와 원본을 비교할 수 있으므로, storyboardid 로 정확히 짝지어 반환한다.
"""
import json
from dataclasses import dataclass, field
from typing import Any

from db_config import get_connection

_CANDIDATE_QUERY = """
SELECT
    v.id AS video_id,
    v.runid AS run_id,
    v.storyboardid AS storyboard_id,
    v.prompt AS prompt,
    v.videourl AS video_url,
    v.regdt AS video_regdt,
    r.title AS run_title,
    sb.conceptindex AS concept_index,
    sb.machinejson AS machinejson
FROM v5videos v
JOIN v5storyboards sb ON sb.id = v.storyboardid
JOIN v5runs r ON r.runid = v.runid
WHERE v.prompt IS NOT NULL AND v.prompt <> ''
  AND v.videourl IS NOT NULL AND v.videourl <> ''
ORDER BY v.regdt DESC
LIMIT 500
"""


@dataclass
class MatchedUnit:
    run_id: str
    run_title: str
    video_id: int
    storyboard_id: int
    concept_index: int
    prompt: str
    video_url: str
    scenes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def expected_cut_count(self) -> int:
        """스토리보드 씬의 shots(서브컷) 합계 — shots 가 없으면 씬 자체를 1컷으로 센다."""
        total = 0
        for scene in self.scenes:
            shots = scene.get("shots")
            total += len(shots) if shots else 1
        return total


def fetch_matched_units(limit: int) -> list[MatchedUnit]:
    """prompt·영상·스토리보드 이미지가 모두 있는 (run, video) 조합을 최근 순으로 최대 limit개 반환.

    storyboard_count > 0 이어도 machinejson 파싱 결과 이미지가 하나도 없는 건은 비교가
    불가능하므로 여기서 걸러진다 — 반환된 개수가 요청한 limit 보다 적을 수 있다.
    """
    rows = _fetch_candidates()

    units: list[MatchedUnit] = []
    for row in rows:
        scenes = _extract_scenes(row["machinejson"])
        if not scenes:
            continue
        units.append(MatchedUnit(
            run_id=row["run_id"],
            run_title=row["run_title"],
            video_id=row["video_id"],
            storyboard_id=row["storyboard_id"],
            concept_index=row["concept_index"],
            prompt=row["prompt"],
            video_url=row["video_url"],
            scenes=scenes,
        ))
        if len(units) >= limit:
            break
    return units


def _fetch_candidates() -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_CANDIDATE_QUERY)
            return cur.fetchall()
    finally:
        conn.close()


def _extract_scenes(machinejson_text: str | None) -> list[dict[str, Any]]:
    """machinejson.m9.scenes 중 sketchurl(스토리보드 이미지)이 있는 항목만 반환한다."""
    try:
        data = json.loads(machinejson_text or "{}")
    except (json.JSONDecodeError, TypeError):
        return []
    scenes = (data.get("m9") or {}).get("scenes") or []
    return [s for s in scenes if s.get("sketchurl")]
