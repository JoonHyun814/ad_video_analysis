from utils.env_loader import get_data_root
"""eval_plan.json 에 따라 전체 4개 도메인으로 VL 파이프라인을 실행.

python -m pikk_tagging.LLM.run_eval
python -m pikk_tagging.LLM.run_eval --eval_plan path/to/eval_plan.json --model_path D:/models/Qwen2.5-VL-7B-Instruct
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from analysis.pikk_tagging.LLM.model import QwenVLModel
from analysis.pikk_tagging.LLM.analyzer import analyze_video
from analysis.pikk_tagging.LLM.aggregator import compute_dominant_tags
from analysis.pikk_tagging.LLM.io import save_results

_DEFAULT_PLAN  = get_data_root() / "pikk_output\LLM\qwen_vl\eval_plan.json"
_DEFAULT_MODEL = Path(r"D:\models\Qwen2.5-VL-7B-Instruct")
_DEFAULT_OUT   = get_data_root() / "pikk_output\LLM\qwen_vl"
_ALL_DOMAINS   = ["angle", "shot_size", "lighting", "focus"]


def _print_video_summary(youtube_id: str, result: dict) -> None:
    dom = result.get("dominant_tags", {})
    ru  = result.get("resource_usage", {})
    tu  = result.get("tokens_used", {})
    print(f"  [{youtube_id}] frames={result.get('total_frames')}  {result.get('inference_time_sec')}s")
    print(f"    토큰={tu.get('total')}  GPU={ru.get('gpu_memory_peak_mb')}MB")
    print(f"    대표 태그: {dom}")


def main() -> None:
    p = argparse.ArgumentParser(description="eval_plan.json 기반 VL 파이프라인 일괄 실행")
    p.add_argument("--eval_plan",  default=str(_DEFAULT_PLAN),  help="eval_plan.json 경로")
    p.add_argument("--model_path", default=str(_DEFAULT_MODEL), help="Qwen VL 모델 경로")
    p.add_argument("--fps",        type=float, default=2.0,      help="초당 분석 프레임 수")
    p.add_argument("--out_dir",    default=str(_DEFAULT_OUT),    help="결과 저장 루트")
    p.add_argument("--domains",    default=",".join(_ALL_DOMAINS),
                   help=f"분석 도메인 (기본: {','.join(_ALL_DOMAINS)})")
    args = p.parse_args()

    plan_path = Path(args.eval_plan)
    if not plan_path.exists():
        sys.exit(f"eval_plan.json 없음: {plan_path}\n먼저 prepare_eval.py 를 실행하세요.")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    videos = plan.get("videos", [])
    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    out_dir = Path(args.out_dir)

    # 실행 가능한 영상 필터링
    runnable = [v for v in videos if v.get("video_path") and Path(v["video_path"]).exists()]
    skipped  = len(videos) - len(runnable)
    print(f"평가 계획: 총 {len(videos)}개 영상  (실행 가능: {len(runnable)}, 건너뜀: {skipped})")
    print(f"도메인: {domains}  fps={args.fps}")
    if skipped:
        print(f"  [건너뜀] 영상 파일 없음 — prepare_eval.py --skip_download=False 로 다운로드 필요")

    if not runnable:
        sys.exit("실행 가능한 영상 없음.")

    model = QwenVLModel(args.model_path)
    total_tokens = 0
    ok_count = 0

    for i, vid_info in enumerate(runnable, 1):
        youtube_id = vid_info["youtube_id"]
        video_path = Path(vid_info["video_path"])
        if (out_dir / youtube_id / "vl_results.json").exists():
            print(f"\n[{i}/{len(runnable)}] {youtube_id}  건너뜀 (이미 완료)")
            continue
        print(f"\n[{i}/{len(runnable)}] {youtube_id}  ({video_path.name})")

        result = analyze_video(video_path, model, domains, fps=args.fps)
        result["dominant_tags"] = compute_dominant_tags(result["frames"], domains)
        result["model"]         = model.model_name
        result["model_path"]    = model.model_path

        out_path = save_results(result, out_dir / youtube_id)
        print(f"  저장: {out_path}")
        _print_video_summary(youtube_id, result)

        total_tokens += result.get("tokens_used", {}).get("total", 0)
        ok_count += 1

    print(f"\n완료: {ok_count}/{len(runnable)}개  총 토큰={total_tokens:,}")
    print(f"뷰어: python -m pikk_tagging.LLM.viewer  →  http://localhost:5007")


if __name__ == "__main__":
    main()
