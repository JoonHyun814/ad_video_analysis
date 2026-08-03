"""scenario_analysis.json 1건을 concept+production 양쪽으로 추출해 ChromaDB 두 컬렉션에
적재하는 통합 파이프라인 — 이 파이프라인의 진입점은 run_pipeline() 하나뿐이다.

evaluation/strategy(+evaluation/concept)·evaluation/creative 로 나뉘어 있던 추출·적재를
호출부에서 CLI 3번 조합할 필요 없이 한 번에 끝내기 위한 모듈이다. 저장 형식은 기존
concept_reference_store.upsert_concept_reference()/element_vector_store.upsert_analysis() 가
그대로 소비하는 모양을 유지해 저장 계층은 재사용한다(새로 짠 것은 프롬프트뿐).
"""
import json
from pathlib import Path

from utils.io_checks import require_valid_json
from utils.llm_dispatch import call_llm

from evaluation.ad_concept_production.concept_prompt import build_concept_prompt
from evaluation.ad_concept_production.production_prompt import build_production_prompt
from evaluation.creative import element_schema as es
from evaluation.creative.element_analysis import compute_duration
from evaluation.creative.run import _industry_for

_CONCEPT_FILE = "concept_analysis.json"
_PRODUCTION_FILE = "production_analysis.json"
_ENRICH_KEYS = ("target_gender", "duration_bucket", "price_tier")


def _extract_concept(scenario: dict, backend: str, timeout: int) -> dict:
    return call_llm(build_concept_prompt(scenario), backend=backend, timeout=timeout)


def _extract_production(scenario: dict, industry: str, secondary: str | None,
                        backend: str, timeout: int) -> dict:
    result = call_llm(build_production_prompt(scenario, industry, secondary), backend=backend, timeout=timeout)
    if "error" in result:
        return result
    duration = compute_duration(scenario)
    profile = result.setdefault("profile", {})
    profile["industry_category"] = industry
    if secondary:
        profile["industry_secondary"] = secondary
    if duration is not None:
        profile["duration_sec"] = duration
        profile["duration_bucket"] = es.duration_bucket(duration)
    casting = result.get("casting") or {}
    if "expression_restraint" in casting:  # LLM 이 "true"/"false" 문자열로 줄 때 bool 정규화
        casting["expression_restraint"] = str(casting["expression_restraint"]).lower() == "true"
    return result


def _save(video_dir: Path, filename: str, data: dict) -> None:
    (video_dir / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_pipeline(
    video_id: int,
    video_dir: Path,
    db_path: str | Path = "output/vector_db",
    backend: str = "claude",
    timeout: int = 600,
    force: bool = False,
) -> dict:
    """<video_dir>/scenario_analysis.json 을 읽어 concept_analysis.json·production_analysis.json
    으로 저장하고, 성공한 쪽만 각각 ad_concept_reference/ad_production_reference 에 upsert 한다.

    force=False(기본)면 concept_analysis.json/production_analysis.json 이 이미 있을 때 LLM 재호출
    없이 그 파일을 그대로 적재만 한다(재실행 안전 — 중단 후 이어서 돌려도 중복 과금 없음).
    force=True 면 있어도 무시하고 새로 추출한다.

    반환값의 concept_error/production_error 가 둘 다 None 이면 완전 성공이다.
    """
    scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")
    industry, secondary = _industry_for(video_dir)

    concept_path, production_path = video_dir / _CONCEPT_FILE, video_dir / _PRODUCTION_FILE

    if force or not concept_path.exists():
        concept = _extract_concept(scenario, backend, timeout)
        concept["_meta"] = {"video_id": video_id, "llm_backend": backend}
        _save(video_dir, _CONCEPT_FILE, concept)
    else:
        concept = json.loads(concept_path.read_text(encoding="utf-8"))

    if force or not production_path.exists():
        production = _extract_production(scenario, industry, secondary, backend, timeout)
        production["_meta"] = {"video_id": video_id, "llm_backend": backend}
        _save(video_dir, _PRODUCTION_FILE, production)
    else:
        production = json.loads(production_path.read_text(encoding="utf-8"))

    if "error" not in production:
        from evaluation.creative.element_vector_store import upsert_analysis
        upsert_analysis(video_id=video_id, analysis=production, db_path=db_path)

    if "error" not in concept:
        from evaluation.concept.concept_reference_store import upsert_concept_reference
        profile = production.get("profile") or {}
        enrich = {k: profile[k] for k in _ENRICH_KEYS if profile.get(k) is not None} or None
        upsert_concept_reference(video_id=video_id, strategy=concept, db_path=db_path, enrich=enrich)

    return {
        "video_id": video_id,
        "concept_error": concept.get("error"),
        "production_error": production.get("error"),
    }
