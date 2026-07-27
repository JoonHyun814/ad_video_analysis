"""검색된 N편 광고 세그먼트의 크리에이티브 요소를 집계하고 클리셰를 비튼 광고를 찾는다.

creative vector db(video_creative_profile/ad_creative_element)에 이미 적재된 영상만
대상으로 한다 — scenario_analysis.json 자동 추출이나 category DB 조회는 하지 않는다.
"""
from pathlib import Path

from evaluation.creative.cliche_aggregate import aggregate_elements
from evaluation.creative.element_vector_store import fetch_elements, fetch_profiles


def build_segment_report(video_ids: list[int], db_path: Path) -> dict:
    """검색된 video_id 목록을 하나의 임시 세그먼트로 보고 요소 빈도를 집계한다."""
    where = {"video_id": {"$in": video_ids}}
    elements = fetch_elements(where=where, db_path=db_path)
    profiles = fetch_profiles(where=where, db_path=db_path)
    return aggregate_elements(elements, profiles)


def _dominant_rows_by_type(report: dict) -> dict[str, dict]:
    dominant: dict[str, dict] = {}
    for row in report["rows"]:
        if row["judgement"] not in ("strong_cliche", "convention"):
            continue
        cur = dominant.get(row["element_type"])
        if cur is None or row["ratio"] > cur["ratio"]:
            dominant[row["element_type"]] = row
    return dominant


def select_notable_cliches(report: dict) -> tuple[list[dict], int]:
    """전체 (element_type, subtype) 조합 중 '중요해 보이는' 클리셰만 추린다.

    strong_cliche(빈도 60%↑)는 전부 포함한다. element_type 에 strong_cliche 가
    하나도 없으면 그 안에서 가장 우세한 convention(30~60%) 1건만 포함해, 근소한
    convention 여러 건이 나란히 나오는 잡음을 줄인다. minor/cliche_breaker 는 제외
    (breaker 는 별도 '비틀기' 절에서 다룬다). 반환값 2번째는 후보 총 개수(선별 전).
    """
    by_type: dict[str, list[dict]] = {}
    for row in report["rows"]:
        if row["judgement"] in ("strong_cliche", "convention"):
            by_type.setdefault(row["element_type"], []).append(row)

    notable: list[dict] = []
    for rows in by_type.values():
        strong = [r for r in rows if r["judgement"] == "strong_cliche"]
        notable += strong if strong else [max(rows, key=lambda r: r["ratio"])]
    notable.sort(key=lambda r: -r["ratio"])
    return notable, sum(len(v) for v in by_type.values())


def aggregate_twist_strategies(report: dict) -> list[dict]:
    """실제 클리셰(strong_cliche/convention)가 있는 element_type 별로, 그걸 비트는 대안
    subtype 들을 모아 일반화된 '비틀기 전략'을 만든다 (특정 광고 귀속 없이).

    대조군 없는 고립(모두 제각각이라 다수결 자체가 없는 경우, 단순 다양성)은 제외한다.
    """
    dominant_by_type = _dominant_rows_by_type(report)
    strategies: dict[str, dict] = {}
    for row in report["rows"]:
        if row["judgement"] != "cliche_breaker":
            continue
        dominant = dominant_by_type.get(row["element_type"])
        if dominant is None:
            continue
        entry = strategies.setdefault(row["element_type"], {
            "element_type": row["element_type"],
            "dominant_subtype": dominant["element_subtype"],
            "dominant_ratio": dominant["ratio"],
            "alternatives": [],
        })
        entry["alternatives"].append({
            "subtype": row["element_subtype"],
            "example": row["examples"][0]["document"] if row["examples"] else "",
        })
    return sorted(strategies.values(), key=lambda s: -s["dominant_ratio"])
