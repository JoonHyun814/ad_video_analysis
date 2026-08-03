"""strategy_analysis.json(M1·M2·M3 역추출)을 ad_concept_reference 컬렉션에 적재·조회한다.

M3(컨셉 발산)이 "이 브리프(M0~M2)와 전략적으로 비슷한 기존 광고는 어떤 인간 진실·가치
제안에서 출발해 어떤 전략 렌즈로 컨셉을 만들고 그 why 를 어떻게 증명했는가"를 참고하는
전용 컬렉션이다 — 연출/촬영 디테일은 다루지 않는다(그건 컨셉 확정 후 M5~M9·스토리보드가
참고하는 evaluation/creative/element_vector_store.py 의 ad_production_reference 몫).
evaluation/README.md 스키마 통합 계획 참고.

evaluation/strategy/run.py(evaluation/strategy/strategy_extraction.py)가 scenario_analysis.json
에서 역추출한 m1(corejob·humantruth)/m2(valueproposition)/m3(lens·bigidea·provingwhy·job·
differentiation·claimtag·risk)를 문서·메타데이터로 쓴다 — concept_evaluation.json(구 스키마,
flat 카테고리 라벨만 있고 "왜 이 컨셉인가"의 인과가 없음)은 더 이상 문서 본문에 쓰지 않고,
있으면 세그먼트 필터용 카테고리 메타데이터(industry_category 등)로만 보조 사용한다.

레거시 evaluation/concept/concept_vector_store.py(video_concept)·facet_vector_store.py
(ad_target/ad_usp/ad_creative)를 대체한다 — 두 파일은 legacy G1~G6 파이프라인이 여전히
참조하므로 삭제하지 않고 그대로 두되, 이 모듈은 그것들을 재사용하지 않는다.
"""
from pathlib import Path

import chromadb

from evaluation.category.vector_store import _get_or_create

CONCEPT_COLLECTION = "ad_concept_reference"

# creative_element_analysis.json(production reference)의 profile 에서 가져올 수 있으면
# 같이 심어두는 크로스 세그먼트 필드 — M3 가 길이/가격대로도 좁혀 검색할 수 있게 한다.
_ENRICH_KEYS = ("target_gender", "duration_bucket", "price_tier")

# concept_evaluation.json(구 스키마)이 있으면 세그먼트 필터 보조용으로만 남기는 카테고리 필드.
# 문서 본문(_document)에는 쓰지 않는다 — strategy_analysis.json 이 없는 영상의 필터링 커버리지를
# 넓히기 위한 하위호환 메타데이터일 뿐, "왜 이 컨셉인가" 인과는 여기서 나오지 않는다.
_LEGACY_META_FIELDS: tuple[tuple[str, str], ...] = (
    ("target_persona", "target_persona_category"),
    ("usp", "usp_category"),
    ("positioning", "positioning_category"),
    ("appeal_type", "appeal_type"),
    ("perceived_value", "perceived_value_category"),
    ("message_strategy", "message_strategy_category"),
)

_LENS_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("twist_taboo_break", ("반전", "금기")),
    ("metaphor_analogy", ("비유", "은유")),
    ("demo_evidence", ("데모", "증거", "시연")),
    ("enemy_personification", ("의인화",)),
    ("user_testimonial", ("증언",)),
    ("identity_belonging", ("정체성", "소속")),
    ("functional_job_direct", ("기능적",)),
    ("emotional_job_direct", ("감정적",)),
    ("comparison_contrast", ("비교", "대조")),
)


def _normalize_lens(raw: str) -> str:
    """strategy_analysis.json 의 m3.concepts[].lens 는 자유 텍스트라(고정 enum 아님)
    module3.md 9종 전략 렌즈 어휘로 정규화해야 exact-match 세그먼트 필터가 걸린다."""
    if not raw:
        return "other"
    lowered = raw.lower()
    for lens, keywords in _LENS_KEYWORDS:
        if any(kw.lower() in lowered for kw in keywords):
            return lens
    return "other"


