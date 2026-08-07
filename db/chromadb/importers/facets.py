"""concept_evaluation.json 을 facet 별 3개 컬렉션(ad_target/ad_usp/ad_creative)으로 분리 적재·검색한다.

세그먼트 축(타겟·USP)과 크리에이티브 축(소구·연출)을 별도 임베딩으로 나눠,
생성 파이프라인이 "타겟이 비슷한 광고"와 "연출이 비슷한 광고"를 구분해 조회하고
세그먼트 내 크리에이티브 분포(클리셰)를 분석할 수 있게 한다.
메타데이터는 3개 컬렉션에 동일하게 복제되어 어느 facet 에서든 exact 필터가 가능하다.

evaluation/concept/run.py(`--mode concept --load_facets`)가 upsert_facets 를, generation/의
segment_retrieval.py·cliche_report.py·g1_input_normalization.py·cli.py 가 fetch_members/
query_facet/GENRE_CHOICES 를 쓴다.
"""
from pathlib import Path

import chromadb

from db.chromadb.connection import DEFAULT_DB_PATH, get_client, get_or_create_collection

FACETS = ("target", "usp", "creative")
COLLECTIONS: dict[str, str] = {"target": "ad_target", "usp": "ad_usp", "creative": "ad_creative"}

# 광고 장르 — 광고주 입력과 DB 메타데이터가 공유하는 통제 enum. appeal_type 대표값에서 파생한다.
GENRE_CHOICES = ("humor", "emotional", "informational", "aspirational", "urgency", "other")
_APPEAL_TO_GENRE: dict[str, str] = {
    "humor": "humor", "parody_wordplay": "humor",
    "emotional_storytelling": "emotional", "maternal_love": "emotional", "nostalgia": "emotional",
    "rational_info": "informational", "comparison": "informational", "testimonial": "informational",
    "aspiration": "aspirational", "vanity": "aspirational", "sex_appeal": "aspirational",
    "fear": "urgency", "scarcity_urgency": "urgency",
}

_CREATIVE_FIELDS = ("appeal_type", "execution_style", "perceived_value", "message_strategy")
_META_CATEGORY_FIELDS = (
    "target_persona", "usp", "positioning",
    "appeal_type", "execution_style", "perceived_value", "message_strategy",
)
_LABELS: dict[str, str] = {
    "target_persona": "타겟 페르소나", "usp": "USP", "positioning": "포지셔닝",
    "appeal_type": "소구 유형", "execution_style": "연출 스타일",
    "perceived_value": "지각 가치", "message_strategy": "메시지 전략",
}


def derive_genre(appeal_categories: list[str]) -> str:
    """appeal_type category 배열의 대표값(첫 번째)을 광고 장르 enum 으로 매핑한다."""
    if not appeal_categories:
        return "other"
    return _APPEAL_TO_GENRE.get(appeal_categories[0], "other")


# ── 문서 / 메타데이터 빌더 ──────────────────────────────────────────────────────

def _field_line(concept: dict, field: str, with_detail: bool) -> str:
    """한 필드를 '라벨 [category]: description (연출: ...)' 형태의 문서 행으로 만든다."""
    obj = concept.get(field) or {}
    category, description = obj.get("category") or [], obj.get("description")
    detail = obj.get("production_detail") if with_detail else None
    if not (category or description or detail):
        return ""
    line = _LABELS[field]
    if category:
        line += f" [{', '.join(category)}]"
    if description:
        line += f": {description}"
    if detail:
        line += f" (연출: {detail})"
    return line


def build_facet_documents(concept: dict) -> dict[str, str]:
    """facet 별 임베딩 문서를 만든다. 값이 없는 facet 은 빈 문자열."""
    target = _field_line(concept, "target_persona", with_detail=False)
    usp_lines = [_field_line(concept, f, with_detail=False) for f in ("usp", "positioning")]
    creative_lines = [_field_line(concept, f, with_detail=True) for f in _CREATIVE_FIELDS]
    return {
        "target": target,
        "usp": "\n".join(line for line in usp_lines if line),
        "creative": "\n".join(line for line in creative_lines if line),
    }


def build_metadata(video_id: int, concept: dict) -> dict:
    """세그먼트 필터·분포 집계용 범주형 메타데이터 (3개 컬렉션 공통)."""
    meta: dict = {"video_id": video_id}
    if val := concept.get("product_category"):
        meta["product_category"] = val
    if industries := concept.get("industry_category"):
        meta["industry_category"] = industries[0]
    for field in _META_CATEGORY_FIELDS:
        category = (concept.get(field) or {}).get("category") or []
        if category:
            meta[field] = category[0]
    meta["genre"] = derive_genre((concept.get("appeal_type") or {}).get("category") or [])
    return meta


# ── 적재 ───────────────────────────────────────────────────────────────────────

def _facet_id(video_id: int, facet: str) -> str:
    return f"ad:{video_id}:{facet}"


def _collection(facet: str, db_path: str | Path) -> chromadb.Collection:
    client = get_client(db_path)
    return get_or_create_collection(client, COLLECTIONS[facet])


def upsert_facets(video_id: int, concept: dict, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """concept_evaluation 결과 1건을 3개 facet 컬렉션에 upsert 한다."""
    upsert_facet_batch([(video_id, concept)], db_path=db_path)


def upsert_facet_batch(
    records: list[tuple[int, dict]],
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """복수 concept_evaluation 결과를 facet 별로 모아 일괄 upsert 한다."""
    for facet in FACETS:
        ids, docs, metas = [], [], []
        for video_id, concept in records:
            doc = build_facet_documents(concept)[facet]
            if not doc:
                continue
            ids.append(_facet_id(video_id, facet))
            docs.append(doc)
            metas.append(build_metadata(video_id, concept))
        if not ids:
            continue
        _collection(facet, db_path).upsert(ids=ids, documents=docs, metadatas=metas)
        print(f"  [facets] {COLLECTIONS[facet]}: {len(ids)}건 upsert")


# ── 검색 ───────────────────────────────────────────────────────────────────────

def query_facet(
    facet: str,
    text: str,
    n_results: int = 10,
    where: dict | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """facet 컬렉션에서 임베딩 유사도 상위 n_results 를 반환한다."""
    col = _collection(facet, db_path)
    kwargs: dict = {
        "query_texts": [text],
        "n_results": min(n_results, col.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    res = col.query(**kwargs)
    return [
        {"video_id": m.get("video_id"), "document": d, "metadata": m, "distance": dist}
        for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


def fetch_members(
    facet: str,
    where: dict | None = None,
    video_ids: list[int] | None = None,
    include_embeddings: bool = False,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """facet 컬렉션 멤버를 필터/ID 로 조회한다 (세그먼트 분포 분석용)."""
    col = _collection(facet, db_path)
    include = ["documents", "metadatas"] + (["embeddings"] if include_embeddings else [])
    kwargs: dict = {"include": include}
    if where:
        kwargs["where"] = where
    if video_ids is not None:
        kwargs["ids"] = [_facet_id(v, facet) for v in video_ids]
    res = col.get(**kwargs)
    rows: list[dict] = []
    for i, id_ in enumerate(res["ids"]):
        row = {"id": id_, "video_id": res["metadatas"][i].get("video_id"),
               "document": res["documents"][i], "metadata": res["metadatas"][i]}
        if include_embeddings:
            row["embedding"] = list(res["embeddings"][i])
        rows.append(row)
    return rows
