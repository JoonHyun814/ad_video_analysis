"""M4 — 검색기준.txt/검색기준2.txt 의 축(구조·톤무드·샷기술)을 따라 검색 쿼리를 제안한다(LLM 호출 1회).

이 단계는 벡터 DB를 만지지 않는다 — "무엇을, 어떤 축으로 검색할지"만 LLM이 정하고, 실제 검색
실행은 M5(retrieval.py, 코드, 결정적)가 맡는다. 옛 설계는 장치(device) 후보별로 쿼리 1개씩
제안했지만, 사용자 요청으로 장치 단위 대신 검색기준 문서의 축(axis) 단위로 쿼리를 제안하도록
바꿨다 — "장치"는 검색 결과를 본 뒤 M6(device_synthesis.py)이 쿼리별로 만든다.
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader
from generation.retrieval_pipeline.schemas import M4Output
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M4"


def build_prompt(concept_line: str, context: dict[str, Any], ad_length: str) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("common.md") + "\n\n---\n\n" + prompt_loader.load("query_scout_system.md")
    user_template = prompt_loader.load("query_scout_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line,
        "ad_length": ad_length,
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_query_scout(concept_line: str, context: dict[str, Any], ad_length: str = "15초"
                    ) -> tuple[M4Output, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(concept_line, context, ad_length)
    raw = llm_adapter.chat_json(prompt["system"], prompt["user"], stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        # LLM 호출·JSON 파싱 실패를 조용히 빈 스키마로 흘려보내지 않는다 — pydantic 은 결측
        # 필드를 기본값(빈 문자열/빈 배열)으로 채워 통과시키므로, 여기서 막지 않으면 실패가
        # "쿼리 0개짜리 정상 결과"로 둔갑해 다음 단계(M5)로 조용히 넘어간다.
        raise RuntimeError(f"M4(query_scout) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return M4Output.model_validate(raw), prompt
