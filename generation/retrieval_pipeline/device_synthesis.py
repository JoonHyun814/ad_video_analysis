"""M6 — 쿼리별 검색 결과를 반영해 쿼리 1건당 연출 장치 1개를 만든다(LLM 호출 1회, 배치).

각 장치는 **자신의 쿼리가 실제로 찾아온 검색 결과에만** 근거한다 — 다른 쿼리의 검색 결과를
섞어 쓰지 않는다(쿼리별 그라운딩을 명확히 하기 위해, prompts/device_synthesis_system.md 참고).
검색 결과가 0건인 쿼리는 "레퍼런스 미발견 — 원칙만 적용"으로 표시하고 reference_ads 를 비워
둔다(할루시네이션 방지).
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader
from generation.retrieval_pipeline.schemas import M6Output
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M6"


def build_prompt(concept_line: str, context: dict[str, Any], ad_length: str,
                 creative_problem: str, searches: list[dict[str, Any]]) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("common.md") + "\n\n---\n\n" + prompt_loader.load("device_synthesis_system.md")
    user_template = prompt_loader.load("device_synthesis_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line,
        "ad_length": ad_length,
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
        "creative_problem": creative_problem,
        "queries_with_search_results_json": json.dumps(searches, ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_device_synthesis(concept_line: str, context: dict[str, Any], ad_length: str,
                         creative_problem: str, searches: list[dict[str, Any]]
                         ) -> tuple[M6Output, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(concept_line, context, ad_length, creative_problem, searches)
    raw = llm_adapter.chat_json(prompt["system"], prompt["user"], stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        # query_scout.run_query_scout() 와 동일한 이유로 조용히 빈 장치 목록을 만들지 않는다.
        raise RuntimeError(f"M6(device_synthesis) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return M6Output.model_validate(raw), prompt
