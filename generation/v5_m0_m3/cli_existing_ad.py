"""v5_m0_m3 CLI — 기존 방영 광고 분석(`data/ad_concept_production/<video_id>/`)을 재료로
M0(URL 크롤) 없이 M0~M3 산출물 또는 M4~M9 대체 산출물을 만든다.

사용법:
    python -m generation.v5_m0_m3.cli_existing_ad --video_id 86 --mode m3 \\
        [--llm_backend api] [--output_dir output/v5_m0_m3]
    python -m generation.v5_m0_m3.cli_existing_ad --video_id 86 --mode direct \\
        [--llm_backend api] [--output_dir output/v5_m0_m3]

--mode m3     : module0/m1/m2/m3 조립(LLM 미호출). cli_m4_m9.py 입력용
                (existing_<video_id>_m0_m3.json).
--mode direct : {m4,m5,m9} 1회 LLM 호출로 조립(M4~M9 재생성 없음). cli_storyboard.py
                입력용(existing_<video_id>_direct_m4_m9.json) — "바로 생성" 비교군.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.v5_m0_m3 import existing_ad_adapter, llm_adapter


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="기존 방영 광고 분석에서 v5_m0_m3 M0~M3 또는 직접-변환 M4~M9 산출물을 만든다"
    )
    p.add_argument("--video_id", required=True, type=int, help="data/ad_concept_production/<video_id>/")
    p.add_argument("--mode", required=True, choices=("m3", "direct"))
    p.add_argument("--data_root", type=Path, default=Path("data/ad_concept_production"))
    p.add_argument("--llm_backend", default="api", choices=("cli", "api"),
                   help="--mode direct 에서만 사용(기본 api — 반복 배치 호출에 더 안정적)")
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3"))
    return p


def main() -> None:
    args = _build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "m3":
        result = existing_ad_adapter.build_m0_m3(args.video_id, data_root=args.data_root)
        out_path = args.output_dir / f"existing_{args.video_id}_m0_m3.json"
    else:
        llm_adapter.set_backend(args.llm_backend)
        result = existing_ad_adapter.build_direct_creative(args.video_id, data_root=args.data_root)
        out_path = args.output_dir / f"existing_{args.video_id}_direct_m4_m9.json"

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()
