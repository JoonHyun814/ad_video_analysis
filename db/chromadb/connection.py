"""db/chromadb/ 전체가 공유하는 ChromaDB 클라이언트·컬렉션 연결 헬퍼 + 임베딩 함수.

EMBEDDING_MODEL/get_embedding_function 은 원래 evaluation/category/vector_store.py 가
소유했던 것을 여기로 흡수했다 — 이 저장소의 ChromaDB 접근은 이제 db/chromadb 하나로
통합되므로, 어떤 컬렉션을 적재/검색하든(video_category, category_analysis, scenario_analysis,
ad_concept_reference, ad_production_reference, ad_target/ad_usp/ad_creative) 이 한 곳의
임베딩 함수를 재사용한다.

저장 경로는 컬렉션명 하나로 통일한다 — 컬렉션마다 별도 물리 저장소를 두지 않고
`data/<collection>/` 에 1:1로 대응시킨다(`db_path_for`). 예전에는 `output/vector_db`
하나가 여러 컬렉션을 같이 담고 `data/category`처럼 컬렉션명과 다른 폴더명을 쓰기도
했는데, 폴더명만 보고 바로 컬렉션을 찾을 수 있도록 통일했다.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"

EMBEDDING_MODEL = "BAAI/bge-m3"  # 한/영 cross-lingual 임베딩

_ef_cache: embedding_functions.SentenceTransformerEmbeddingFunction | None = None


def get_embedding_function() -> embedding_functions.SentenceTransformerEmbeddingFunction:
    """프로세스 단위로 임베딩 모델을 1회만 로드한다."""
    global _ef_cache
    if _ef_cache is None:
        _ef_cache = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return _ef_cache


# ── 멀티모달(이미지) 임베딩 — db.chromadb.importers.keyframe_visual/visual_search 전용 ──
# clip-ViT-B-32(이미지)와 clip-ViT-B-32-multilingual-v1(텍스트, 한국어 포함)은 같은 임베딩
# 공간을 공유하는 sentence-transformers 공식 조합 — 새 라이브러리(open-clip 등) 없이 이미
# 설치된 sentence-transformers 만으로 텍스트→이미지 교차 검색이 가능하다.
_CLIP_TEXT_MODEL = "clip-ViT-B-32-multilingual-v1"
_CLIP_IMAGE_MODEL = "clip-ViT-B-32"

_clip_text_ef_cache: "_ClipTextEmbeddingFunction | None" = None
_clip_image_encoder_cache = None


class _ClipTextEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """ChromaDB 컬렉션에 등록해 query_texts 검색 시 자동으로 쓰이는 CLIP 텍스트 인코더.

    이미지 인코딩(clip-ViT-B-32)과 같은 임베딩 공간이라, 여기로 인코딩한 한국어/영어 쿼리가
    keyframe_visual 이 미리 계산해둔 이미지 벡터와 직접 비교된다.

    `chromadb.api.types.EmbeddingFunction`을 상속해야 한다 — `col.query()`는 `__call__`이
    아니라 `embed_query()`를 호출하는데, 이 메서드는 Protocol 기본 구현(`__call__`에 위임)이라
    실제로 상속하지 않으면(구조적 덕타이핑만으로는) 제공되지 않는다.
    """

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(_CLIP_TEXT_MODEL)

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._model.encode(list(input), convert_to_numpy=True).tolist()

    @staticmethod
    def name() -> str:
        return _CLIP_TEXT_MODEL


def get_clip_text_embedding_function() -> "_ClipTextEmbeddingFunction":
    """프로세스 단위로 CLIP 텍스트 인코더를 1회만 로드한다(검색 경로 전용)."""
    global _clip_text_ef_cache
    if _clip_text_ef_cache is None:
        _clip_text_ef_cache = _ClipTextEmbeddingFunction()
    return _clip_text_ef_cache


def get_clip_image_encoder():
    """프로세스 단위로 CLIP 이미지 인코더를 1회만 로드한다(적재 경로 전용 — `.encode(list[PIL.Image])`).

    ChromaDB 임베딩 함수 인터페이스를 따르지 않는 순수 sentence-transformers 모델 — 임포터가
    이미지를 미리 벡터로 변환해 `collection.upsert(embeddings=...)` 로 직접 넣기 때문에 컬렉션에
    등록할 필요가 없다.
    """
    global _clip_image_encoder_cache
    if _clip_image_encoder_cache is None:
        from sentence_transformers import SentenceTransformer
        _clip_image_encoder_cache = SentenceTransformer(_CLIP_IMAGE_MODEL)
    return _clip_image_encoder_cache


def db_path_for(collection: str) -> Path:
    """컬렉션명 → 저장 경로. `data/<collection>/` 하나로 통일한다."""
    return DATA_ROOT / collection


def get_client(db_path: Path | str) -> chromadb.ClientAPI:
    """db_path 의 PersistentClient 를 연다."""
    return chromadb.PersistentClient(path=str(db_path))


def get_collection(client: chromadb.ClientAPI, name: str, with_embeddings: bool = False):
    """컬렉션을 가져온다.

    존재하지 않는 이름이면 ChromaDB 예외를 그대로 올린다 — 오타로 빈 컬렉션이 새로
    생기는 걸 막기 위해 get_or_create_collection 대신 get_collection 만 쓴다.
    with_embeddings=True 는 자연어 유사도 검색(query_texts)에 필요한 임베딩 함수를 붙인다 —
    get()/count() 만 쓸 때는 필요 없다.
    """
    if with_embeddings:
        return client.get_collection(name, embedding_function=get_embedding_function())
    return client.get_collection(name)


def get_or_create_collection(client: chromadb.ClientAPI, name: str, embedding_function=None):
    """적재 스크립트 전용 — 컬렉션이 있으면 가져오고, 없으면 cosine 유사도로 새로 만든다.

    embedding_function 을 안 주면 get_embedding_function() 을 기본으로 쓴다(이 저장소의
    모든 컬렉션이 같은 bge-m3 를 쓰므로).

    get_or_create_collection(metadata=...) 를 그대로 쓰면 기존 데이터가 초기화되는
    ChromaDB 1.5.x 버그가 있어 get/create 두 단계로 나눈다. 조회 전용 스크립트는 오타로
    빈 컬렉션이 새로 생기지 않도록 `get_collection` 만 쓰고, 이 함수는 적재(import) 스크립트만 쓴다.
    """
    ef = embedding_function if embedding_function is not None else get_embedding_function()
    try:
        return client.get_collection(name, embedding_function=ef)
    except Exception:
        return client.create_collection(name, embedding_function=ef, metadata={"hnsw:space": "cosine"})
