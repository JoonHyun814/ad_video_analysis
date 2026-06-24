"""광고 브리프·시나리오 생성 파이프라인 CLI."""
import argparse
import json
import sys
from pathlib import Path

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"
_STAGES = ("m1", "m2", "m3", "m4", "m5", "m6", "m7")

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT_MODEL
from utils.io_checks import is_parse_failed, require_valid_json


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="광고 브리프·시나리오 생성 파이프라인")
    p.add_argument("--brand", required=True, help="브랜드명")
    p.add_argument("--product", required=True, help="제품명")
    p.add_argument("--brief", action="store_true", help="웹 검색으로 브리프 생성")
    p.add_argument("--scenario", action="store_true", help="브리프에서 시나리오 생성 (단일 단계, 레거시)")
    p.add_argument("--pipeline", action="store_true", help="M1→M7 전체 파이프라인 실행")
    p.add_argument("--stage", choices=_STAGES, help="특정 모듈만 실행 (이전 출력 파일 필요)")
    # brief 생성용 선택 입력
    p.add_argument("--usp", default="", help="USP (미입력 시 모델 생성)")
    p.add_argument("--target_age", default="", help="타겟 연령대 (미입력 시 모델 생성)")
    p.add_argument("--target_persona", default="", help="타겟 페르소나 (미입력 시 모델 생성)")
    p.add_argument("--positioning", default="", help="브랜드 포지셔닝 (미입력 시 모델 생성)")
    p.add_argument("--slogan", default="", help="슬로건 (미입력 시 모델 생성)")
    p.add_argument("--ingredients", nargs="*", default=None, help="핵심 성분 목록 (미입력 시 모델 생성)")
    p.add_argument("--functions", nargs="*", default=None, help="핵심 기능 목록 (미입력 시 모델 생성)")
    # 공통
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--qwen_model", default=_QWEN_DEFAULT_MODEL, help="[qwen] 베이스 모델명/경로")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT_MODEL, help=f"[gemini] 모델명 (기본: {_GEMINI_DEFAULT_MODEL})")
    p.add_argument("--output_dir", type=Path, default=Path("output/generation"), help="저장 디렉토리 (기본: output/generation)")
    # 벡터 DB 참조 (M3 참고 / M4 유사도 kill)
    p.add_argument("--m3_reference", action="store_true",
                   help="[M3] M2 포지셔닝과 유사한 기존 광고를 검색해 발산 컨텍스트로 주입")
    p.add_argument("--m3_reference_n", type=int, default=5,
                   help="[M3] 참고할 유사 광고 수 (기본: 5)")
    p.add_argument("--m4_similarity_kill", action="store_true",
                   help="[M4] 컨셉별 기존 광고 유사도 검사, threshold 이내면 강제 kill")
    p.add_argument("--m4_similarity_threshold", type=float, default=0.30,
                   help="[M4] cosine distance threshold (기본: 0.30, 작을수록 엄격)")
    p.add_argument("--m5_narrative_reference", action="store_true",
                   help="[M5] 선정 컨셉의 서사 필드로 기존 광고를 검색해 스크립트 참고로 주입 (브랜드·산업 제외)")
    p.add_argument("--m5_narrative_reference_n", type=int, default=5,
                   help="[M5] 참고할 서사 유사 광고 수 (기본: 5)")
    p.add_argument("--vector_db_path", type=Path, default=Path("output/vector_db"),
                   help="ChromaDB 저장 경로 (기본: output/vector_db)")
    p.add_argument("--vector_collection", default="video_category",
                   help="ChromaDB 컬렉션명 (기본: video_category)")
    # M6 게이트 반송 시 자동 재진입
    p.add_argument("--m6_auto_retry_max", type=int, default=0,
                   help="[M6] GATE B 반송 시 자동 재진입 최대 횟수 (기본: 0 = 비활성). "
                        "verdict=return_to_m5 → M5 재작성(M6 failure_modes 주입), "
                        "unresolved_criticals 존재 또는 return_to_gate_a → M4 selected 다음 컨셉으로 fallback.")
    return p


def _build_seed_brief(args: argparse.Namespace) -> dict:
    """CLI 입력값으로 웹 검색 없이 최소 브리프를 구성한다."""
    brief: dict = {"brand": args.brand, "product": args.product}
    for key in ("usp", "target_age", "target_persona", "positioning", "slogan"):
        if val := getattr(args, key, ""):
            brief[key] = val
    if args.ingredients:
        brief["ingredients"] = args.ingredients
    if args.functions:
        brief["functions"] = args.functions
    return brief


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


def _run_brief(args: argparse.Namespace) -> dict:
    from generation.brief_generator import generate_brief_from_web

    print(f"  브리프 생성 중 [{args.llm_backend}]...")
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
    brief_path = args.output_dir / f"{args.brand}_{args.product}.json"
    _save_json(brief_path, brief)
    return brief


def _run_scenario_legacy(args: argparse.Namespace, brief: dict) -> None:
    """단일 단계 시나리오 생성 (레거시 --scenario 플래그용)."""
    print(f"  시나리오 생성 중 [{args.llm_backend}]...")
    if args.llm_backend == "codex":
        from generation.scenario_generator_codex import generate_scenario_codex
        scenario = generate_scenario_codex(brief, model=args.codex_model)
    elif args.llm_backend == "qwen":
        from pipeline import qwen_client
        qwen_client.init(model=args.qwen_model)
        from generation.scenario_generator_qwen import generate_scenario_qwen
        scenario = generate_scenario_qwen(brief)
    elif args.llm_backend == "gemini":
        from generation.scenario_generator_gemini import generate_scenario_gemini
        scenario = generate_scenario_gemini(brief, model=args.gemini_model)
    else:
        from generation.scenario_generator import generate_scenario
        scenario = generate_scenario(brief)
    if "error" in scenario:
        print(f"  [경고] 시나리오 생성 실패: {scenario.get('error')}", file=sys.stderr)
    _save_json(args.output_dir / f"{args.brand}_{args.product}_scenario.json", scenario)


def main() -> None:
    args = _build_parser().parse_args()

    if not any([args.brief, args.scenario, args.pipeline, args.stage]):
        print("[오류] --brief / --scenario / --pipeline / --stage 중 하나 이상 지정 필요", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[생성 파이프라인] brand={args.brand}, product={args.product}, backend={args.llm_backend}")

    brief_path = args.output_dir / f"{args.brand}_{args.product}.json"

    if args.pipeline:
        # 파이프라인은 seed brief로 M1-M4를 실행하고, GATE A 통과 후 내부에서 웹 검색 브리프를 생성한다.
        from generation.scenario_pipeline import run_pipeline
        run_pipeline(args, _build_seed_brief(args))
    else:
        if args.brief:
            print("  웹 검색 중...")
            brief = _run_brief(args)
            if is_parse_failed(brief):
                raise SystemExit("[오류] 브리프 결과에 parse_failed 항목 있음. 재실행 필요.")
        else:
            brief = require_valid_json(brief_path, "brief_analysis")

        if args.scenario:
            _run_scenario_legacy(args, brief)
        elif args.stage:
            from generation.scenario_pipeline import run_single_stage
            run_single_stage(args, brief)

    print("완료.")


if __name__ == "__main__":
    main()
