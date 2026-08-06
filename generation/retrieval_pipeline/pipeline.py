"""retrieval_pipeline 오케스트레이터.

  run_m0_m2(): generation.v5_m0_m3.pipeline.run_m0_m2() 를 그대로 재노출한다(사용자 요청 —
      "M0~M2는 v5_m0_m3과 동일"). 크롤·M1·M2 로직을 이 파이프라인에 다시 구현하지 않는다.
  run_m3(): generation/docs/m3_concept.md 의 발산 기법 7종으로 컨셉 후보를 만들고, 타깃 그룹에
      맞는 페르소나 3명이 각자 순위를 매긴 뒤 코드가 취합한다(LLM 5회, concept_scout.py — 자세한
      흐름은 그 파일 docstring 참고). **M3부터 이 파이프라인의 실행 폴더(output/retrieval_pipeline/
      <날짜>_<제목>/)를 만든다**(사용자 요청 — "m3 단계 결과도 <날짜>_<제목> 폴더 안에 저장되도록
      수정") — cli_m3.py 가 `--title` 을 받아 폴더를 만들고 m3.json 을 그 안에 저장하면, 이후
      cli_m4~cli_m7 은 항상 그 폴더 안에서 이어진다.

  M0~M2 결과(module0/m1/m2, 대개 수십 KB)는 M3 가 context(압축 요약)를 뽑아내는 데만 쓰고,
  그 뒤로는 어떤 산출물에도 다시 싣지 않는다(사용자 요청 — "모든 산출물에 m0-m2 결과가 있을
  필요 없음"). M4~M7 은 module0/m1/m2 자체가 아니라 M3 가 이미 압축해 둔 `context` 만 받는다
  — _CARRY_KEYS 가 이를 강제한다.

M4~M7 는 검색기준.txt/검색기준2.txt 를 반영한 재설계로 각 단계의 책임이 바뀌었다(사용자 요청 —
"m4: 장치 별이 아니라 검색기준 문서를 참조하여 쿼리 생성", "m5: 쿼리 실행 및 결과 기록",
"m6: 쿼리별 장치 생성", "m7: m6 들을 조립해서 스토리라인 생성"):

  run_m4(): 검색기준 문서의 축(구조·톤무드·샷기술)을 따라 크리에이티브 문제 진단 + 검색 쿼리
            제안 (LLM 1회, query_scout.py)
  run_m5(): 쿼리를 벡터 DB에 실제로 실행하고 결과를 기록 (결정적, LLM 아님, retrieval.py)
  run_m6(): 쿼리별 검색 결과로 쿼리 1건당 연출 장치 1개 생성 (LLM 1회, device_synthesis.py)
  run_m7(): 장치들을 조립해 대안 스토리라인 생성 (LLM 1회 이상, storyline.py) — 매 호출마다
            LLM 이 스스로 지금 가진 장치로 충분한지 진단한다(gap_assessment). 부족하다고
            판단하면 additional_queries 로 run_m5()~run_m6() 를 한 번 더 돌려 장치를 보강한 뒤
            run_m7() 을 다시 호출한다(최대 max_rounds 회, 사용자 요청 — "m7 가 끝난 후 LLM 이
            스스로 연출이 부족하다고 느낄 경우 추가 참조를 위한 retrieval(m4)를 할 수 있도록").
            재시도 라운드는 매번 새 M4 진단을 다시 하지 않는다 — M7 자신이 이미 무엇이 부족한지
            정확히 알고 있으므로 그 판단을 그대로 다음 라운드의 쿼리로 쓴다. 재시도로 생긴
            라운드도 `rounds` 에 그대로 남아 cli_m7.py 가 파일로 남긴다(투명성 유지).

각 함수는 바로 앞 함수의 반환 dict 를 그대로 입력받는다 — cli_m3~cli_m7.py 가 이 dict 를
파일로 저장/로드하며 체인을 이어간다.
"""
from __future__ import annotations

from typing import Any

from generation.retrieval_pipeline import (
    concept_scout, device_synthesis, query_scout, render_markdown, retrieval, storyline,
)
from generation.retrieval_pipeline.context import build_context
from generation.retrieval_pipeline.schemas import QueryDevice, SearchQuery
from generation.v5_m0_m3.pipeline import run_m0_m2  # noqa: F401  (재노출 — 사용자 요청)

_CARRY_KEYS = ("concept_line", "ad_length", "context")
_MAX_ROUNDS_DEFAULT = 2


def run_m3(module0: dict, m1: dict, m2: dict) -> dict[str, Any]:
    """M3 — 발산 기법 7종으로 컨셉 후보를 만들고 페르소나 3명이 매긴 순위를 취합한다(LLM 5회).

    module0/m1/m2 는 여기서 context 로 압축되는 데만 쓰이고 반환값에는 실리지 않는다 — 이후
    모든 단계는 이 함수가 만든 `context` 만 이어받는다.
    """
    context = build_context(module0, m1, m2)
    output, prompts = concept_scout.run_concept_scout(context)
    return {
        "context": context,
        "m3": {
            "prompts": prompts,
            "personas": [p.model_dump() for p in output.personas],
            "concepts": [c.model_dump() for c in output.concepts],
        },
    }


def run_m4(context: dict[str, Any], concept_line: str, *, ad_length: str = "15초") -> dict[str, Any]:
    """M4 — 검색기준 축을 따라 크리에이티브 문제 진단 + 검색 쿼리 제안(LLM 1회, 아직 검색 없음)."""
    scout_output, prompt = query_scout.run_query_scout(concept_line, context, ad_length)
    return {
        "concept_line": concept_line, "ad_length": ad_length, "context": context,
        "prompt": prompt,
        "creative_problem": scout_output.creative_problem,
        "queries": [q.model_dump() for q in scout_output.queries],
    }


