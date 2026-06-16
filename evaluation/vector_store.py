"""category_analysis.json 결과를 ChromaDB 벡터 DB에 적재하고 검색한다."""
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

_COLLECTION = "video_category"
EMBEDDING_MODEL = "BAAI/bge-m3"  # 한/영 cross-lingual 임베딩

_ef_cache: embedding_functions.SentenceTransformerEmbeddingFunction | None = None


def get_embedding_function() -> embedding_functions.SentenceTransformerEmbeddingFunction:
    """프로세스 단위로 임베딩 모델을 1회만 로드한다."""
    global _ef_cache
    if _ef_cache is None:
        _ef_cache = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
    return _ef_cache
# 벡터화할 필드: 앞 두 항목(industry_category, product_category)은 메타데이터에도 동시 저장
_TEXT_FIELDS = (
    "industry_category", "product_category",
    "product", "target_persona", "key_message", "usp", "positioning",
    "hook_strategy", "creative_style", "narrative_structure", "role_sequence", "key_scenes",
)
_META_FIELDS = (
    "industry_category", "product_category", "campaign_objective", "placement",
    "duration", "target_age_min", "target_age_max", "brand_name",
)
_FIELD_LABELS: dict[str, str] = {
    "industry_category": "산업 카테고리",
    "product_category": "제품 카테고리",
    "product": "제품",
    "target_persona": "타겟 페르소나",
    "key_message": "핵심 메시지",
    "usp": "USP",
    "positioning": "포지셔닝",
    "hook_strategy": "훅 전략",
    "creative_style": "크리에이티브 스타일",
    "narrative_structure": "서사 구조",
    "role_sequence": "역할 시퀀스",
    "key_scenes": "핵심 씬",
}


# ── 문서 / 메타데이터 빌더 ──────────────────────────────────────────────────────

def _build_document(category: dict) -> str:
    lines = [
        f"{_FIELD_LABELS.get(f, f)}: {category[f]}"
        for f in _TEXT_FIELDS
        if category.get(f)
    ]
    return "\n".join(lines)


def _build_metadata(video_id: int, category: dict) -> dict:
    meta: dict = {"video_id": video_id}
    for field in _META_FIELDS:
        val = category.get(field)
        if val is not None:
            meta[field] = val
    return meta


# ── ChromaDB 헬퍼 ──────────────────────────────────────────────────────────────

def _get_or_create(client, name: str) -> chromadb.Collection:
    """컬렉션이 있으면 그대로 가져오고, 없으면 cosine 유사도로 새로 생성한다.
    get_or_create_collection 에 metadata= 를 넘기면 기존 데이터가 초기화되는
    ChromaDB 1.5.x 버그를 피하기 위해 두 단계로 나눈다."""
    ef = get_embedding_function()
    try:
        return client.get_collection(name, embedding_function=ef)
    except Exception:
        return client.create_collection(
            name, embedding_function=ef, metadata={"hnsw:space": "cosine"}
        )


# ── 적재 ───────────────────────────────────────────────────────────────────────

def upsert_video(
    video_id: int,
    category: dict,
    db_path: str | Path = "output/vector_db",
    collection_name: str = _COLLECTION,
) -> None:
    """category_analysis 결과를 ChromaDB에 upsert 한다."""
    client = chromadb.PersistentClient(path=str(db_path))
    col = _get_or_create(client, collection_name)
    col.upsert(
        ids=[f"ad:{video_id}:category"],
        documents=[_build_document(category)],
        metadatas=[_build_metadata(video_id, category)],
    )
    print(f"  [vector_store] upsert 완료: ad:{video_id}:category (collection={collection_name})")


def upsert_batch(
    records: list[tuple[int, dict]],
    db_path: str | Path = "output/vector_db",
    collection_name: str = _COLLECTION,
) -> None:
    """복수 category_analysis 결과를 한 번에 upsert 한다."""
    client = chromadb.PersistentClient(path=str(db_path))
    col = _get_or_create(client, collection_name)
    ids = [f"ad:{vid}:category" for vid, _ in records]
    docs = [_build_document(cat) for _, cat in records]
    metas = [_build_metadata(vid, cat) for vid, cat in records]
    col.upsert(ids=ids, documents=docs, metadatas=metas)
    print(f"  [vector_store] {len(ids)}건 upsert 완료 (collection={collection_name})")