def _select_concept(m3: dict) -> dict:
    """m3.concepts 는 evaluation/strategy/strategy_schemas.py M3_GUIDE 상 정확히 1개가 정상
    (역추출은 발산이 아니므로). 드물게 여러 개가 나오면(프롬프트 이탈) 이름에 실구현 마커가
    붙은 것을 우선하고, 없으면 첫 번째를 쓴다."""
    concepts = m3.get("concepts") or []
    if len(concepts) <= 1:
        return concepts[0] if concepts else {}
    for c in concepts:
        name = c.get("name", "")
        if "실구현" in name or "주 컨셉" in name:
            return c
    return concepts[0]


def _collection(db_path: str | Path) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(db_path))
    return _get_or_create(client, CONCEPT_COLLECTION)


def _document(strategy: dict) -> str:
    m1, m2 = strategy.get("m1") or {}, strategy.get("m2") or {}
    concept = _select_concept(strategy.get("m3") or {})
    truth = m1.get("humantruth") or {}
    fields = (
        ("핵심 Job", m1.get("corejob", "")),
        ("인간 진실", truth.get("truth", "")),
        ("진실의 모순", truth.get("contradiction", "")),
        ("가치 제안(why)", m2.get("valueproposition", "")),
        ("전략 렌즈", concept.get("lens", "")),
        ("빅 아이디어", concept.get("bigidea", "")),
        ("why 를 증명하는 방식", concept.get("provingwhy", "")),
        ("충족하는 Job", concept.get("job", "")),
        ("차별화 이유", concept.get("differentiation", "")),
        ("리스크", concept.get("risk", "")),
    )
    return "\n".join(f"{label}: {val}" for label, val in fields if val)


def _first_category(concept_eval: dict, field: str) -> str | None:
    block = concept_eval.get(field)
    if not isinstance(block, dict):
        return None
    cats = block.get("category")
    return cats[0] if isinstance(cats, list) and cats else None


def _legacy_metadata(concept_eval: dict) -> dict:
    """concept_evaluation.json(있으면)에서 뽑는 보조 세그먼트 필터 필드."""
    meta: dict = {}
    industries = concept_eval.get("industry_category")
    if isinstance(industries, list) and industries:
        meta["industry_category"] = industries[0]
    if product_category := concept_eval.get("product_category"):
        meta["product_category"] = product_category
    for field, meta_key in _LEGACY_META_FIELDS:
        if val := _first_category(concept_eval, field):
            meta[meta_key] = val
    return meta


def _metadata(video_id: int, strategy: dict, enrich: dict | None, concept_eval: dict | None) -> dict:
    concept = _select_concept(strategy.get("m3") or {})
    meta: dict = {"video_id": video_id}
    meta["lens"] = _normalize_lens(concept.get("lens", ""))
    if claimtag := concept.get("claimtag"):
        meta["claimtag"] = claimtag
    for key in _ENRICH_KEYS:
        if enrich and (val := enrich.get(key)) is not None:
            meta[key] = val
    if concept_eval:
        meta.update(_legacy_metadata(concept_eval))
    return meta


def upsert_concept_reference(
    video_id: int,
    strategy: dict,
    db_path: str | Path = "output/vector_db",
    enrich: dict | None = None,
    concept_eval: dict | None = None,
) -> None:
    """strategy_analysis.json 1건을 ad_concept_reference 에 1레코드로 upsert 한다.

    enrich: 같은 영상의 creative_element_analysis.json profile 에서 뽑은
    {target_gender, duration_bucket, price_tier}(있는 것만) — 없으면 그 필드들은 비운다.
    concept_eval: 같은 영상의 concept_evaluation.json(구 스키마, 있으면) — 세그먼트 필터
    보조 카테고리 메타데이터만 뽑아 쓴다(문서 본문에는 반영하지 않음).
    """
    _collection(db_path).upsert(
        ids=[f"ad:{video_id}:concept"],
        documents=[_document(strategy)],
        metadatas=[_metadata(video_id, strategy, enrich, concept_eval)],
    )
    print(f"  [concept_reference_store] video_id={video_id}: concept 1건 upsert")


def fetch_concepts(where: dict | None = None, db_path: str | Path = "output/vector_db") -> list[dict]:
    """세그먼트에 속한 concept 레코드를 조회한다."""
    res = _collection(db_path).get(**({"where": where} if where else {}), include=["documents", "metadatas"])
    return [
        {"video_id": m.get("video_id"), "document": d, "metadata": m}
        for d, m in zip(res["documents"], res["metadatas"])
    ]
