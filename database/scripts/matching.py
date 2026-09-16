"""prompt·스토리보드 이미지·영상이 모두 존재하는 (run, video, storyboard) 매칭 단위 조회.

v5videos 1건은 v5storyboards 1건(storyboardid)에서 나온 프롬프트로 생성된다. 셋 다 있어야
scenario_analysis 와 원본을 비교할 수 있으므로, storyboardid 로 정확히 짝지어 반환한다.

나레이션 음성 또는 로고/QR/오버레이 후반 합성이 끝난 영상(caption/narration)이 없는 건은
평가 대상에서 아예 제외한다 — AI 원본 생성 영상(videourl)만 있는 건 스킵한다.

v5postwork(후반 합성 요청) 실측 결과, captionvideourl 이 있는 videoid 상당수가 실제 클라이언트
납품이 아니라 PTBWA 내부 QA 테스트("QA v0.9 오버레이 문구", "424", "ㅇㅇ" 같은 placeholder
문구)였고, 그 중 일부는 렌더 워커가 엉뚱한 원본 영상을 합성하는 버그까지 확인됐다. 이런
overlaymsg/keywordtext 패턴을 가진 videoid 는 매칭에서 제외한다.

추가 실측: captionvideourl 파일명이 `<runid>_<videoid>.mp4`(원본과 동일한, 해시 없는 단순
이름)인 경우와 `<runid>_<videoid>_crf23_fast_none_<해시>.mp4`(잡별 고유 해시 포함)인 경우로
나뉘는데, 단순 이름 쪽에서만 오매칭이 확인됐다(6건 중 3건). 해시 포함 이름은 검증한 7건 전부
정상이었다 — 렌더 워커에 코드 경로가 두 개 있고, 해시 없는 쪽이 videoid 재처리 시 파일명이
겹쳐 덮어쓰기/경쟁 상태를 일으키는 것으로 추정된다. `require_verified_caption=True` 로 이
"안전한" 해시 패턴 캡션만 고를 수 있다.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any

from db_config import get_connection

_QA_LABEL_RE = re.compile(r"qa\s*v\d", re.IGNORECASE)
_JAMO_ONLY_RE = re.compile(r"^[ㄱ-ㅎㅏ-ㅣ]+$")
_VERIFIED_CAPTION_RE = re.compile(r"_crf23_fast_none_")

_VIDEO_SOURCES = ("postprocessed", "original")

_BASE_CANDIDATE_QUERY = """
SELECT
    v.id AS video_id,
    v.runid AS run_id,
    v.storyboardid AS storyboard_id,
    v.prompt AS prompt,
    v.videourl AS video_url,
    v.narrationvideourl AS narration_video_url,
    v.narrationstatus AS narration_status,
    v.captionvideourl AS caption_video_url,
    v.captionrenderstatus AS caption_render_status,
    v.regdt AS video_regdt,
    r.title AS run_title,
    sb.conceptindex AS concept_index,
    sb.machinejson AS machinejson
FROM v5videos v
JOIN v5storyboards sb ON sb.id = v.storyboardid
JOIN v5runs r ON r.runid = v.runid
WHERE v.prompt IS NOT NULL AND v.prompt <> ''
  AND v.videourl IS NOT NULL AND v.videourl <> ''
  {extra_condition}
ORDER BY v.regdt DESC
LIMIT 500
"""

_POSTPROCESSED_ONLY_CONDITION = """
  AND (
    (v.captionrenderstatus = 'done' AND v.captionvideourl IS NOT NULL AND v.captionvideourl <> '')
    OR (v.narrationstatus = 'done' AND v.narrationvideourl IS NOT NULL AND v.narrationvideourl <> '')
  )