# ── 쿼리 빌더 ─────────────────────────────────────────────────────────────────

def build_query_text(
    industry_category: str | None = None,
    product_category: str | None = None,
    product: str | None = None,
    target_persona: str | None = None,
    key_message: str | None = None,
    usp: str | None = None,
    positioning: str | None = None,
    hook_strategy: str | None = None,
    creative_style: str | None = None,
    narrative_structure: str | None = None,
    role_sequence: str | None = None,
    key_scenes: str | None = None,
) -> str | None:
    """제공된 텍스트 필드를 합쳐 벡터 쿼리 문자열을 만든다."""
    kwargs = {
        "industry_category": industry_category,
        "product_category": product_category,
        "product": product,
        "target_persona": target_persona,
        "key_message": key_message,
        "usp": usp,
        "positioning": positioning,
        "hook_strategy": hook_strategy,
        "creative_style": creative_style,
        "narrative_structure": narrative_structure,
        "role_sequence": role_sequence,
        "key_scenes": key_scenes,
    }
    lines = [
        f"{_FIELD_LABELS.get(f, f)}: {v}"
        for f, v in kwargs.items()
        if v
    ]
    return "\n".join(lines) if lines else None


def build_where(
    industry_category: str | None = None,
    product_category: str | None = None,
    campaign_objective: str | None = None,
    placement: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    duration_max: float | None = None,
) -> dict | None:
    """메타데이터 exact/range 필터를 ChromaDB where 문법으로 변환한다."""
    conditions: list[dict] = []
    for field, val in (
        ("industry_category", industry_category),
        ("campaign_objective", campaign_objective),
        ("placement", placement),
    ):
        if val:
            conditions.append({field: {"$eq": val}})
    if product_category:
        conditions.append({"product_category": {"$eq": product_category}})
    if age_min is not None:
        conditions.append({"target_age_min": {"$gte": age_min}})
    if age_max is not None:
        conditions.append({"target_age_max": {"$lte": age_max}})
    if duration_max is not None:
        conditions.append({"duration": {"$lte": duration_max}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


# ── 검색 ───────────────────────────────────────────────────────────────────────

def query(
    # 벡터 유사도 텍스트 (optional)
    industry_category: str | None = None,
    product_category: str | None = None,
    product: str | None = None,
    target_persona: str | None = None,
    key_message: str | None = None,
    usp: str | None = None,
    positioning: str | None = None,
    hook_strategy: str | None = None,
    creative_style: str | None = None,
    narrative_structure: str | None = None,
    role_sequence: str | None = None,
    key_scenes: str | None = None,
    # 메타데이터 필터 (optional)
    filter_industry: str | None = None,
    filter_product_category: str | None = None,
    filter_campaign_objective: str | None = None,
    filter_placement: str | None = None,
    filter_age_min: int | None = None,
    filter_age_max: int | None = None,
    filter_duration_max: float | None = None,
    # 검색 제어
    text: str | None = None,
    n_results: int = 5,
    db_path: str | Path = "output/vector_db",
    collection_name: str = _COLLECTION,
) -> list[dict]:
    """필드별 인자로 유사도 검색한다.

    text 를 직접 넘기면 다른 텍스트 필드를 무시한다.
    filter_* 인자는 메타데이터 exact/range 필터로 적용된다.
    """
    query_text = text or build_query_text(
        industry_category=industry_category,
        product_category=product_category,
        product=product,
        target_persona=target_persona,
        key_message=key_message,
        usp=usp,
        positioning=positioning,
        hook_strategy=hook_strategy,
        creative_style=creative_style,
        narrative_structure=narrative_structure,
        role_sequence=role_sequence,
        key_scenes=key_scenes,
    )
    where = build_where(
        industry_category=filter_industry,
        product_category=filter_product_category,
        campaign_objective=filter_campaign_objective,
        placement=filter_placement,
        age_min=filter_age_min,
        age_max=filter_age_max,
        duration_max=filter_duration_max,
    )

    client = chromadb.PersistentClient(path=str(db_path))
    col = _get_or_create(client, collection_name)

    if not query_text:
        raise ValueError("검색할 텍스트 필드를 하나 이상 제공해야 한다.")

    kwargs: dict = {
        "query_texts": [query_text],
        "n_results": min(n_results, col.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    res = col.query(**kwargs)
    return [
        {"document": d, "metadata": m, "distance": dist}
        for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]
