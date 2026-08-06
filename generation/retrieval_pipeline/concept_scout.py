"""M3 — generation/docs/m3_concept.md 의 발산 기법 7종으로 한 줄 컨셉을 만들고 자가평가·순위를
매긴다(LLM 호출 1회).

M4(query_scout.py)가 받는 "한 줄 크리에이티브 원칙"을 사용자가 직접 타이핑하는 대신, 이 단계가
후보 7개를 만들어 순위를 매겨 제안한다 — cli_m4.py 는 `--concept` 를 생략하면 이 중 rank=1을
자동으로 쓰고, `--select_concept "<technique>"` 로 다른 후보를 지정할 수도 있다(v5_m0_m3 의
cli_m4_m9.py `--select_concept` 와 같은 패턴).
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader
from generation.retrieval_pipeline.schemas import M3Output
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M3"


def build_prompt(context: dict[str, Any]) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("m3_system.md")
    user_template = prompt_loader.load("m3_user.md")
    user = prompt_loader.fill(user_template, {
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_concept_scout(context: dict[str, Any]) -> tuple[M3Output, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(context)
    raw = llm_adapter.chat_json(prompt["system"], prompt["user"], stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        # query_scout.run_query_scout() 와 동일한 이유로 조용히 빈 후보 목록을 만들지 않는다.
        raise RuntimeError(f"M3(concept_scout) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    output = M3Output.model_validate(raw)
    output.concepts.sort(key=lambda c: c.rank or 999)
    return output, prompt
