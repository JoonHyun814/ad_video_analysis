"""M5~M9 --retrieval on/off A/B 비교 — M0~M4 는 한 번만 실행해 고정하고, 그 위에서
M5~M9 만 두 번(retrieval 끄고/켜고) 실행해 비교한다.

M4까지 고정하는 이유: M4(비평·선택)는 같은 입력을 줘도 실행마다 다른 컨셉을 고를 수 있는
LLM 샘플링 변동이 있다 — 이 변동이 "M5~M9 retrieval 유무 차이"와 섞이면 원인을 못 가른다.
그래서 M4까지는 정확히 한 번만(retrieval 없이) 실행해 고정하고, 그 위에서 M5~M9만 반복
비교한다. ab_test_retrieval.py(M0~M2 고정, M3 on/off)와 같은 설계 원칙을 M4까지 한 단계
더 내려 적용한 것이다.

사용법:
    python -m generation.v5_m0_m3.ab_test_retrieval_m5_m9 \\
        --input output/v5_m0_m3/<slug>_m0_m3.json \\
        [--llm_backend cli|api] [--style cinematic] [--output_dir output/v5_m0_m3/m3_ab_test]
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter, modules_runner


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


async def _run_m5_m9(module0: dict, handoffs: dict, *, style: str | None) -> dict:
    """고정된 handoffs[1..4] 위에서 M5~M9 순차 실행(pipeline.run_m4_m9 의 M5~M9 구간과 동일 로직)."""
    handoffs = dict(handoffs)  # 두 분기(off/on)가 서로의 handoffs 를 오염시키지 않도록 얕은 복사
    if style:
        module0 = dict(module0)
        module0["videostyle"] = style
    gates: dict[str, str] = {}

    m5 = await modules_runner.run_module(5, module0=module0, handoffs=handoffs)
    handoffs[5] = m5
    if not m5:
        return {"gates": gates, "error": "MODULE 5 실행 실패(빈 응답)"}

    m6 = await modules_runner.run_module(6, module0=module0, handoffs=handoffs)
    handoffs[6] = m6
    gates["b"] = modules_runner.gate_b(m6)
    # pipeline.run_m4_m9() 와 동일하게 GATE B block 이어도 중단하지 않는다(소스 run_full() 재현 —
    # pipeline.py 의 GATE B 주석 참고). 이 A/B 스크립트가 pipeline.py 의 M5~M9 구간을 그대로
    # 복제한 것이므로 동작도 동일하게 맞춘다.

    m7 = await modules_runner.run_module(7, module0=module0, handoffs=handoffs)
    handoffs[7] = m7
    if not m7:
        return {"m5": m5, "m6": m6, "gates": gates, "error": "MODULE 7 실행 실패(빈 응답)"}
    gates["c"] = modules_runner.gate_c(m7)

    m9 = await modules_runner.run_module(9, module0=module0, handoffs=handoffs)
    if not m9:
        return {"m5": m5, "m6": m6, "m7": m7, "gates": gates, "error": "MODULE 9 실행 실패(빈 응답)"}

    return {"m5": m5, "m6": m6, "m7": m7, "m9": m9, "gates": gates}


async def run_ab(input_path: Path, *, llm_backend: str = "cli", style: str | None = None,
                 output_dir: Path = Path("output/v5_m0_m3/m3_ab_test")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    llm_adapter.set_backend(llm_backend)
    llm_adapter.set_retrieval(False)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    module0, m1, m2, m3 = data["module0"], data["m1"], data["m2"], data["m3"]
    label = input_path.stem.removesuffix("_m0_m3")

    # ── M4 1회만(retrieval 없이) 실행해 고정 ──
    handoffs: dict[int, dict] = {1: m1, 2: m2, 3: m3}
    m4 = await modules_runner.run_module(4, module0=module0, handoffs=handoffs)
    handoffs[4] = m4
    annotated_m3 = modules_runner.annotate_concepts_with_verdict(m3, m4) or m3
    handoffs[3] = annotated_m3
    _write(output_dir / f"{label}_m4fixed.json",
           {"m3": annotated_m3, "m4": m4, "gatea": modules_runner.gate_a(m4)})

    # ── M5~M9, retrieval 끈 채로(고정된 handoffs[1..4] 위에서) ──
    llm_adapter.set_retrieval(False)
    off = await _run_m5_m9(module0, handoffs, style=style)
    _write(output_dir / f"{label}_m5m9_no_retrieval.json", off)

    # ── M5~M9, retrieval 켠 채로(같은 handoffs[1..4] — 유일한 차이는 retrieval) ──
    log_path = output_dir / f"{label}_m5m9_retrieval.jsonl"
    llm_adapter.set_retrieval(True)
    llm_adapter.set_retrieval_log(log_path)
    on = await _run_m5_m9(module0, handoffs, style=style)
    _write(output_dir / f"{label}_m5m9_with_retrieval.json", on)
    print(f"  검색 도구 사용 기록: {log_path}{' (사용 없음)' if not log_path.exists() else ''}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M5~M9 --retrieval on/off A/B 비교 (M0~M4 고정)")
    p.add_argument("--input", required=True, type=Path,
                   help="run_m0_m3()/cli_m3.py 가 만든 *_m0_m3.json 경로 ({module0,m1,m2,m3})")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"))
    p.add_argument("--style", default="", help="M9 콘티 촬영 포맷(미지정 시 cinematic 기본값)")
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3/m3_ab_test"))
    return p


def main() -> None:
    args = _build_parser().parse_args()
    asyncio.run(run_ab(args.input, llm_backend=args.llm_backend, style=args.style or None,
                       output_dir=args.output_dir))


if __name__ == "__main__":
    main()
