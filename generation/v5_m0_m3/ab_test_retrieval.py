"""M3(컨셉 발산) --retrieval on/off A/B 비교 — M0~M2 는 한 번만 실행해 고정하고, 그 위에서
M3 만 두 번(retrieval 끄고/켜고) 실행해 비교한다.

cli.py 로 두 번 따로 실행하면(예: 오늘자 다트비트 비교) 매번 M0(크롤)~M2 도 새로 돌기 때문에
크롤 변동·LLM 샘플링 변동이 "retrieval 유무 차이"와 섞여버린다 — 이 스크립트는 M1/M2 핸드오프를
딱 한 번만 만들어 두 M3 호출에 동일하게 넣어서 그 교란 요인을 제거한다.

사용법:
    python -m generation.v5_m0_m3.ab_test_retrieval --url <URL> [--producttitle ...] \\
        [--llm_backend cli|api] [--output_dir output/v5_m0_m3/m3_ab_test]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter, module0_ingest, modules_runner
from generation.v5_m0_m3.pipeline import module0_is_usable


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


async def run_ab(url: str, *, producttitle: str = "", llm_backend: str = "cli",
                 output_dir: Path = Path("output/v5_m0_m3/m3_ab_test")) -> None:
    label = _slug(producttitle or url)
    output_dir.mkdir(parents=True, exist_ok=True)
    llm_adapter.set_backend(llm_backend)
    llm_adapter.set_retrieval(False)

    # ── M0~M2 1회만 실행해 고정 ──
    module0 = await module0_ingest.ingest(sourceurl=url, producttitle=producttitle, label=label)
    usable, reason = module0_is_usable(module0)
    if not usable:
        raise SystemExit(f"[오류] {reason}")

    handoffs: dict[int, dict] = {}
    for n in (1, 2):
        out = await modules_runner.run_module(n, module0=module0, handoffs=handoffs)
        handoffs[n] = out
        if not out:
            raise SystemExit(f"[오류] MODULE {n} 실행 실패(빈 응답) — 고정 입력을 만들지 못했다")

    _write(output_dir / f"{label}_base_m0_m2.json",
           {"module0": module0, "m1": handoffs[1], "m2": handoffs[2]})

    # ── M3, retrieval 끈 채로 ──
    llm_adapter.set_retrieval(False)
    m3_off = await modules_runner.run_module(3, module0=module0, handoffs=handoffs)
    if not m3_off:
        raise SystemExit("[오류] MODULE 3(retrieval off) 실행 실패(빈 응답)")
    _write(output_dir / f"{label}_m3_no_retrieval.json", m3_off)

    # ── M3, retrieval 켠 채로 (같은 module0/handoffs — 위와 유일한 차이는 retrieval 뿐) ──
    log_path = output_dir / f"{label}_retrieval.jsonl"
    llm_adapter.set_retrieval(True)
    llm_adapter.set_retrieval_log(log_path)
    m3_on = await modules_runner.run_module(3, module0=module0, handoffs=handoffs)
    if not m3_on:
        raise SystemExit("[오류] MODULE 3(retrieval on) 실행 실패(빈 응답)")
    _write(output_dir / f"{label}_m3_with_retrieval.json", m3_on)
    print(f"  검색 도구 사용 기록: {log_path}{' (사용 없음)' if not log_path.exists() else ''}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M3 --retrieval on/off A/B 비교 (M0~M2 고정)")
    p.add_argument("--url", required=True, help="제품 상세페이지 URL")
    p.add_argument("--producttitle", default="", help="크롤 차단 시 web_search 복구 힌트 + 파일명 slug")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"))
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3/m3_ab_test"))
    return p


def main() -> None:
    args = _build_parser().parse_args()
    asyncio.run(run_ab(args.url, producttitle=args.producttitle,
                       llm_backend=args.llm_backend, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
