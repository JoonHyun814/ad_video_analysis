"""M2 — M0(제품 정보) + M1(인사이트)로 포지셔닝을 수립한다(LLM 1회)."""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader
from generation.retrieval_pipeline.module_schemas import Module1, Module2
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M2"


def build_prompt(module0: dict[str, Any], m1: Module1) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("m2_system.md")
    user_template = prompt_loader.load("m2_user.md")
    user = prompt_loader.fill(user_template, {
        "module0_json": json.dumps(module0, ensure_ascii=False, indent=2),
        "module1_json": json.dumps(m1.model_dump(), ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_module2(module0: dict[str, Any], m1: Module1) -> tuple[Module2, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(module0, m1)
    raw = llm_adapter.chat_json(prompt["system"], prompt["user"], stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        raise RuntimeError(f"M2 LLM 호출 실패: {raw.get('error')} - {str(raw.get('raw', ''))[:300]}")
    return Module2.model_validate(raw), prompt
