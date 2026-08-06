"""M6 — 검색 결과를 반영해 최종 크리에이티브 레퍼런스 문서를 완성한다(LLM 호출).

이 호출의 user 프롬프트에 실제로 들어가는 값(M5가 실행한 장치별 검색 결과 포함)이 바로
사용자가 확인하고 싶어했던 "실제 모델에 입력되는 데이터"다 — build_prompt() 가 반환하는
문자열이 그대로 LLM에 전송되고, cli_m6.py 가 이를 파일로 그대로 남긴다.
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader
from generation.retrieval_pipeline.schemas import M4SynthesisOutput
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M6"


def build_prompt(concept_line: str, context: dict[str, Any], ad_length: str,
                 creative_problem: str, searches: list[dict[str, Any]]) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("m4_common.md") + "\n\n---\n\n" + prompt_loader.load("m4_synthesis_system.md")
    user_template = prompt_loader.load("m4_synthesis_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line,
        "ad_length": ad_length,
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
        "creative_problem": creative_problem,
        "devices_with_search_results_json": json.dumps(searches, ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_synthesis(concept_line: str, context: dict[str, Any], ad_length: str,
                  creative_problem: str, searches: list[dict[str, Any]]
                  ) -> tuple[M4SynthesisOutput, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(concept_line, context, ad_length, creative_problem, searches)
    raw = llm_adapter.chat_json(prompt["system"], prompt["user"], stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        # device_scout.run_device_scout() 와 동일한 이유로 조용히 빈 문서를 만들지 않는다.
        raise RuntimeError(f"M6(synthesis) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return M4SynthesisOutput.model_validate(raw), prompt
