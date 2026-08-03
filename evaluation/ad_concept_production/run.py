"""ad_concept_production 통합 파이프라인 CLI — scenario_analysis.json 1건을 concept+production
양쪽으로 추출해 ad_concept_reference/ad_production_reference 에 바로 적재한다."""
import argparse
import sys
from pathlib import Path

_LLM_BACKENDS = ("claude", "codex", "gemini")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="evaluation.cli --mode ad_concept_production",
        description="scenario_analysis.json → concept+production 추출 → ad_concept_reference/"
                    "ad_production_reference 적재(단일 통합 파이프라인)",
    )
    p.add_argument("--video_id", required=True, help="대상 영상 ID(쉼표 구분 복수 허용)")
    p.add_argument("--data_dir", type=Path, default=Path("output/total"),
                   help="데이터 루트(기본: output/total). 경로: <data_dir>/<video_id>/")
    p.add_argument("--db_path", type=Path, default=Path("output/vector_db"), help="ChromaDB 저장 경로")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드(기본: claude)")
    p.add_argument("--timeout", type=int, default=600, help="추출 1건당 LLM 호출 타임아웃 초(기본: 600)")
    p.add_argument("--force", action="store_true",
                   help="concept_analysis.json/production_analysis.json 이 이미 있어도 무시하고 재추출")
    return p


def main(argv: list[str] | None = None) -> None:
    from evaluation.ad_concept_production.pipeline import run_pipeline

    args = _build_parser().parse_args(argv)
    video_ids = [v.strip() for v in str(args.video_id).split(",") if v.strip()]

    failed = []
    for vid in video_ids:
        video_dir = args.data_dir / vid
        if not video_dir.exists():
            print(f"[오류] 데이터 디렉토리 없음: {video_dir}", file=sys.stderr)
            failed.append(vid)
            continue

        print(f"[ad_concept_production] video_id={vid}, backend={args.llm_backend}")
        result = run_pipeline(int(vid), video_dir, db_path=args.db_path,
                              backend=args.llm_backend, timeout=args.timeout, force=args.force)
        if result["concept_error"]:
            print(f"  [경고] concept 추출 실패: {result['concept_error']}", file=sys.stderr)
        if result["production_error"]:
            print(f"  [경고] production 추출 실패: {result['production_error']}", file=sys.stderr)
        if result["concept_error"] or result["production_error"]:
            failed.append(vid)
        else:
            print(f"  video_id={vid}: concept+production 적재 완료")

    print("완료." if not failed else f"완료 (실패: {failed}).")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
