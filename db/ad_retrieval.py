"""ad_production_reference(creative vector db)에서 지정 기준으로 유사 광고를 추출한다.

scenario_analysis.json 이나 video_category(category DB)는 참조하지 않는다 — 이미
creative 요소가 적재된 영상만 검색 대상이 된다 (커버리지는 그만큼 제한적일 수 있음).
"""
from pathlib import Path

import chromadb

from evaluation.category.vector_store import _get_or_create
from evaluation.creative.element_vector_store import PRODUCTION_COLLECTION

_DEFAULT_DB = Path("output/vector_db")
_OVERSAMPLE = 60


def retrieve_similar_ads(
    query_text: str,
    duration_bucket: str = "15s",
    n_results: int = 15,
    db_path: str | Path = _DEFAULT_DB,
    oversample: int = _OVERSAMPLE,
) -> list[dict]:
    """query_text 유사도 순으로 duration_bucket 광고를 creative vector db 에서 최대 n_results건 추출한다.

    ad_production_reference 는 record_kind="profile" 이 영상 1개 = 1레코드라 video_id 자체로
    이미 중복이 없다(record_kind="element" 레코드는 이 필터로 제외된다).
    """
    client = chromadb.PersistentClient(path=str(db_path))
    col = _get_or_create(client, PRODUCTION_COLLECTION)
    if col.count() == 0:
        return []
    res = col.query(
        query_texts=[query_text],
        n_results=min(oversample, col.count()),
        where={"$and": [{"duration_bucket": {"$eq": duration_bucket}}, {"record_kind": {"$eq": "profile"}}]},
        include=["documents", "metadatas", "distances"],
    )
    picked: list[dict] = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        picked.append({
            "video_id": meta.get("video_id"),
            "distance": round(dist, 4),
            "industry": meta.get("industry_category"),
            "product_category": meta.get("product_category_norm"),
            "product_category_raw": meta.get("product_category_raw"),
            "document": doc,
        })
        if len(picked) >= n_results:
            break
    return picked
