"""새 컨셉 파이프라인(CM1~CM4) 오케스트레이터 — 기존 M1~M7을 대체할 예정.

현재는 CM4(컨셉 5개 생성)까지만 구현됐다. CM5(4점 채점·선정)·CM6(최종 scenario_analysis 작성)는
아직 없으므로, 완성될 때까지 --pipeline(M1~M7)은 그대로 유지된다.
"""
import argparse

from generation.scenario_pipeline import llm_kwargs, load_json, save_json, stage_path
from utils.io_checks import is_parse_failed


def _require_stage_ok(result: dict, stage: str) -> None:
    """직전 단계 결과가 parse_failed 이면 다음 단계로 진행하지 않는다."""
    if is_parse_failed(result):
        raise SystemExit(
            f"[오류] {stage.upper()} 결과에 parse_failed 항목 있음.\n"
            f"  해당 단계를 재실행해 정상 결과를 만든 뒤 파이프라인을 다시 시도하세요."
        )


# ── 개별 모듈 실행 ────────────────────────────────────────────────────────────

def run_cm1(brief: dict, args: argparse.Namespace) -> dict:
    from generation.m1_category_insight import run
    print("  [CM1] 산업/제품 카테고리 분석 중...")
    result = run(brief, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "cm1"), result)
    return result


def run_cm2(brief: dict, cm1: dict, args: argparse.Namespace) -> dict:
    from generation.m2_target_positioning import run
    print("  [CM2] 타겟/USP/포지셔닝 수립 중...")
    result = run(brief, cm1, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "cm2"), result)
    return result


def run_cm3(cm1: dict, cm2: dict, args: argparse.Namespace) -> dict:
    from generation.m3_reference_collection import collect_references
    print("  [CM3] 참고 광고 수집 중 (4개 관점)...")
    result = collect_references(
        cm1, cm2,
        n_per_lens=args.concept_reference_n,
        db_path=args.vector_db_path,
        collection=args.concept_collection,
    )
    save_json(stage_path(args.output_dir, args.brand, args.product, "cm3"), result)
    return result


def run_cm4(brief: dict, cm1: dict, cm2: dict, cm3: dict, args: argparse.Namespace) -> dict:
    from generation.m4_concept_generation import run
    print("  [CM4] 컨셉 5개 생성 중...")
    result = run(brief, cm1, cm2, cm3, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "cm4"), result)
    return result


# ── 전체 파이프라인 ───────────────────────────────────────────────────────────

def run_concept_pipeline(args: argparse.Namespace, seed_brief: dict) -> None:
    """CM1→CM4 를 순차 실행한다."""
    cm1 = run_cm1(seed_brief, args)
    _require_stage_ok(cm1, "cm1")
    cm2 = run_cm2(seed_brief, cm1, args)
    _require_stage_ok(cm2, "cm2")
    cm3 = run_cm3(cm1, cm2, args)
    cm4 = run_cm4(seed_brief, cm1, cm2, cm3, args)
    _require_stage_ok(cm4, "cm4")
    print("\n  CM4까지 완료 — CM5(채점·선정)·CM6(최종 시나리오 작성)는 아직 구현되지 않았습니다.")


# ── 개별 스테이지 실행 ────────────────────────────────────────────────────────

def run_concept_single_stage(args: argparse.Namespace, brief: dict) -> None:
    """--stage cm1|cm2|cm3|cm4 로 지정된 단일 모듈만 실행한다."""
    od, b, p = args.output_dir, args.brand, args.product

    def _load(s: str) -> dict:
        return load_json(stage_path(od, b, p, s), s.upper())

    dispatch = {
        "cm1": lambda: run_cm1(brief, args),
        "cm2": lambda: run_cm2(brief, _load("cm1"), args),
        "cm3": lambda: run_cm3(_load("cm1"), _load("cm2"), args),
        "cm4": lambda: run_cm4(brief, _load("cm1"), _load("cm2"), _load("cm3"), args),
    }
    dispatch[args.stage]()
