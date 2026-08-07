"""creative_element_analysis.json 을 ad_production_reference 컬렉션 1개에 적재·조회한다.

컨셉 확정 후 M5(스크립트)~M9(콘티)·스토리보드 HTML 이 참고하는 "연출/프로덕션 디테일"
전용 컬렉션이다(전략 단계 M3 참고용 ad_concept_reference 는 db/chromadb/importers/
concept_reference.py 가 별도로 관리한다).

record_kind 메타데이터로 레코드 2종을 한 컬렉션에 함께 둔다:
- record_kind="profile": 영상 1개 = 1레코드. 세그먼트 검색용(캐스팅·서사패턴·연출 스타일 포함).
- record_kind="element" : 크리에이티브 요소 1개 = 1레코드. 클리셰 빈도 집계·연출 기법 검색용.
  요소 메타데이터에 profile 필터 키를 복제해 세그먼트 필터를 요소 단위로 직접 건다.

evaluation/creative/run.py(`--mode creative --load_vector`)와 evaluation/ad_concept_production/
pipeline.py 가 upsert_analysis 를, db/chromadb/creative_search.py 가 fetch_profiles/
fetch_elements 를 쓴다.
"""
from pathlib import Path

import chromadb

from db.chromadb.connection import DEFAULT_DB_PATH, get_client, get_or_create_collection
from evaluation.creative import element_schema as es

PRODUCTION_COLLECTION = "ad_production_reference"

# 요소 레코드에 복제되는 세그먼트 필터 키
_SEGMENT_KEYS = ("industry_category", "industry_secondary", "product_category_norm", "product_subtype",
                 "target_gender", "duration_bucket",
                 "usp_category", "positioning_category", "price_tier")
_CASTING_KEYS = ("main_model", "age_band", "skin_look", "hair", "wardrobe", "expression_restraint")
# 영상당 1개인 SINGLE_TYPES 요소 중, profile 메타데이터로도 승격해 세그먼트 필터·클리셰
# 캐스팅 집계(cliche_aggregate._aggregate_casting)에서 바로 걸 수 있게 하는 것들.
_PROMOTED_ELEMENT_TYPES = ("narrative_pattern", "persuasion_engine", "narrative_form", "tone_register")


def _normalize_legacy(analysis: dict) -> dict:
    """v1 분석 파일의 type/subtype/카테고리 명칭을 v2 로 흡수한다."""
    profile = analysis.get("profile") or {}
    if pcn := profile.get("product_category_norm"):
        profile["product_category_norm"] = es.LEGACY_CATEGORY_MAP.get(pcn, pcn)
    if not profile.get("industry_category"):
        profile["industry_category"] = es.infer_industry(profile.get("product_category_norm"))
    for elem in analysis.get("elements") or []:
        etype = elem.get("element_type", "")
        elem["element_type"] = es.LEGACY_TYPE_MAP.get(etype, etype)
        sub = elem.get("element_subtype", "")
        elem["element_subtype"] = es.LEGACY_SUBTYPE_MAP.get(sub, sub)
    return analysis


def _collection(db_path: str | Path) -> chromadb.Collection:
    client = get_client(db_path)
    return get_or_create_collection(client, PRODUCTION_COLLECTION)


def _with_kind(where: dict | None, record_kind: str) -> dict:
    """호출측 where 에 record_kind 조건을 합친다(단일 조건이면 $and 로 감싸지 않는다)."""
    cond = {"record_kind": {"$eq": record_kind}}
    if not where:
        return cond
    return {"$and": [cond, where]}


# ── 문서 / 메타데이터 빌더 ──────────────────────────────────────────────────────

def _profile_metadata(video_id: int, analysis: dict) -> dict:
    profile, casting = analysis.get("profile") or {}, analysis.get("casting") or {}
    meta: dict = {"video_id": video_id, "record_kind": "profile"}
    for key in (*_SEGMENT_KEYS, "product_category_raw", "duration_sec", "execution_style"):
        if (val := profile.get(key)) is not None:
            meta[key] = val
    for key in _CASTING_KEYS:
        if (val := casting.get(key)) is not None:
            if key == "expression_restraint" and not isinstance(val, bool):
                val = str(val).lower() == "true"  # 구버전 추출 결과의 "true"/"false" 문자열 흡수
            meta[key] = val
    for elem in analysis.get("elements") or []:
        etype = elem.get("element_type")
        if etype in _PROMOTED_ELEMENT_TYPES:
            meta[etype] = elem.get("element_subtype", "other")
    return meta


