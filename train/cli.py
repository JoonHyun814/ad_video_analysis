"""train_pipeline CLI 진입점.

사용법:
    # 데이터셋 빌드 (data_dir 여러 경로 가능)
    python -m train_pipeline.cli --build_dataset --data_dir output/ output2/ --out_dir data/

    # 학습
    python -m train_pipeline.cli --config configs/sample
"""

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Qwen VL 3 광고 분석 학습 파이프라인")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--build_dataset",
        action="store_true",
        help="data_dir 내 분석 결과를 학습용 JSONL 데이터셋으로 변환",
    )
    group.add_argument(
        "--config",
        type=Path,
        metavar="CONFIG",
        help="학습 설정 파일 경로 (.yaml 확장자 자동 추가)",
    )
    parser.add_argument(
        "--data_dir",
        type=Path,
        nargs="+",
        default=[Path("output")],
        metavar="DIR",
        help="분석 결과 루트 디렉토리 (video_id 하위 폴더 포함). 여러 경로 가능. 기본: output/",
    )
    parser.add_argument(
        "--out_dir",
        type=Path,
        required=True,
        metavar="DIR",
        help="빌드된 JSONL 저장 디렉토리 (필수)",
    )
    parser.add_argument(
        "--holdout_ratio",
        type=float,
        default=0.0,
        metavar="RATIO",
        help="0보다 크면 video_id 기준으로 이 비율만큼 홀드아웃(학습에서 제외)하고 매니페스트를 저장. 기본: 0 (홀드아웃 없음)",
    )
    parser.add_argument(
        "--holdout_seed",
        type=int,
        default=42,
        metavar="SEED",
        help="홀드아웃 샘플링 시드. 동일 seed·ratio·data_dir 이면 동일 결과 재현. 기본: 42",
    )
    parser.add_argument(
        "--holdout_out",
        type=Path,
        default=None,
        metavar="PATH",
        help="홀드아웃 video_id 매니페스트 저장 경로. 기본: <out_dir>/holdout_video_ids.json",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.build_dataset:
        from train_pipeline.dataset_builder import build_all

        exclude_ids = None
        if args.holdout_ratio > 0:
            from train_pipeline.holdout import list_video_ids, select_holdout, save_manifest

            video_ids = list_video_ids(args.data_dir)
            exclude_ids = select_holdout(video_ids, args.holdout_ratio, args.holdout_seed)
            manifest_path = args.holdout_out or (args.out_dir / "holdout_video_ids.json")
            save_manifest(exclude_ids, manifest_path, args.holdout_seed, args.holdout_ratio)
            print(f"홀드아웃 {len(exclude_ids)}개 video_id 제외 → {manifest_path}")

        counts = build_all(args.data_dir, args.out_dir, exclude_ids=exclude_ids)
        if not counts:
            print("빌드된 샘플 없음. data_dir 내 분석 결과를 확인하세요.", file=sys.stderr)
            sys.exit(1)
        total = sum(counts.values())
        print(f"\n총 {total}개 샘플 빌드 완료")

        if exclude_ids:
            eval_dir = args.out_dir / "eval"
            eval_counts = build_all(args.data_dir, eval_dir, include_only_ids=exclude_ids)
            eval_total = sum(eval_counts.values())
            print(f"홀드아웃 eval셋 {eval_total}개 샘플 빌드 완료 → {eval_dir} (trainer.py 의 *_eval 경로로 지정)")
    else:
        from train_pipeline.trainer import load_config, train
        cfg = load_config(args.config)
        train(cfg)


if __name__ == "__main__":
    main()
