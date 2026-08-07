"""retrieval_pipeline 오케스트레이터.

  run_m0_m2(): generation.v5_m0_m3.pipeline.run_m0_m2() 를 그대로 재노출한다(사용자 요청 —
      "M0~M2는 v5_m0_m3과 동일"). 크롤·M1·M2 로직을 이 파이프라인에 다시 구현하지 않는다.
  run_m3_blank(): M3는 아직 설계 전이라 공백 placeholder만 반환한다(사용자 요청 — "M3는 일단
      공백으로 남기고"). v5_m0_m3 의 <slug>_m0_m3.json 계약과 같은 모양({"module0","m1","m2","m3"})을
      유지해, M3가 나중에 채워져도 cli_m4.py 입력 형식이 안 바뀐다.

한 줄 컨셉 원칙을 받아 DBH_Creative_Reference_Ideas.md 의 사고 과정(레퍼런스 근거 → 장치 →
대안 스토리라인 → 비교/권고)을 재현하는 나머지 구간은 M4~M7 네 단계로 나눴다(사용자 요청 —
"m4를 순서별로 m4 -> m5, ... 으로 구분"). v5_m0_m3 의 cli.py/cli_m3.py/cli_m4_m9.py 분리와 같은
이유다 — 앞 단계(비용이 큰 LLM 호출)를 고정해두고 뒷 단계만 몇 번이든 다시 돌릴 수 있게:

  run_m4(): 크리에이티브 문제 진단 + 연출 장치 후보·검색 쿼리 제안 (LLM 1회, device_scout.py)
  run_m5(): 장치별 벡터 DB 검색 실행 (결정적, LLM 아님, retrieval.py)
  run_m6(): 검색 결과를 반영해 최종 문서 JSON 합성 (LLM 1회, synthesis.py)
  run_m7(): 최종 문서 JSON → Markdown 렌더링 (LLM 아님, render_markdown.py)

각 함수는 바로 앞 함수의 반환 dict 를 그대로 입력받는다 — cli_m4~cli_m7.py 가 이 dict 를
파일로 저장/로드하며 체인을 이어간다.
"""
from __future__ import annotations

from typing import Any

from generation.retrieval_pipeline import device_scout, render_markdown, retrieval, synthesis
from generation.retrieval_pipeline.context import build_context
from generation.retrieval_pipeline.schemas import DeviceQuery, M4SynthesisOutput
from generation.v5_m0_m3.pipeline import run_m0_m2  # noqa: F401  (재노출 — 사용자 요청)

_CARRY_KEYS = ("module0", "m1", "m2", "m3", "concept_line", "ad_length", "context")


def run_m3_blank(module0: dict, m1: dict, m2: dict) -> dict[str, Any]:
    """M3(컨셉 발산)는 아직 미구현 — 계약 형태만 맞춘 빈 placeholder를 반환한다."""
    return {
        "module0": module0, "m1": m1, "m2": m2,
        "m3": {"note": "M3(컨셉 발산)는 이 파이프라인에서 아직 구현되지 않았습니다 — 공백 placeholder."},
    }


def run_m4(module0: dict, m1: dict, m2: dict, m3: dict, concept_line: str, *,
          ad_length: str = "15초") -> dict[str, Any]:
    """M4 — 크리에이티브 문제 진단 + 연출 장치 후보·검색 쿼리 제안(LLM 1회, 아직 검색 없음).

    반환에는 다음 단계(M5)가 그대로 이어받을 수 있도록 module0~m3 와 concept_line/ad_length 를
    함께 담는다(각 단계 출력 파일이 독립적으로 다음 단계의 유일한 입력이 될 수 있도록).
    """
    context = build_context(module0, m1, m2)
    scout_output, prompt = device_scout.run_device_scout(concept_line, context, ad_length)
    return {
        "module0": module0, "m1": m1, "m2": m2, "m3": m3,
        "concept_line": concept_line, "ad_length": ad_length,
        "context": context,
        "prompt": prompt,
        "creative_problem": scout_output.creative_problem,
        "device_candidates": [d.model_dump() for d in scout_output.devices],
    }


def run_m5(m4_result: dict[str, Any], *, top_k: int = 3,
          db_path: str | None = None) -> dict[str, Any]:
    """M5 — M4가 제안한 장치별 검색 쿼리를 벡터 DB에 실제로 실행한다(결정적, LLM 아님)."""
    devices = [DeviceQuery.model_validate(d) for d in m4_result.get("device_candidates", [])]
    searches = retrieval.run_searches(devices, top_k=top_k, db_path=db_path)
    return {
        **{k: m4_result[k] for k in _CARRY_KEYS if k in m4_result},
        "creative_problem": m4_result.get("creative_problem", ""),
        "device_candidates": m4_result.get("device_candidates", []),
        "search_queries": retrieval.queries_only(searches),
        "search_results": retrieval.results_only(searches),
        "searches": searches,
    }


def run_m6(m5_result: dict[str, Any]) -> dict[str, Any]:
    """M6 — M5의 검색 결과를 반영해 최종 문서 JSON을 합성한다(LLM 1회).

    이 호출의 user 프롬프트에 실제로 들어가는 값(장치별 검색 결과 포함)이 사용자가 확인하고
    싶어했던 "실제 모델에 입력되는 데이터"다 — 반환의 `prompt` 키에 그대로 남는다.
    """
    final_output, prompt = synthesis.run_synthesis(
        m5_result["concept_line"], m5_result["context"], m5_result["ad_length"],
        m5_result.get("creative_problem", ""), m5_result.get("searches", []),
    )
    return {
        **{k: m5_result[k] for k in _CARRY_KEYS if k in m5_result},
        "prompt": prompt,
        **final_output.model_dump(),
    }


def run_m7(m6_result: dict[str, Any]) -> str:
    """M7 — M6의 구조화 출력을 DBH_Creative_Reference_Ideas.md 형식 Markdown으로 렌더링한다."""
    output = M4SynthesisOutput.model_validate(m6_result)
    return render_markdown.render(m6_result["concept_line"], m6_result["ad_length"], output)


def run_m4_m7(module0: dict, m1: dict, m2: dict, m3: dict, concept_line: str, *,
             ad_length: str = "15초", top_k: int = 3, db_path: str | None = None
             ) -> dict[str, Any]:
    """run_m4()~run_m7() 를 이어 붙인 편의 래퍼 — 네 단계를 한 번에 실행하고 싶을 때만 쓴다
    (v5_m0_m3.pipeline.run_m0_m3() 와 같은 성격 — CLI는 단계 분리가 목적이라 이 래퍼를 노출하지
    않는다). 반환에 m6 의 모든 필드 + `markdown` 을 함께 담는다."""
    m4 = run_m4(module0, m1, m2, m3, concept_line, ad_length=ad_length)
    m5 = run_m5(m4, top_k=top_k, db_path=db_path)
    m6 = run_m6(m5)
    markdown = run_m7(m6)
    return {**m6, "markdown": markdown}
