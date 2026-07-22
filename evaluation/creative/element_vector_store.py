"""creative_element_analysis.json 을 컬렉션 2개에 적재·조회한다.

- video_creative_profile: 영상 1개 = 1레코드. 세그먼트 검색용.
- ad_creative_element   : 크리에이티브 요소 1개 = 1레코드. 클리셰 빈도 집계용.
  요소 메타데이터에 profile 필터 키를 복제해 세그먼트 필터를 요소 단위로 직접 건다.
"""
from pathlib import Path

import chromadb

from evaluation.category.vector_store import _get_or_create
from evaluation.creative import element_schema as es

PROFILE_COLLECTION = "video_creative_profile"
ELEMENT_COLLECTION = "ad_creative_element"

# 요소 레코드에 복제되는 세그먼트 필터 키
_SEGMENT_KEYS = ("industry_category", "product_category_norm", "product_subtype",
                 "target_gender", "duration_bucket")
_CASTING_KEYS = ("main_model", "age_band", "skin_look", "hair", "wardrobe", "expression_restraint")


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


def _collection(name: str, db_path: str | Path) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(db_path))
    return _get_or_create(client, name)


# ── 문서 / 메타데이터 빌더 ──────────────────────────────────────────────────────

def _profile_metadata(video_id: int, analysis: dict) -> dict:
    profile, casting = analysis.get("profile") or {}, analysis.get("casting") or {}
    meta: dict = {"video_id": video_id}
    for key in (*_SEGMENT_KEYS, "product_category_raw", "duration_sec"):
        if (val := profile.get(key)) is not None:
            meta[key] = val
    for key in _CASTING_KEYS:
        if (val := casting.get(key)) is not None:
            if key == "expression_restraint" and not isinstance(val, bool):
                val = str(val).lower() == "true"  # 구버전 추출 결과의 "true"/"false" 문자열 흡수
            meta[key] = val
    for elem in analysis.get("elements") or []:
        if elem.get("element_type") == "narrative_pattern":
            meta["narrative_pattern"] = elem.get("element_subtype", "other")
            break
    return meta


def _profile_document(analysis: dict) -> str:
    profile = analysis.get("profile") or {}
    parts = [profile.get("product_category_raw", ""), profile.get("summary", "")]
    return "\n".join(p for p in parts if p)


def _element_document(elem: dict) -> str:
    doc = elem.get("description", "")
    if detail := elem.get("production_detail"):
        doc += f" (연출: {detail})"
    return doc


def _element_metadata(video_id: int, elem: dict, profile_meta: dict) -> dict:
    meta = {
        "video_id": video_id,
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
    db_path: str | Path = "output/vector_db",
) -> None:
    """분석 결과 1건을 profile 1레코드 + element N레코드로 upsert 한다 (v1 파일 흡수)."""
    analysis = _normalize_legacy(analysis)
    profile_meta = _profile_metadata(video_id, analysis)
    _collection(PROFILE_COLLECTION, db_path).upsert(
        ids=[f"ad:{video_id}:profile"],
        documents=[_profile_document(analysis)],
        metadatas=[profile_meta],
    )

    elements = analysis.get("elements") or []
    col = _collection(ELEMENT_COLLECTION, db_path)
    # 요소 개수가 줄어든 재적재에서 잔여 레코드가 남지 않도록 기존 요소를 먼저 지운다
    col.delete(where={"video_id": video_id})
    if elements:
        col.upsert(
            ids=[f"ad:{video_id}:elem:{i}" for i in range(len(elements))],
            documents=[_element_document(e) for e in elements],
            metadatas=[_element_metadata(video_id, e, profile_meta) for e in elements],
        )
    print(f"  [element_vector_store] video_id={video_id}: profile 1건 + element {len(elements)}건 upsert")


# ── 조회 ───────────────────────────────────────────────────────────────────────

def build_segment_where(
    industry_category: str | None = None,
    product_category_norm: str | None = None,
    product_subtype: str | None = None,
    target_gender: str | None = None,
    duration_bucket: str | None = None,
) -> dict | None:
    """세그먼트 필터를 ChromaDB where 문법으로 변환한다."""
    conditions = [
        {key: {"$eq": val}}
        for key, val in (
            ("industry_category", industry_category),
            ("product_category_norm", product_category_norm),
            ("product_subtype", product_subtype),
            ("target_gender", target_gender),
            ("duration_bucket", duration_bucket),
        )
        if val
    ]
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def fetch_profiles(where: dict | None = None, db_path: str | Path = "output/vector_db") -> list[dict]:
    """세그먼트에 속한 profile 레코드를 조회한다."""
    res = _collection(PROFILE_COLLECTION, db_path).get(
        **({"where": where} if where else {}), include=["documents", "metadatas"]
    )
    return [
        {"video_id": m.get("video_id"), "document": d, "metadata": m}
        for d, m in zip(res["documents"], res["metadatas"])
    ]


def fetch_elements(where: dict | None = None, db_path: str | Path = "output/vector_db") -> list[dict]:
    """세그먼트에 속한 요소 레코드를 조회한다 (클리셰 집계 입력)."""
    res = _collection(ELEMENT_COLLECTION, db_path).get(
        **({"where": where} if where else {}), include=["documents", "metadatas"]
    )
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
