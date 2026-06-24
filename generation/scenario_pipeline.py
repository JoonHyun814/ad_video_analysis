"""M1~M7 파이프라인 오케스트레이터 — 각 모듈 실행·저장·게이트 판정."""
import argparse
import json
import sys
from pathlib import Path

from generation.gates import check_gate_a, check_gate_b, check_gate_c
from utils.io_checks import is_parse_failed, require_valid_json


def stage_path(output_dir: Path, brand: str, product: str, stage: str, attempt: int = 1) -> Path:
    """attempt=1 은 기본 경로(`_m5.json`), 2 이상은 `_m5_<attempt>.json` 으로 분리 저장."""
    suffix = "" if attempt <= 1 else f"_{attempt}"
    return output_dir / f"{brand}_{product}_{stage}{suffix}.json"


def load_json(path: Path, label: str) -> dict:
    return require_valid_json(path, label)


def _require_stage_ok(result: dict, stage: str) -> None:
    """직전 단계 결과가 parse_failed 이면 다음 단계로 진행하지 않는다."""
    if is_parse_failed(result):
        raise SystemExit(
            f"[오류] {stage.upper()} 결과에 parse_failed 항목 있음.\n"
            f"  해당 단계를 재실행해 정상 결과를 만든 뒤 파이프라인을 다시 시도하세요."
        )


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


def llm_kwargs(args: argparse.Namespace) -> dict:
    return {"backend": args.llm_backend, "gemini_model": args.gemini_model, "codex_model": args.codex_model}


# ── 개별 모듈 실행 ────────────────────────────────────────────────────────────

def run_m1(brief: dict, args: argparse.Namespace) -> dict:
    from generation.m1_consumer_insight import run
    print("  [M1] 소비자 인사이트 추출 중...")
    result = run(brief, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "m1"), result)
    return result


def run_m2(brief: dict, m1: dict, args: argparse.Namespace) -> dict:
    from generation.m2_positioning import run
    print("  [M2] 포지셔닝 전략 수립 중...")
    result = run(brief, m1, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "m2"), result)
    return result


def run_m3(brief: dict, m1: dict, m2: dict, args: argparse.Namespace) -> dict:
    from generation.m3_concept_divergence import run
    from generation.vector_reference import maybe_reference_ads
    refs = maybe_reference_ads(args, brief, m2)
    print("  [M3] 컨셉 발산 중 (5~8개)...")
    result = run(brief, m1, m2, reference_ads=refs, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "m3"), result)
    return result


def run_m4(m3: dict, args: argparse.Namespace) -> dict:
    from generation.m4_concept_kill import run
    from generation.vector_reference import enforce_similarity_kill, maybe_similarity_info
    sim_info, threshold = maybe_similarity_info(args, m3)
    print("  [M4] 컨셉 비평·킬 중...")
    result = run(m3, similarity_info=sim_info, similarity_threshold=threshold, **llm_kwargs(args))
    result = enforce_similarity_kill(result, sim_info, threshold)
    save_json(stage_path(args.output_dir, args.brand, args.product, "m4"), result)
    return result


def run_m5(
    brief: dict, m3: dict, m4: dict, args: argparse.Namespace,
    *, m6_feedback: dict | None = None, attempt: int = 1,
) -> dict:
    from generation.m5_dr_script import run
    from generation.vector_reference import maybe_narrative_references
    refs = maybe_narrative_references(args, m3, m4)
    label = "재작성" if m6_feedback else "생성"
    print(f"  [M5] DR 스크립트 {label} 중 (attempt={attempt})...")
    result = run(brief, m3, m4, narrative_references=refs, m6_feedback=m6_feedback, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "m5", attempt), result)
    return result


def run_m6(brief: dict, m5: dict, args: argparse.Namespace, *, attempt: int = 1) -> dict:
    from generation.m6_red_team import run
    print(f"  [M6] 레드팀 프리모템 중 (attempt={attempt})...")
    result = run(brief, m5, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "m6", attempt), result)
    return result


