"""ChromaDB 벡터 유사도 검색 CLI.

메타데이터 필터(exact/range)와 텍스트 유사도 검색을 조합한다.
"""
import argparse
import json
import sys
from pathlib import Path

# db/ 디렉토리 직접 실행 시 상위 패키지(evaluation 등)를 찾을 수 있도록 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

_DEFAULT_DB = Path(__file__).parent.parent / "output" / "vector_db"
_DEFAULT_COLLECTION = "video_category"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 광고 카테고리 유사도 검색")

    # 메타데이터 필터 (exact / range)
    f = p.add_argument_group("메타데이터 필터 (exact / range)")
    f.add_argument("--campaign_objective", help="캠페인 목적 (awareness | consideration | conversion)")
    f.add_argument("--placement", help="게재 지면 (예: ctv_15s, youtube_pre_roll_30s)")
    f.add_argument("--age_min", type=int, metavar="N", help="타겟 연령 하한 (target_age_min >= N)")
    f.add_argument("--age_max", type=int, metavar="N", help="타겟 연령 상한 (target_age_max <= N)")
    f.add_argument("--duration_max", type=float, metavar="SEC", help="영상 길이 상한 (duration <= SEC)")

    # 벡터 유사도 텍스트 입력
    t = p.add_argument_group("벡터 유사도 텍스트 (입력한 값을 합쳐 쿼리 생성)")
    t.add_argument("--industry_category", help="산업 카테고리 (예: beauty, healthcare, retail_ecommerce)")
    t.add_argument("--product_category", help="제품 카테고리 (예: 스킨케어, 음료, 쇼핑몰)")
    t.add_argument("--target_persona", help="타겟 페르소나 설명")
    t.add_argument("--key_message", help="핵심 메시지")
    t.add_argument("--usp", help="USP")
    t.add_argument("--positioning", help="포지셔닝")
    t.add_argument("--hook_strategy", help="훅 전략")
    t.add_argument("--creative_style", help="크리에이티브 스타일")
    t.add_argument("--narrative_structure", help="서사 구조")
    t.add_argument("--role_sequence", help="역할 시퀀스 (예: HOOK,FEATURE,CTA)")
    t.add_argument("--key_scenes", help="핵심 씬 설명")
    t.add_argument("--query", help="위 필드 대신 자유 텍스트 쿼리를 직접 입력")

    # 검색 제어
    p.add_argument("--n_results", type=int, default=5, help="반환 결과 수 (기본: 5)")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB)
    p.add_argument("--collection", default=_DEFAULT_COLLECTION)
    p.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON으로 출력")
    return p


def _build_python_filters(args: argparse.Namespace) -> list:
    """get() 결과를 Python에서 후처리할 필터 함수 리스트."""
    fns = []
    if args.campaign_objective:
        v = args.campaign_objective
        fns.append(lambda m, v=v: m.get("campaign_objective") == v)
    if args.placement:
        v = args.placement
        fns.append(lambda m, v=v: m.get("placement") == v)
    if args.age_min is not None:
        v = args.age_min
        fns.append(lambda m, v=v: (m.get("target_age_min") or 0) >= v)
    if args.age_max is not None:
        v = args.age_max
        fns.append(lambda m, v=v: (m.get("target_age_max") or 999) <= v)
    if args.duration_max is not None:
        v = args.duration_max
        fns.append(lambda m, v=v: (m.get("duration") or 999) <= v)
    return fns


def _print_results(results: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if not results:
        print("검색 결과 없음.")
        return
    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        dist = r.get("distance")
        score = f"  유사도 거리: {dist:.4f}" if dist is not None else ""
        print(f"\n[{i}] video_id={meta.get('video_id')}  brand={meta.get('brand_name', '-')}{score}")
        print(f"     산업: {meta.get('industry_category', '-')}  |  제품: {meta.get('product_category', '-')}")
        print(f"     목적: {meta.get('campaign_objective', '-')}  |  게재: {meta.get('placement', '-')}  |  길이: {meta.get('duration', '-')}s")
        print(f"     연령: {meta.get('target_age_min', '-')}~{meta.get('target_age_max', '-')}")
        print(f"     --- 문서 ---")
        print(f"     {r['document'][:300].replace(chr(10), chr(10) + '     ')}")


def main() -> None:
    import chromadb
    from evaluation.vector_store import build_query_text, build_where, _get_or_create

    args = _build_parser().parse_args()

    # 벡터 쿼리 텍스트 구성
    query_text = args.query or build_query_text(
        industry_category=args.industry_category,
        product_category=args.product_category,
        target_persona=args.target_persona,
        key_message=args.key_message,
        usp=args.usp,
        positioning=args.positioning,
        hook_strategy=args.hook_strategy,
        creative_style=args.creative_style,
        narrative_structure=args.narrative_structure,
        role_sequence=getattr(args, "role_sequence", None),
        key_scenes=getattr(args, "key_scenes", None),
    )

    # 메타데이터 where 필터 (벡터 검색 시 사용)
    where = build_where(
        campaign_objective=args.campaign_objective,
        placement=args.placement,
        age_min=args.age_min,
        age_max=args.age_max,
        duration_max=args.duration_max,
    )

    client = chromadb.PersistentClient(path=str(args.db_path))
    col = _get_or_create(client, args.collection)

    if col.count() == 0:
        print("[오류] 컬렉션이 비어 있습니다. 먼저 --load_vector 로 데이터를 적재하세요.", file=sys.stderr)
        sys.exit(1)

    if query_text:
        kwargs: dict = {
            "query_texts": [query_text],
            "n_results": min(args.n_results, col.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        raw = col.query(**kwargs)
        results = [
            {"metadata": m, "document": d, "distance": dist}
            for m, d, dist in zip(raw["metadatas"][0], raw["documents"][0], raw["distances"][0])
        ]
    else:
        # 텍스트 없음 → 전체 조회 후 Python 필터링
        raw_get = col.get(include=["documents", "metadatas"])
        filter_fns = _build_python_filters(args)
        results = [
            {"metadata": m, "document": d, "distance": None}
            for m, d in zip(raw_get["metadatas"], raw_get["documents"])
            if all(fn(m) for fn in filter_fns)
        ][: args.n_results]

    _print_results(results, args.as_json)


if __name__ == "__main__":
    main()
