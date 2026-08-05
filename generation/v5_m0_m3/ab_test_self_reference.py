"""self-reference restore/exclude A/B 비교 — M0~M4 는 한 번만(retrieval 없이) 실행해 고정하고,
그 위에서 M5~M9 만 두 번(retrieval 켠 채로 self_mode=restore/exclude 만 바꿔) 실행해 비교한다.

M4까지 고정하는 이유는 ab_test_retrieval_m5_m9.py 와 동일하다 — M4 는 같은 입력을 줘도 실행마다
다른 컨셉을 고를 수 있는 LLM 샘플링 변동이 있고, retrieval 자체도 M4~M9 전 단계에 열려 있어
M4 실행 중 self-reference 를 만나면 그 변동까지 같이 섞인다. 그래서 M4 까지는 retrieval 없이
정확히 한 번만 실행해 고정하고, M5~M9 두 실행이 완전히 같은 handoffs[1..4] 위에서 self_mode
하나만 다르게 돈다 — "restore 와 exclude 의 유일한 차이는 검색 결과에 자기 자신이 있는지
여부"라는 실험 설계를 보장한다(사용자 요청).

사용법:
    python -m generation.v5_m0_m3.ab_test_self_reference \\
        --input output/v5_m0_m3/<slug>_m0_m3.json --self_video_id <video_id> \\
        [--llm_backend cli|api] [--style cinematic] [--output_dir output/v5_m0_m3/self_ref_ab_test]
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
    """고정된 handoffs[1..4] 위에서 M5~M9 순차 실행(pipeline.run_m4_m9 의 M5~M9 구간과 동일 로직,
    ab_test_retrieval_m5_m9.py 와 동일 함수)."""
    handoffs = dict(handoffs)  # 두 분기(restore/exclude)가 서로의 handoffs 를 오염시키지 않도록 얕은 복사
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

    m7 = await modules_runner.run_module(7, module0=module0, handoffs=handoffs)
    handoffs[7] = m7
    if not m7:
        return {"m5": m5, "m6": m6, "gates": gates, "error": "MODULE 7 실행 실패(빈 응답)"}
    gates["c"] = modules_runner.gate_c(m7)

    m9 = await modules_runner.run_module(9, module0=module0, handoffs=handoffs)
    if not m9:
        return {"m5": m5, "m6": m6, "m7": m7, "gates": gates, "error": "MODULE 9 실행 실패(빈 응답)"}

    return {"m5": m5, "m6": m6, "m7": m7, "m9": m9, "gates": gates}


async def run_ab(input_path: Path, self_video_id: int, *, llm_backend: str = "cli",
                 style: str | None = None,
                 output_dir: Path = Path("output/v5_m0_m3/self_ref_ab_test")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    llm_adapter.set_backend(llm_backend)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    module0, m1, m2, m3 = data["module0"], data["m1"], data["m2"], data["m3"]
    label = input_path.stem.removesuffix("_m0_m3")

    # ── M4 1회만(retrieval 없이) 실행해 고정 ──
    llm_adapter.set_retrieval(False)
    llm_adapter.set_self_reference(None)
    handoffs: dict[int, dict] = {1: m1, 2: m2, 3: m3}
    m4 = await modules_runner.run_module(4, module0=module0, handoffs=handoffs)
    handoffs[4] = m4
    annotated_m3 = modules_runner.annotate_concepts_with_verdict(m3, m4) or m3
    handoffs[3] = annotated_m3
    _write(output_dir / f"{label}_m4fixed.json",
           {"m3": annotated_m3, "m4": m4, "gatea": modules_runner.gate_a(m4)})

    # ── M5~M9, retrieval 켠 채로 self_mode=restore(같은 handoffs[1..4] — 유일한 차이는 self_mode) ──
    llm_adapter.set_retrieval(True)
    restore_log = output_dir / f"{label}_m5m9_restore_retrieval.jsonl"
    llm_adapter.set_retrieval_log(restore_log)
    llm_adapter.set_self_reference(self_video_id, "restore")
    restore = await _run_m5_m9(module0, handoffs, style=style)
    _write(output_dir / f"{label}_m5m9_restore.json", restore)

    # ── M5~M9, retrieval 켠 채로 self_mode=exclude(같은 handoffs[1..4] — 유일한 차이는 self_mode) ──
    exclude_log = output_dir / f"{label}_m5m9_exclude_retrieval.jsonl"
    llm_adapter.set_retrieval_log(exclude_log)
    llm_adapter.set_self_reference(self_video_id, "exclude")
    exclude = await _run_m5_m9(module0, handoffs, style=style)
    _write(output_dir / f"{label}_m5m9_exclude.json", exclude)

    print(f"  restore 검색 기록: {restore_log}{' (사용 없음)' if not restore_log.exists() else ''}")
    print(f"  exclude 검색 기록: {exclude_log}{' (사용 없음)' if not exclude_log.exists() else ''}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="self-reference restore/exclude A/B 비교 (M0~M4 고정, M5~M9 만 self_mode 차이)"
    )
    p.add_argument("--input", required=True, type=Path,
                   help="run_m0_m3()/cli_m3.py 가 만든 *_m0_m3.json 경로 ({module0,m1,m2,m3})")
    p.add_argument("--self_video_id", required=True, type=int,
                   help="검색 결과에서 restore/exclude 대상이 될 video_id(지금 분석 중인 광고 자신)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"))
    p.add_argument("--style", default="", help="M9 콘티 촬영 포맷(미지정 시 cinematic 기본값)")
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3/self_ref_ab_test"))
    return p


def main() -> None:
    args = _build_parser().parse_args()
    asyncio.run(run_ab(args.input, args.self_video_id, llm_backend=args.llm_backend,
                       style=args.style or None, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
