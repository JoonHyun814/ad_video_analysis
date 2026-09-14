"""컬렉션 하나를 dense(bge-m3) 임베딩 검색 + BM25 키워드 검색으로 동시에 찾아 RRF로 결합한다."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from db.chromadb.connection import db_path_for, get_client, get_collection
from db.chromadb.search_query import search as _dense_search

_RRF_K_DEFAULT = 60
_CANDIDATE_MULTIPLIER = 4
_CANDIDATE_MIN = 20

# 컬렉션별 BM25 인덱스 캐시 — db_path 문자열 → (index, ids, metadatas, documents, built_count).
# col.count() 가 캐시된 built_count 와 다르면(적재 스크립트가 새로 돌았으면) 재구축한다.
_bm25_cache: dict[str, tuple[BM25Okapi, list[str], list[dict], list[str], int]] = {}

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """문자 bigram 토크나이저 — 형태소 분석기 없이도 한국어 조사 변형에 부분 매칭된다.

    영문 단어(공백 경계)는 그대로 두고, 각 단어를 소문자화한 연속 문자열에서 2-gram 을
    슬라이딩으로 뽑는다. 단어 길이가 1이면 단어 자체를 하나의 토큰으로 쓴다(bigram 불가능).
    """
    tokens: list[str] = []
    for word in _TOKEN_RE.findall(text.lower()):
        if len(word) < 2:
            tokens.append(word)
            continue
        tokens.extend(word[i:i + 2] for i in range(len(word) - 1))
    return tokens


def _build_bm25_index(collection_name: str, db_path: Path | str) -> tuple[BM25Okapi, list[str], list[dict], list[str], int]:
    client = get_client(db_path)
    col = get_collection(client, collection_name)
    count = col.count()
    if count == 0:
        return BM25Okapi([[""]]), [], [], [], 0
    raw = col.get(include=["documents", "metadatas"])
    ids, metadatas, documents = raw["ids"], raw["metadatas"], raw["documents"]
    corpus_tokens = [_tokenize(doc or "") for doc in documents]
    index = BM25Okapi(corpus_tokens)
    return index, ids, metadatas, documents, count


def _get_bm25_index(collection_name: str, db_path: Path | str) -> tuple[BM25Okapi, list[str], list[dict], list[str], int]:
    key = str(db_path)
    cached = _bm25_cache.get(key)
    if cached is not None:
        client = get_client(db_path)
        col = get_collection(client, collection_name)
        if col.count() == cached[4]:
            return cached
    built = _build_bm25_index(collection_name, db_path)
    _bm25_cache[key] = built
    return built


def hybrid_search(collection_name: str, query_text: str, n_results: int = 5,
                   db_path: Path | str | None = None, rrf_k: int = _RRF_K_DEFAULT) -> list[dict[str, Any]]:
    """dense 유사도 순위와 BM25 키워드 순위를 Reciprocal Rank Fusion 으로 결합해 상위 n_results 건을 반환한다.

    db_path 를 안 주면 `data/<collection_name>/` 를 쓴다. dense_rank/bm25_rank/rrf_score 를 함께
    반환해 어느 쪽 신호로 이 문서가 뽑혔는지 알 수 있게 한다(한쪽에만 걸리면 다른 쪽은 None).
    """
    resolved_path = db_path if db_path is not None else db_path_for(collection_name)
    candidate_n = max(n_results * _CANDIDATE_MULTIPLIER, _CANDIDATE_MIN)

    dense_hits = _dense_search(collection_name, query_text, candidate_n, resolved_path)
    dense_rank_by_id = {hit["id"]: i + 1 for i, hit in enumerate(dense_hits)}
    doc_by_id = {hit["id"]: (hit["metadata"], hit["document"]) for hit in dense_hits}

    bm25_index, ids, metadatas, documents, count = _get_bm25_index(collection_name, resolved_path)
    bm25_rank_by_id: dict[str, int] = {}
    if count > 0:
        scores = bm25_index.get_scores(_tokenize(query_text))
        ranked = sorted(range(len(ids)), key=lambda i: scores[i], reverse=True)[:candidate_n]
        bm25_rank_by_id = {ids[i]: rank + 1 for rank, i in enumerate(ranked)}
        for i in ranked:
            doc_by_id.setdefault(ids[i], (metadatas[i], documents[i]))

    all_ids = set(dense_rank_by_id) | set(bm25_rank_by_id)
    scored = []
    for doc_id in all_ids:
        d_rank = dense_rank_by_id.get(doc_id)
        b_rank = bm25_rank_by_id.get(doc_id)
        rrf_score = (1 / (rrf_k + d_rank) if d_rank else 0) + (1 / (rrf_k + b_rank) if b_rank else 0)
        scored.append((rrf_score, doc_id, d_rank, b_rank))
    scored.sort(key=lambda t: t[0], reverse=True)

    results = []
    for rrf_score, doc_id, d_rank, b_rank in scored[:n_results]:
        meta, doc = doc_by_id[doc_id]
        results.append({
            "id": doc_id, "metadata": meta, "document": doc,
            "rrf_score": round(rrf_score, 6), "dense_rank": d_rank, "bm25_rank": b_rank,
        })
    return results


def _print_results(results: list[dict]) -> None:
    if not results:
        print("검색 결과 없음.")
        return
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] id={r['id']}  rrf_score={r['rrf_score']:.5f}  "
              f"dense_rank={r['dense_rank']}  bm25_rank={r['bm25_rank']}")
        print("meta:", r["metadata"])
        print(f"     {r['document'][:300]}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션 하이브리드(dense+BM25) 유사도 검색")
    p.add_argument("--collection", required=True, help="검색할 컬렉션명")
    p.add_argument("--query", required=True, help="자연어 검색 쿼리")
    p.add_argument("--n_results", type=int, default=5, help="반환 결과 수 (기본: 5)")
    p.add_argument("--db_path", type=Path, default=None,
                   help="ChromaDB 저장 경로(미지정 시 data/<collection>/)")
    p.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON으로 출력")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    results = hybrid_search(args.collection, args.query, args.n_results, args.db_path)
    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _print_results(results)


if __name__ == "__main__":
    main()
