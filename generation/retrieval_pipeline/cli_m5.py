"""retrieval_pipeline CLI — M5(장치별 벡터 DB 검색 실행, 결정적·LLM 아님).

M4(cli_m4.py)가 제안한 장치 후보·검색 쿼리를 db.chromadb.creative_search 로 그대로
실행한다(evaluation/ad_concept_production 이 적재한 ad_production_reference/ad_concept_reference
컬렉션, 각각 data/ad_production_reference/·data/ad_concept_reference/). M4 를 다시 태우지 않고
--top_k 만 바꿔 재검색하고 싶을 때 이 단계만 다시 돌리면 된다.

사용법:
    python -m generation.retrieval_pipeline.cli_m5 --input <run_dir>/m4.json [--top_k 3] [--db_path ...]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m5



def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M5 (장치별 벡터 DB 검색 실행)")
    p.add_argument("--input", type=Path, required=True, help="m4.json 경로(creative_problem/device_candidates 포함)")
    p.add_argument("--top_k", type=int, default=3, help="장치 1개당 검색해올 참조 광고 수(기본 3, 최대 20)")
    p.add_argument("--db_path", default=None,
                   help="ChromaDB 경로(미지정 시 concept/production 컬렉션이 각자 data/<collection>/ 자동 결정)")
    p.add_argument("--output_dir", type=Path, default=None, help="결과 저장 경로(기본: --input 과 같은 디렉터리)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))

    result = run_m5(data, top_k=args.top_k, db_path=args.db_path)

    output_dir = args.output_dir or args.input.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "m5.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()
