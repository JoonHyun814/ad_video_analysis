"""MLLM-VAU 재현 CLI.

  extract : 영상별 훅(첫 3초) 프레임 샘플링 → ASR → 음향 피처 → MLLM 기법(methodology/rationale) 추출
  topics  : 모든 영상의 rationale 을 BERTopic 으로 토픽화 → 토픽별 대표 키워드·영상별 대표 기법/피처 테이블
"""
import argparse
import os
from pathlib import Path

os.environ.setdefault("USE_TF", "0")  # transformers 가 TensorFlow 를 불러오지 않도록
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from hook_pipeline.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_OUTPUT_ROOT, HOOK_SEC
from hook_pipeline.mllm import LLM_BACKENDS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decoding the Hook (MLLM-VAU) 재현 파이프라인")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_extract_args(sub.add_parser("extract", help="영상별 훅 기법·음향 피처 추출"))
    _add_topics_args(sub.add_parser("topics", help="BERTopic 토픽화 + 대표값 선정"))
    return parser


def _add_video_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--video_id", type=int, default=None, help="video_uploads.id (단일)")
    p.add_argument("--video_ids", type=str, default=None, help="범위 (예: 1-10 / 1,3,5 / 1-5,7,9-12)")
    p.add_argument("--out_dir", type=Path, default=DEFAULT_OUTPUT_ROOT, help=f"결과 루트 (기본: {DEFAULT_OUTPUT_ROOT})")


def _add_extract_args(p: argparse.ArgumentParser) -> None:
    _add_video_args(p)
    p.add_argument("--video_path", type=Path, default=None, help="영상 파일 직접 지정 (DB 조회 생략)")
    p.add_argument("--llm_backend", choices=LLM_BACKENDS, default="claude", help="claude -p / codex exec (기본: claude)")
    p.add_argument("--llm_model", type=str, default=None, help="claude --model / codex -m 에 전달할 모델명")
    p.add_argument("--sampling", choices=("keyframe", "random"), default="keyframe", help="프레임 샘플링 전략 (기본: keyframe)")
    p.add_argument("--num_frames", type=int, default=8, help="[random] 샘플링 프레임 수 m (기본: 8)")
    p.add_argument("--alpha", type=float, default=0.5, help="[keyframe] τ = α·max(D) 의 α (기본: 0.5)")
    p.add_argument("--min_interval", type=int, default=8, help="[keyframe] 키프레임 간 최소 간격 Δt, 프레임 수 (기본: 8)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--hook_sec", type=float, default=HOOK_SEC, help=f"훅 구간 길이(초) (기본: {HOOK_SEC})")
    p.add_argument("--asr_model", type=str, default="medium", help="faster-whisper 모델 (기본: medium)")
    p.add_argument("--asr_language", type=str, default="ko", help="ASR 언어, 'auto' 면 자동 감지 (기본: ko)")


def _add_topics_args(p: argparse.ArgumentParser) -> None:
    _add_video_args(p)
    p.add_argument("--nr_topics", type=str, default="10,13,15,17,20",
                   help="perplexity 로 비교할 토픽 수 후보 (기본: 10,13,15,17,20)")
    p.add_argument("--min_cluster_size", type=int, default=10, help="HDBSCAN min_cluster_size (BERTopic 기본: 10)")
    p.add_argument("--embedding_model", type=str, default=DEFAULT_EMBEDDING_MODEL)
    p.add_argument("--seed", type=int, default=42)


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "extract":
        from hook_pipeline.cli_runners import run_extract_command

        run_extract_command(args)
    else:
        from hook_pipeline.cli_runners import run_topics_command

        run_topics_command(args)


if __name__ == "__main__":
    main()
