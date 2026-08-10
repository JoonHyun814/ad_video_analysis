"""retrieval_pipeline 오케스트레이터.

  run_m0_m2(): generation.v5_m0_m3.pipeline.run_m0_m2() 를 그대로 재노출한다(사용자 요청 —
      "M0~M2는 v5_m0_m3과 동일"). 크롤·M1·M2 로직을 이 파이프라인에 다시 구현하지 않는다.
  run_m3(): M0~M2 맥락을 입력받아 search_chromadb 도구를 자율 호출하며 연출 장치 8개를
      완성한다(LLM 1회, 도구 왕복은 다회, device_generation.py). 이전 설계(M3 공백
      placeholder → M4 device_scout → M5 retrieval → M6 synthesis → M7 render)를 걷어내고
      파이프라인을 처음부터 다시 설계하는 중이다(사용자 요청 — "pipeline 개편, 다 지우고
      한단계씩 개발"). 뒷 단계(스토리라인 등)는 아직 없다 — 다음 요청에서 이어 붙인다.
"""
from __future__ import annotations

from typing import Any

from generation.retrieval_pipeline import device_generation
from generation.retrieval_pipeline.context import build_context
from generation.v5_m0_m3.pipeline import run_m0_m2  # noqa: F401  (재노출 — 사용자 요청)


def run_m3(module0: dict, m1: dict, m2: dict, *, concept_line: str = "",
          ad_length: str = "15초", backend: str = "cli", log_prefix: str = "default",
          log_dir: str | None = None) -> dict[str, Any]:
    """M3 — m0~m2 맥락을 분석하고 도구 호출로 근거를 모아 연출 장치 8개를 완성한다.

    log_prefix: search_chromadb 호출 로그 파일명(<log_prefix>.jsonl) — cli_m3.py 는
    --title(슬러그)을 그대로 넘긴다(사용자 요청 — 프로젝트 제목별로 로그 분리).
    log_dir: 그 로그 파일을 남길 폴더 — cli_m3.py 는 이 실행의 출력 폴더
    (output/retrieval_pipeline/<날짜>_<제목>/)를 그대로 넘긴다(사용자 요청 — 날짜 폴더 하위에
    저장). 안 주면 tool_chat.py 기본값(logs/search_chromadb/)을 쓴다.

    반환에 module0~m2/concept_line/ad_length/context 를 함께 담는다 — 다음 단계가 이 dict
    하나만으로 이어받을 수 있도록(각 단계 출력 파일이 독립적으로 다음 단계의 유일한 입력이
    될 수 있도록 하는 이 파이프라인의 기존 관례를 그대로 따른다).
    """
    context = build_context(module0, m1, m2)
    output, prompt = device_generation.run_device_generation(
        context, ad_length=ad_length, concept_line=concept_line, backend=backend,
        log_prefix=log_prefix, log_dir=log_dir,
    )
    return {
        "module0": module0, "m1": m1, "m2": m2,
        "concept_line": concept_line, "ad_length": ad_length,
        "context": context,
        "prompt": prompt,
        "creative_problem": output.creative_problem,
        "devices": [d.model_dump() for d in output.devices],
    }
