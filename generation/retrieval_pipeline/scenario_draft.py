"""M3 — M2가 완성한 연출 장치 8개(근거 포함) 중 2~4개씩 조합해 러프한 시나리오 초안을
정확히 5개 만든다(LLM 1회, 도구 없음 — 장치 자체의 근거는 이미 M2에서 끝난 일이라 여기서
다시 검색하지 않는다). device_generation.py(M2)와 같은 패턴 — LLM 호출 1회, tool_chat.run()
을 그대로 재사용한다(README의 선례 — "M5는 검색을 쓰지 않지만 같은 호출 인프라를 재사용"과
동일한 이유). system/user 프롬프트 문구는 전부 prompts/m3_*.md 에 있다(이 파일은 프롬프트
조립·LLM 호출·파싱만 한다).

M4(scenario_generation.py, 풀 프로덕션 시나리오 1개 완성)보다 가벼운 발산 단계다 — 컷 단위
beats 까지 완성하지 않고, "이 장치들을 조합하면 대략 이런 이야기가 된다"는 스케치 5개를 빠르게
비교하기 위한 것이다(사용자 요청 — "m2의 device를 2~4개정도 조합해서 러프한 시나리오를
5개정도 생성"). 이 초안 중 하나를 골라 M4로 넘기는 배선은 아직 없다(다음 요청에서 다룬다).
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader, tool_chat
from generation.retrieval_pipeline.schemas import ScenarioDraftOutput


def build_prompt(context: dict[str, Any], creative_problem: str, devices: list[dict[str, Any]],
                 *, concept_line: str = "", ad_length: str = "15초", log_prefix: str = "default"
                 ) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system_template = prompt_loader.load("m3_common.md") + "\n\n---\n\n" + prompt_loader.load("m3_system.md")
    system = prompt_loader.fill(system_template, {"log_prefix": log_prefix})
    user_template = prompt_loader.load("m3_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line or "(제공되지 않음)",
        "ad_length": ad_length,
        "creative_problem": creative_problem,
        "devices_json": json.dumps(devices, ensure_ascii=False, indent=2),
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_scenario_draft(context: dict[str, Any], creative_problem: str, devices: list[dict[str, Any]],
                       *, concept_line: str = "", ad_length: str = "15초", backend: str = "cli",
                       log_prefix: str = "default", log_dir: str | None = None
                       ) -> tuple[ScenarioDraftOutput, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(context, creative_problem, devices, concept_line=concept_line,
                          ad_length=ad_length, log_prefix=log_prefix)
    raw = tool_chat.run(prompt["system"], prompt["user"], backend=backend,
                        log_prefix=log_prefix, log_dir=log_dir, stage="M3")
    if isinstance(raw, dict) and raw.get("error"):
        # M2/M4와 동일한 이유로 조용히 빈 스키마로 흘려보내지 않는다 — pydantic 결측 필드
        # 기본값(빈 배열)이 실패를 "초안 0개짜리 정상 결과"로 둔갑시켜 다음 단계로 조용히
        # 넘어가는 것을 막는다.
        raise RuntimeError(f"M3(scenario_draft) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return ScenarioDraftOutput.model_validate(raw), prompt
