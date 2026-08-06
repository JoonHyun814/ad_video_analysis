"""M7 — M6이 만든 장치들을 조립해 대안 스토리라인을 만든다(LLM 호출 1회).

동시에 지금 가진 장치만으로 강한 스토리라인을 만들 수 있는지 스스로 진단한다(gap_assessment) —
부족하다고 판단하면 추가로 검색해야 할 쿼리(additional_queries, SearchQuery 와 같은 스키마)를
제안한다. 이 필드를 pipeline.run_m7() 의 재시도 루프가 읽어 M5~M6 를 한 번 더 돌리고 장치를
보강한 뒤 이 단계를 다시 호출한다(사용자 요청 — "m7 가 끝난 후 LLM 이 스스로 연출이 부족하다고
느낄 경우 추가 참조를 위한 retrieval 을 할 수 있도록").
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader
from generation.retrieval_pipeline.schemas import QueryDevice, StorylineOutput
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M7"


def build_prompt(concept_line: str, context: dict[str, Any], ad_length: str,
                 creative_problem: str, devices: list[QueryDevice]) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("common.md") + "\n\n---\n\n" + prompt_loader.load("storyline_system.md")
    user_template = prompt_loader.load("storyline_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line,
        "ad_length": ad_length,
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
        "creative_problem": creative_problem,
        "devices_json": json.dumps([d.model_dump() for d in devices], ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_storyline(concept_line: str, context: dict[str, Any], ad_length: str,
                  creative_problem: str, devices: list[QueryDevice]
                  ) -> tuple[StorylineOutput, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(concept_line, context, ad_length, creative_problem, devices)
    raw = llm_adapter.chat_json(prompt["system"], prompt["user"], stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        # query_scout.run_query_scout() 와 동일한 이유로 조용히 빈 문서를 만들지 않는다.
        raise RuntimeError(f"M7(storyline) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return StorylineOutput.model_validate(raw), prompt
