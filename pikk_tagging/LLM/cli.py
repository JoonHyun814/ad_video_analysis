"""Qwen VL 기반 pikk 도메인 분류 파이프라인 CLI.

python -m pikk_tagging.LLM.cli --video path/to/video.mp4
python -m pikk_tagging.LLM.cli --video path/to/video.mp4 --target_domain angle,focus
python -m pikk_tagging.LLM.cli --video path/to/video.mp4 --target_domain angle,focus,shot_size,lighting
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from pikk_tagging.LLM.model import QwenVLModel
from pikk_tagging.LLM.analyzer import analyze_video
from pikk_tagging.LLM.aggregator import compute_dominant_tags
from pikk_tagging.LLM.io import save_results
from pikk_tagging.LLM.prompts import DOMAIN_LABELS

_DEFAULT_MODEL = Path(r"D:\models\Qwen2.5-VL-7B-Instruct")
_DEFAULT_OUT   = Path(r"C:\Users\llm\workspace\outputs\pikk_output\LLM\qwen_vl")
_ALL_DOMAINS   = list(DOMAIN_LABELS.keys())


def _print_summary(result: dict) -> None:
    dominant = result.get("dominant_tags", {})
    ru = result.get("resource_usage", {})
    tu = result.get("tokens_used", {})
    print(f"\n완료: {result.get('total_frames')}프레임 · {result.get('inference_time_sec')}s")
    print(f"  모델   : {result.get('model')}")
    print(f"  토큰   : 입력={tu.get('input')}  출력={tu.get('output')}  합계={tu.get('total')}")
    print(f"  GPU MEM: {ru.get('gpu_memory_peak_mb')}MB  GPU util={ru.get('gpu_util_avg')}%  CPU={ru.get('cpu_percent_avg')}%")
    print(f"  대표 태그: {dominant}")


def main() -> None:
    p = argparse.ArgumentParser(description="Qwen VL 기반 pikk 도메인 분류기")
    p.add_argument("--video",         required=True, help="입력 영상 경로")
    p.add_argument("--target_domain", default=",".join(_ALL_DOMAINS),
                   help=f"분석 도메인 콤마 구분 (기본: {','.join(_ALL_DOMAINS)})")
    p.add_argument("--fps",           type=float, default=2.0,
                   help="초당 분석 프레임 수 (기본 2)")
    p.add_argument("--model_path",    default=str(_DEFAULT_MODEL),
                   help="Qwen VL 모델 디렉토리 경로")
    p.add_argument("--out_dir",       default=str(_DEFAULT_OUT),
                   help="결과 저장 루트 디렉토리")
    args = p.parse_args()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"오류: 영상 파일 없음 — {video}")

    domains = [d.strip() for d in args.target_domain.split(",") if d.strip()]
    invalid = [d for d in domains if d not in DOMAIN_LABELS]
    if invalid:
        sys.exit(f"오류: 알 수 없는 도메인 — {invalid}\n가능한 도메인: {_ALL_DOMAINS}")

    model = QwenVLModel(args.model_path)

    print(f"분석 시작: {video.name}  fps={args.fps}  도메인={domains}")
    result = analyze_video(video, model, domains, fps=args.fps)

    result["dominant_tags"] = compute_dominant_tags(result["frames"], domains)
    result["model"]         = model.model_name
    result["model_path"]    = model.model_path

    out_path = save_results(result, Path(args.out_dir) / video.stem)
    print(f"저장: {out_path}")
    _print_summary(result)


if __name__ == "__main__":
    main()
