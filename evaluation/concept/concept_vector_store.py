"""concept_evaluation.json 결과를 별도 ChromaDB 컬렉션(video_concept)에 적재하고 검색한다."""
from pathlib import Path

import chromadb

from evaluation.category.vector_store import _get_or_create, get_embedding_function  # noqa: F401 (get_embedding_function 은 하위 호환용 재노출)

_COLLECTION = "video_concept"

_DETAIL_FIELDS = (
    "target_persona", "usp", "positioning", "appeal_type",
    "perceived_value", "message_strategy", "execution_style",
)
_FIELD_LABELS: dict[str, str] = {
    "industry_category": "산업 카테고리",
    "product_category": "제품 카테고리",
    "target_persona": "타겟 페르소나",
    "usp": "USP",
    "positioning": "포지셔닝",
    "appeal_type": "소구 유형",
    "perceived_value": "지각 가치",
    "message_strategy": "메시지 전략",
    "execution_style": "연출 스타일",
}

# CM3 의 diverse_appeal/diverse_execution 렌즈가 카테고리별로 1건씩 표본 추출할 때 순회할 값 목록
# ("other" 는 창의적 다각화 신호로 쓸모가 적어 제외한다).
APPEAL_TYPE_CHOICES = (
    "humor", "parody_wordplay", "maternal_love", "vanity", "fear", "sex_appeal",
    "comparison", "rational_info", "emotional_storytelling", "testimonial",
    "scarcity_urgency", "nostalgia", "aspiration",
)
EXECUTION_STYLE_CHOICES = ("slice_of_life", "scientific_evidence", "fantasy", "fashion")


# ── 문서 / 메타데이터 빌더 ──────────────────────────────────────────────────────

def _build_document(concept: dict) -> str:
    """product_category·industry_category 는 값만, 나머지 7개 필드는 category·description·production_detail 을 함께 임베딩 문서에 담는다."""
    lines = []
    if concept.get("product_category"):
        lines.append(f"{_FIELD_LABELS['product_category']}: {concept['product_category']}")
    if industries := concept.get("industry_category"):
        lines.append(f"{_FIELD_LABELS['industry_category']}: {', '.join(industries)}")
    for field in _DETAIL_FIELDS:
        obj = concept.get(field) or {}
        category, description, detail = obj.get("category") or [], obj.get("description"), obj.get("production_detail")
        if not (category or description or detail):
            continue
        line = f"{_FIELD_LABELS[field]}"
        if category:
            line += f" [{', '.join(category)}]"
        if description:
            line += f": {description}"
        if detail:
            line += f" (연출: {detail})"
        lines.append(line)
    return "\n".join(lines)


def _build_metadata(video_id: int, concept: dict) -> dict:
    """industry_category·7개 필드는 category(대표값)만 exact-match 메타데이터로 저장한다."""
    meta: dict = {"video_id": video_id}
    if (val := concept.get("product_category")) is not None:
        meta["product_category"] = val
    if industries := concept.get("industry_category"):
        meta["industry_category"] = industries[0]
    for field in _DETAIL_FIELDS:
        category = (concept.get(field) or {}).get("category") or []
        if category:
            meta[field] = category[0]
    return meta


# ── 적재 ───────────────────────────────────────────────────────────────────────

def upsert_concept(
    video_id: int,
    concept: dict,
    db_path: str | Path = "output/vector_db",
    collection_name: str = _COLLECTION,
) -> None:
    """concept_evaluation 결과를 ChromaDB video_concept 컬렉션에 upsert 한다."""
    client = chromadb.PersistentClient(path=str(db_path))
    col = _get_or_create(client, collection_name)
    col.upsert(
        ids=[f"ad:{video_id}:concept"],
        documents=[_build_document(concept)],
        metadatas=[_build_metadata(video_id, concept)],
    )
    print(f"  [concept_vector_store] upsert 완료: ad:{video_id}:concept (collection={collection_name})")


# ── 쿼리 빌더 ─────────────────────────────────────────────────────────────────

def build_query_text(
    industry_category: str | None = None,
    product_category: str | None = None,
    target_persona: str | None = None,
    usp: str | None = None,
    positioning: str | None = None,
) -> str | None:
    """제공된 텍스트 필드를 합쳐 벡터 쿼리 문자열을 만든다."""
    kwargs = {
        "industry_category": industry_category,
        "product_category": product_category,
        "target_persona": target_persona,
        "usp": usp,
        "positioning": positioning,
    }
    lines = [f"{_FIELD_LABELS[f]}: {v}" for f, v in kwargs.items() if v]
    return "\n".join(lines) if lines else None


# ── 검색 ───────────────────────────────────────────────────────────────────────

def query_similar(
    text: str,
    n_results: int = 5,
    where: dict | None = None,
    db_path: str | Path = "output/vector_db",
    collection_name: str = _COLLECTION,
) -> list[dict]:
    """임베딩 유사도로 상위 n_results 를 반환한다 (전략/타겟 유사 렌즈용)."""
    client = chromadb.PersistentClient(path=str(db_path))
    col = _get_or_create(client, collection_name)
    kwargs: dict = {
        "query_texts": [text],
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


def sample_by_category(
    field: str,
    categories: tuple[str, ...],
    n_results: int = 5,
    db_path: str | Path = "output/vector_db",
    collection_name: str = _COLLECTION,
) -> list[dict]:
    """category 값(예: appeal_type)이 서로 다른 광고를 1건씩 표본 추출한다 (창의적 다각화 렌즈용).

    n_results 에 도달하거나 categories 를 모두 순회할 때까지 값이 다른 카테고리마다 1건씩 담는다.
    """
    client = chromadb.PersistentClient(path=str(db_path))
    col = _get_or_create(client, collection_name)
    rows: list[dict] = []
    for category in categories:
        if len(rows) >= n_results:
            break
        res = col.get(where={field: {"$eq": category}}, limit=1, include=["documents", "metadatas"])
        if res["documents"]:
            rows.append({"document": res["documents"][0], "metadata": res["metadatas"][0]})
    return rows