"""


def _resolve_video(row: dict) -> tuple[str, str] | tuple[None, None]:
    """나레이션·로고/오버레이 후반 합성이 끝난 영상만 선택한다 (원본 videourl 은 쓰지 않는다).

    caption(로고·QR·키워드·오버레이 문구 burn-in, 나레이션이 있었다면 그 오디오까지 포함해
    재인코딩된 최종 렌더) > narration(TTS 나레이션만 합성) 순. 둘 다 없으면 (None, None) —
    SQL WHERE 절에서 이미 걸러지므로 정상 경로에서는 발생하지 않는 방어적 처리다.
    """
    if row.get("caption_render_status") == "done" and row.get("caption_video_url"):
        return row["caption_video_url"], "caption"
    if row.get("narration_status") == "done" and row.get("narration_video_url"):
        return row["narration_video_url"], "narration"
    return None, None


@dataclass
class MatchedUnit:
    run_id: str
    run_title: str
    video_id: int
    storyboard_id: int
    concept_index: int
    prompt: str
    video_url: str
    video_source: str  # "caption" | "narration" | "original"
    scenes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def expected_cut_count(self) -> int:
        """스토리보드 씬의 shots(서브컷) 합계 — shots 가 없으면 씬 자체를 1컷으로 센다."""
        total = 0
        for scene in self.scenes:
            shots = scene.get("shots")
            total += len(shots) if shots else 1
        return total


def fetch_matched_units(
    limit: int, video_source: str = "postprocessed", require_verified_caption: bool = False,
) -> list[MatchedUnit]:
    """prompt·스토리보드 이미지·영상이 모두 있는 (run, video) 조합을 최근 순으로 최대 limit개
    반환한다.

    video_source="postprocessed"(기본): 나레이션/캡션(로고·오버레이) 후반 합성이 끝난 영상만
    대상으로 한다(QA 테스트로 보이는 videoid 도 제외). "original": 후반 합성 여부와 무관하게
    AI 원본 생성 영상(videourl)을 그대로 쓴다 — 후반 합성 유무에 따라 비교 결과가 어떻게
    달라지는지 볼 때 쓴다.

    require_verified_caption=True 면 caption 소스 중 해시 포함 파일명(`_crf23_fast_none_`)만
    고른다 — 오매칭이 확인된 적 없는 "안전한" 렌더 경로만 골라 성공률을 높인다(모듈 docstring
    참고). video_source="original" 이나 narration 소스에는 영향 없다.

    두 모드 다 storyboard_count > 0 이어도 machinejson 파싱 결과 이미지가 하나도 없는 건은
    제외된다 — 반환된 개수가 요청한 limit 보다 적을 수 있다.
    """
    if video_source not in _VIDEO_SOURCES:
        raise ValueError(f"video_source 는 {_VIDEO_SOURCES} 중 하나여야 합니다: {video_source}")

    rows = _fetch_candidates(video_source)
    qa_flagged = (
        _fetch_qa_flagged_video_ids([r["video_id"] for r in rows])
        if video_source == "postprocessed" else set()
    )

    units: list[MatchedUnit] = []
    for row in rows:
        if row["video_id"] in qa_flagged:
            continue
        scenes = extract_scenes(row["machinejson"])
        if not scenes:
            continue
        if video_source == "postprocessed":
            video_url, resolved_source = _resolve_video(row)
            if video_url is None:
                continue
            if (
                require_verified_caption and resolved_source == "caption"
                and not _VERIFIED_CAPTION_RE.search(video_url)
            ):
                continue
        else:
            video_url, resolved_source = row["video_url"], "original"
        units.append(MatchedUnit(
            run_id=row["run_id"],
            run_title=row["run_title"],
            video_id=row["video_id"],
            storyboard_id=row["storyboard_id"],
            concept_index=row["concept_index"],
            prompt=row["prompt"],
            video_url=video_url,
            video_source=resolved_source,
            scenes=scenes,
        ))
        if len(units) >= limit:
            break
    return units


def _fetch_candidates(video_source: str) -> list[dict]:
    condition = _POSTPROCESSED_ONLY_CONDITION if video_source == "postprocessed" else ""
    query = _BASE_CANDIDATE_QUERY.format(extra_condition=condition)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()
    finally:
        conn.close()


def _fetch_qa_flagged_video_ids(video_ids: list[int]) -> set[int]:
    """overlaymsg/keywordtext 가 QA 테스트·placeholder 로 보이는 v5postwork 요청이 하나라도
    있는 videoid 집합을 반환한다 — captionvideourl 이 실제 납품본이 아닐 위험이 큰 videoid."""
    if not video_ids:
        return set()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(video_ids))
            cur.execute(
                f"SELECT videoid, overlaymsg, keywordtext FROM v5postwork WHERE videoid IN ({fmt})",
                video_ids,
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        r["videoid"] for r in rows
        if _looks_like_qa_test(r["overlaymsg"]) or _looks_like_qa_test(r["keywordtext"])
    }


def _looks_like_qa_test(text: str | None) -> bool:
    """'QA v0.9 ...' 명시적 QA 라벨, 순수 숫자, 자모만 있는 의미없는 placeholder 문구를 감지한다."""
    if not text:
        return False
    t = text.strip()
    if not t:
        return False
    return bool(_QA_LABEL_RE.search(t) or t.isdigit() or _JAMO_ONLY_RE.match(t))


def extract_scenes(machinejson_text: str | None) -> list[dict[str, Any]]:
    """machinejson.m9.scenes 중 sketchurl(스토리보드 이미지)이 있는 항목만 반환한다."""
    try:
        data = json.loads(machinejson_text or "{}")
    except (json.JSONDecodeError, TypeError):
        return []
    scenes = (data.get("m9") or {}).get("scenes") or []
    return [s for s in scenes if s.get("sketchurl")]