def run_m5(m4_result: dict[str, Any], *, top_k: int = 3,
          db_path: str = "output/vector_db") -> dict[str, Any]:
    """M5 — M4가 제안한 쿼리를 벡터 DB에 실제로 실행한다(결정적, LLM 아님)."""
    queries = [SearchQuery.model_validate(q) for q in m4_result.get("queries", [])]
    searches = retrieval.run_searches(queries, top_k=top_k, db_path=db_path)
    return {
        **{k: m4_result[k] for k in _CARRY_KEYS if k in m4_result},
        "creative_problem": m4_result.get("creative_problem", ""),
        "queries": m4_result.get("queries", []),
        "search_queries": retrieval.queries_only(searches),
        "search_results": retrieval.results_only(searches),
        "searches": searches,
    }


def run_m6(m5_result: dict[str, Any]) -> dict[str, Any]:
    """M6 — 쿼리별 검색 결과로 쿼리 1건당 장치 1개를 생성한다(LLM 1회).

    이 호출의 user 프롬프트에 실제로 들어가는 값(쿼리별 검색 결과 포함)이 사용자가 확인하고
    싶어했던 "실제 모델에 입력되는 데이터"다 — 반환의 `prompt` 키에 그대로 남는다.
    """
    output, prompt = device_synthesis.run_device_synthesis(
        m5_result["concept_line"], m5_result["context"], m5_result["ad_length"],
        m5_result.get("creative_problem", ""), m5_result.get("searches", []),
    )
    return {
        **{k: m5_result[k] for k in _CARRY_KEYS if k in m5_result},
        "creative_problem": m5_result.get("creative_problem", ""),
        "prompt": prompt,
        "devices": [d.model_dump() for d in output.devices],
    }


def run_m7(m6_result: dict[str, Any], *, top_k: int = 3, db_path: str = "output/vector_db",
          max_rounds: int = _MAX_ROUNDS_DEFAULT) -> dict[str, Any]:
    """M7 — 장치들을 조립해 대안 스토리라인을 만든다(LLM 1회 이상).

    gap_assessment.sufficient 가 False 이고 라운드가 max_rounds 미만이면, additional_queries 로
    run_m5()~run_m6() 를 한 번 더 돌려 장치를 보강한 뒤 다시 조립한다. max_rounds=1 이면 재시도
    없이 첫 결과를 그대로 확정한다.
    """
    concept_line, ad_length, context = m6_result["concept_line"], m6_result["ad_length"], m6_result["context"]
    creative_problem = m6_result.get("creative_problem", "")
    devices: list[dict[str, Any]] = list(m6_result.get("devices", []))
    rounds: list[dict[str, Any]] = [{"round": 1, "devices": devices, "note": "M4~M6 최초 실행"}]

    round_no = 1
    while True:
        device_models = [QueryDevice.model_validate(d) for d in devices]
        story_output, story_prompt = storyline.run_storyline(
            concept_line, context, ad_length, creative_problem, device_models,
        )
        gap = story_output.gap_assessment
        if gap.sufficient or not gap.additional_queries or round_no >= max_rounds:
            break

        round_no += 1
        extra_m4 = {
            **{k: m6_result[k] for k in _CARRY_KEYS if k in m6_result},
            "creative_problem": creative_problem,
            "queries": [q.model_dump() for q in gap.additional_queries],
        }
        extra_m5 = run_m5(extra_m4, top_k=top_k, db_path=db_path)
        extra_m6 = run_m6(extra_m5)
        devices = devices + extra_m6["devices"]
        rounds.append({
            "round": round_no, "gap_note": gap.note,
            "search_queries": extra_m5["search_queries"], "search_results": extra_m5["search_results"],
            "m6_prompt": extra_m6["prompt"], "devices": extra_m6["devices"],
        })

    markdown = render_markdown.render(concept_line, ad_length, creative_problem, device_models, story_output)
    return {
        **{k: m6_result[k] for k in _CARRY_KEYS if k in m6_result},
        "creative_problem": creative_problem,
        "devices": devices,
        "storyline_prompt": story_prompt,
        "storylines": [s.model_dump() for s in story_output.storylines],
        "comparison": [c.model_dump() for c in story_output.comparison],
        "recommendation": story_output.recommendation.model_dump(),
        "common_checks": story_output.common_checks,
        "next_steps": story_output.next_steps,
        "gap_assessment": story_output.gap_assessment.model_dump(),
        "rounds": rounds,
        "markdown": markdown,
    }


def run_m3_m7(module0: dict, m1: dict, m2: dict, concept_line: str, *,
             ad_length: str = "15초", top_k: int = 3, db_path: str = "output/vector_db",
             max_rounds: int = _MAX_ROUNDS_DEFAULT) -> dict[str, Any]:
    """run_m3()~run_m7() 를 이어 붙인 편의 래퍼 — 다섯 단계를 한 번에 실행하고 싶을 때만 쓴다
    (v5_m0_m3.pipeline.run_m0_m3() 와 같은 성격 — CLI는 단계 분리가 목적이라 이 래퍼를 노출하지
    않는다). M3 가 만든 컨셉 순위와 무관하게 `concept_line` 을 그대로 M4 입력으로 쓴다(자동
    선택 로직은 cli_m4.py 의 몫). 반환에 m7 의 모든 필드(`markdown` 포함)를 담는다."""
    m3 = run_m3(module0, m1, m2)
    m4 = run_m4(m3["context"], concept_line, ad_length=ad_length)
    m5 = run_m5(m4, top_k=top_k, db_path=db_path)
    m6 = run_m6(m5)
    return run_m7(m6, top_k=top_k, db_path=db_path, max_rounds=max_rounds)