def run_m7(m5: dict, m6: dict, brief: dict, args: argparse.Namespace) -> dict:
    from generation.m7_validation import run
    print("  [M7] 합성 사전스크린 + 인간 게이트 검증 중...")
    result = run(m5, m6, brief, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "m7"), result)
    return result


# ── 브리프 생성 ───────────────────────────────────────────────────────────────

def run_brief(args: argparse.Namespace) -> dict:
    """웹 검색으로 브리프를 생성하고 저장한다."""
    from generation.brief_generator import generate_brief_from_web
    print("  [BRIEF] 웹 검색 + 브리프 생성 중...")
    brief = generate_brief_from_web(
        args.brand, args.product,
        usp=args.usp, target_age=args.target_age, target_persona=args.target_persona,
        positioning=args.positioning, slogan=args.slogan,
        ingredients=args.ingredients, functions=args.functions,
        llm_backend=args.llm_backend, codex_model=args.codex_model,
        gemini_model=args.gemini_model,
    )
    if "error" in brief:
        print(f"  [경고] 브리프 생성 실패: {brief.get('error')}", file=sys.stderr)
    save_json(args.output_dir / f"{args.brand}_{args.product}.json", brief)
    return brief


# ── 전체 파이프라인 ───────────────────────────────────────────────────────────

def run_pipeline(args: argparse.Namespace, seed_brief: dict) -> None:
    """M1→M4→(웹 검색 브리프)→M5→M7 전체 파이프라인을 순차 실행한다."""
    m1 = run_m1(seed_brief, args)
    _require_stage_ok(m1, "m1")
    m2 = run_m2(seed_brief, m1, args)
    _require_stage_ok(m2, "m2")
    m3 = run_m3(seed_brief, m1, m2, args)
    _require_stage_ok(m3, "m3")
    m4 = run_m4(m3, args)
    _require_stage_ok(m4, "m4")
    if not check_gate_a(m4):
        return

    # GATE A 통과 후 웹 검색으로 브리프 보강 (선정 컨셉 맥락 반영)
    brief = run_brief(args)
    _require_stage_ok(brief, "brief")

    m5 = run_m5(brief, m3, m4, args)
    _require_stage_ok(m5, "m5")
    m6 = run_m6(brief, m5, args)
    _require_stage_ok(m6, "m6")
    from generation.m6_retry import auto_retry
    m4, m5, m6 = auto_retry(
        brief, m3, m4, m5, m6, args,
        run_m5=run_m5, run_m6=run_m6,
        save_m4=lambda data, n: save_json(stage_path(args.output_dir, args.brand, args.product, "m4", n), data),
    )
    if not check_gate_b(m6):
        return

    m7 = run_m7(m5, m6, brief, args)
    _require_stage_ok(m7, "m7")
    if check_gate_c(m7):
        print("\n  [GATE C] Go — 캠페인 진행 승인.")


# ── 개별 스테이지 실행 ────────────────────────────────────────────────────────

def run_single_stage(args: argparse.Namespace, brief: dict) -> None:
    """--stage로 지정된 단일 모듈만 실행한다."""
    od, b, p = args.output_dir, args.brand, args.product

    def _load(s: str) -> dict:
        return load_json(stage_path(od, b, p, s), s.upper())

    dispatch = {
        "m1": lambda: run_m1(brief, args),
        "m2": lambda: run_m2(brief, _load("m1"), args),
        "m3": lambda: run_m3(brief, _load("m1"), _load("m2"), args),
        "m4": lambda: run_m4(_load("m3"), args),
        "m5": lambda: run_m5(brief, _load("m3"), _load("m4"), args),
        "m6": lambda: run_m6(brief, _load("m5"), args),
        "m7": lambda: run_m7(_load("m5"), _load("m6"), brief, args),
    }
    dispatch[args.stage]()
