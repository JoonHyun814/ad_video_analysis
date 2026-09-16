"""이미 comparison.json 이 있는 (run_id, video_id, storyboard_id) 에 대해 스토리보드 텍스트만
QA 필터 없이 다시 조회한다.

comparison.json 이 존재한다는 것 자체가 생성 시점엔 유효한 유닛이었다는 뜻이다. 이후
v5postwork 에 새 QA 테스트 요청이 등록돼 지금은 matching.py::fetch_matched_units() 의 QA
필터에 걸리더라도, 이미 만들어진 비교 결과에 심화 지표(advanced_metrics.py — prompt·scenes
만 쓰고 video_url/video_source 는 쓰지 않는다)를 추가하는 데는 지장이 없어야 한다.
"""
from typing import Any

from db_config import get_connection
from matching import MatchedUnit, extract_scenes


def fetch_unit_by_id(run_id: str, video_id: int, storyboard_id: int, video_source: str) -> MatchedUnit | None:
    """QA 필터·postprocessed/original 판별 없이 정확한 세 키로만 prompt·scenes 를 조회한다."""
    row = _fetch_row(run_id, video_id, storyboard_id)
    if row is None:
        return None
    scenes = extract_scenes(row["machinejson"])
    if not scenes:
        return None
    return MatchedUnit(
        run_id=run_id, run_title="", video_id=video_id, storyboard_id=storyboard_id,
        concept_index=row["concept_index"], prompt=row["prompt"], video_url="",
        video_source=video_source, scenes=scenes,
    )


def _fetch_row(run_id: str, video_id: int, storyboard_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT v.prompt AS prompt, sb.conceptindex AS concept_index, "
                "sb.machinejson AS machinejson "
                "FROM v5videos v JOIN v5storyboards sb ON sb.id = v.storyboardid "
                "WHERE v.runid=%s AND v.id=%s AND v.storyboardid=%s",
                (run_id, video_id, storyboard_id),
            )
            return cur.fetchone()
    finally:
        conn.close()
