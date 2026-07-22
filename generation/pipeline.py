"""G1~G6 클리셰 인지 생성 파이프라인 오케스트레이터 — 각 단계 실행·저장·컨셉 선정.

G1 입력 정규화 → G2 세그먼트+클리셰 리포트 → G3 클리셰 결정 → G4 컨셉 5개 생성
→ G5 임베딩 거리 검증 → G6 시나리오 작성(scenario_analysis 스키마).
G2·G5 는 LLM 없이 벡터 DB 통계만 사용한다.
"""
import argparse
import json
from pathlib import Path

from utils.io_checks import is_parse_failed, require_valid_json

STAGES = ("g1", "g2", "g3", "g4", "g5", "g6")


def stage_path(output_dir: Path, brand: str, product: str, stage: str) -> Path:
    return output_dir / f"{brand}_{product}_{stage}.json"


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


def load_json(path: Path, label: str) -> dict:
    return require_valid_json(path, label)


def llm_kwargs(args: argparse.Namespace) -> dict:
    return {"backend": args.llm_backend, "gemini_model": args.gemini_model, "codex_model": args.codex_model}


def _require_stage_ok(result: dict, stage: str) -> None:
    """직전 단계 결과가 parse_failed 이면 다음 단계로 진행하지 않는다."""
    if is_parse_failed(result):
        raise SystemExit(
            f"[오류] {stage.upper()} 결과에 parse_failed 항목 있음.\n"
            f"  해당 단계를 재실행해 정상 결과를 만든 뒤 파이프라인을 다시 시도하세요."
        )


def _advertiser_inputs(args: argparse.Namespace) -> dict:
    """CLI 로 받은 광고주 지정값 (빈 값은 G1 이 브리프에서 추론)."""
    return {
        "genre": args.genre,
        "target_persona": args.target_persona,
        "usp": args.usp,
        "positioning": args.positioning,
        "brand_position": args.brand_position,
    }


# ── 개별 단계 실행 ────────────────────────────────────────────────────────────

def run_g1(brief: dict, args: argparse.Namespace) -> dict:
    from generation.g1_input_normalization import run
    print("  [G1] 광고주 입력 정규화 중...")
    result = run(brief, _advertiser_inputs(args), **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "g1"), result)
    return result


def run_g2(g1: dict, args: argparse.Namespace) -> dict:
    from generation.cliche_report import build_report
    from generation.segment_retrieval import retrieve_segment
    print("  [G2] 세그먼트 추출 + 클리셰 리포트 생성 중...")
    segment = retrieve_segment(
        genre=g1.get("genre", ""), industry=g1.get("industry_category", ""),
        target_text=g1.get("target_persona", ""), usp_text=g1.get("usp", ""),
        min_n=args.min_segment, cap=args.segment_cap, db_path=args.vector_db_path,
    )
    print(f"      세그먼트: {segment['n_members']}건 (완화={segment['relax_level']})")
    report = build_report(segment, code_share=args.code_share, cliche_share=args.cliche_share,
                          seed=args.cluster_seed, db_path=args.vector_db_path)
    result = {"segment": segment, "report": report}
    save_json(stage_path(args.output_dir, args.brand, args.product, "g2"), result)
    return result


def run_g3(g1: dict, g2: dict, args: argparse.Namespace) -> dict:
    from generation.g3_cliche_decision import run
    print("  [G3] 클리셰 follow/avoid/subvert 결정 중...")
    result = run(g1, g2["report"], **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "g3"), result)
    return result


def run_g4(brief: dict, g1: dict, g3: dict, args: argparse.Namespace) -> dict:
    from generation.g4_concept_generation import run
    print("  [G4] 컨셉 5개 생성 중...")
    result = run(brief, g1, g3, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "g4"), result)
    return result


def run_g5(g4: dict, g2: dict, g3: dict, args: argparse.Namespace) -> dict:
    from generation.g5_verification import verify_concepts
    print("  [G5] 컨셉-클리셰 임베딩 거리 검증 중...")
    result = verify_concepts(g4, g2["report"], g3, avoid_distance=args.avoid_distance)
    passed = result.get("passed", [])
    print(f"      통과: {passed if passed else '없음'}")
    save_json(stage_path(args.output_dir, args.brand, args.product, "g5"), result)
    return result


def run_g6(brief: dict, g1: dict, g4: dict, g5: dict, g3: dict, args: argparse.Namespace) -> dict:
    from generation.g6_scenario_writer import run
    concept = _select_concept(g4, g5, args.concept_id)
    print(f"  [G6] 시나리오 작성 중 (컨셉={concept.get('id')})...")
    result = run(brief, g1, concept, g3, duration=args.duration, **llm_kwargs(args))
    save_json(stage_path(args.output_dir, args.brand, args.product, "g6"), result)
    return result


def _select_concept(g4: dict, g5: dict, concept_id: str | None) -> dict:
    """--concept_id 지정 시 해당 컨셉, 아니면 G5 통과 컨셉 중 첫 번째를 선정한다."""
    concepts = g4.get("concepts", [])
    if not concepts:
        raise SystemExit("[오류] G4 컨셉 없음")
    if concept_id:
        for c in concepts:
            if c.get("id") == concept_id:
                return c
        raise SystemExit(f"[오류] 컨셉 ID 없음: {concept_id}")
    passed = set(g5.get("passed", []))
    for c in concepts:
        if c.get("id") in passed:
            return c
    print("  [경고] G5 통과 컨셉 없음 — 첫 번째 컨셉으로 진행 (violation 확인 필요)")
    return concepts[0]


# ── 전체 파이프라인 / 단일 스테이지 ───────────────────────────────────────────

def run_pipeline(args: argparse.Namespace, brief: dict) -> None:
    """G1→G6 을 순차 실행한다."""
    g1 = run_g1(brief, args)
    _require_stage_ok(g1, "g1")
    g2 = run_g2(g1, args)
    g3 = run_g3(g1, g2, args)
    _require_stage_ok(g3, "g3")
    g4 = run_g4(brief, g1, g3, args)
    _require_stage_ok(g4, "g4")
    g5 = run_g5(g4, g2, g3, args)
    g6 = run_g6(brief, g1, g4, g5, g3, args)
    _require_stage_ok(g6, "g6")


def run_single_stage(args: argparse.Namespace, brief: dict) -> None:
    """--stage g1|...|g6 로 지정된 단일 단계만 실행한다 (이전 단계 출력 파일 필요)."""
    od, b, p = args.output_dir, args.brand, args.product

    def _load(s: str) -> dict:
        return load_json(stage_path(od, b, p, s), s.upper())

    dispatch = {
        "g1": lambda: run_g1(brief, args),
        "g2": lambda: run_g2(_load("g1"), args),
        "g3": lambda: run_g3(_load("g1"), _load("g2"), args),
        "g4": lambda: run_g4(brief, _load("g1"), _load("g3"), args),
        "g5": lambda: run_g5(_load("g4"), _load("g2"), _load("g3"), args),
        "g6": lambda: run_g6(brief, _load("g1"), _load("g4"), _load("g5"), _load("g3"), args),
    }
    dispatch[args.stage]()