def _profile_document(analysis: dict) -> str:
    profile = analysis.get("profile") or {}
    parts = [profile.get("product_category_raw", ""), profile.get("summary", ""),
             profile.get("usp_summary", "")]
    return "\n".join(p for p in parts if p)


def _element_document(elem: dict) -> str:
    doc = elem.get("description", "")
    if detail := elem.get("production_detail"):
        doc += f" (연출: {detail})"
    return doc


def _element_metadata(video_id: int, elem: dict, profile_meta: dict) -> dict:
    meta = {
        "video_id": video_id,
        "record_kind": "element",
        "element_type": elem.get("element_type", "other"),
        "element_subtype": elem.get("element_subtype", "other"),
        "cut_refs": ",".join(str(c) for c in elem.get("cut_refs") or []),
    }
    for key in _SEGMENT_KEYS:
        if (val := profile_meta.get(key)) is not None:
            meta[key] = val
    return meta


# ── 적재 ───────────────────────────────────────────────────────────────────────

def upsert_analysis(
    video_id: int,
    analysis: dict,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """분석 결과 1건을 profile 1레코드 + element N레코드로 upsert 한다 (v1 파일 흡수)."""
    analysis = _normalize_legacy(analysis)
    profile_meta = _profile_metadata(video_id, analysis)
    col = _collection(db_path)
    col.upsert(
        ids=[f"ad:{video_id}:profile"],
        documents=[_profile_document(analysis)],
        metadatas=[profile_meta],
    )

    elements = analysis.get("elements") or []
    # 요소 개수가 줄어든 재적재에서 잔여 레코드가 남지 않도록 기존 요소만 지운다
    # (record_kind="element" 로 좁히지 않으면 방금 올린 profile 레코드까지 지워진다).
    col.delete(where={"$and": [{"video_id": {"$eq": video_id}}, {"record_kind": {"$eq": "element"}}]})
    if elements:
        col.upsert(
            ids=[f"ad:{video_id}:elem:{i}" for i in range(len(elements))],
            documents=[_element_document(e) for e in elements],
            metadatas=[_element_metadata(video_id, e, profile_meta) for e in elements],
        )
    print(f"  [production_reference] video_id={video_id}: profile 1건 + element {len(elements)}건 upsert")


# ── 조회 ───────────────────────────────────────────────────────────────────────

def build_segment_where(
    industry_category: str | None = None,
    product_category_norm: str | None = None,
    product_subtype: str | None = None,
    target_gender: str | None = None,
    duration_bucket: str | None = None,
    usp_category: str | None = None,
    positioning_category: str | None = None,
    price_tier: str | None = None,
) -> dict | None:
    """세그먼트 필터를 ChromaDB where 문법으로 변환한다.

    industry_category 는 주산업(industry_category)·부산업(industry_secondary) 중
    어느 쪽으로 걸려도 매칭한다 (다트비트처럼 tech_electronics+entertainment 복합
    산업 광고가 두 세그먼트 리포트 모두에 잡히도록).
    """
    conditions = []
    if industry_category:
        conditions.append({"$or": [
            {"industry_category": {"$eq": industry_category}},
            {"industry_secondary": {"$eq": industry_category}},
        ]})
    conditions += [
        {key: {"$eq": val}}
        for key, val in (
            ("product_category_norm", product_category_norm),
            ("product_subtype", product_subtype),
            ("target_gender", target_gender),
            ("duration_bucket", duration_bucket),
            ("usp_category", usp_category),
            ("positioning_category", positioning_category),
            ("price_tier", price_tier),
        )
        if val
    ]
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def fetch_profiles(where: dict | None = None, db_path: str | Path = DEFAULT_DB_PATH) -> list[dict]:
    """세그먼트에 속한 profile 레코드를 조회한다."""
    res = _collection(db_path).get(where=_with_kind(where, "profile"), include=["documents", "metadatas"])
    return [
        {"video_id": m.get("video_id"), "document": d, "metadata": m}
        for d, m in zip(res["documents"], res["metadatas"])
    ]


def fetch_elements(where: dict | None = None, db_path: str | Path = DEFAULT_DB_PATH) -> list[dict]:
    """세그먼트에 속한 요소 레코드를 조회한다 (클리셰 집계 입력)."""
    res = _collection(db_path).get(where=_with_kind(where, "element"), include=["documents", "metadatas"])
    return [
        {
            "video_id": m.get("video_id"),
            "element_type": m.get("element_type"),
            "element_subtype": m.get("element_subtype"),
            "cut_refs": m.get("cut_refs", ""),
            "document": d,
        }
        for d, m in zip(res["documents"], res["metadatas"])
    ]
