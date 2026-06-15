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
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.build_dataset:
        from train_pipeline.dataset_builder import build_all
        counts = build_all(args.data_dir, args.out_dir)
        if not counts:
            print("빌드된 샘플 없음. data_dir 내 분석 결과를 확인하세요.", file=sys.stderr)
            sys.exit(1)
        total = sum(counts.values())
        print(f"\n총 {total}개 샘플 빌드 완료")
    else:
        from train_pipeline.trainer import load_config, train
        cfg = load_config(args.config)
        train(cfg)


if __name__ == "__main__":
    main()
