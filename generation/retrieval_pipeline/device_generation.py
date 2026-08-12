"""M2 — M1 인사이트(+선택적 legacy m0~m2 맥락)를 분석하고 search_chromadb 도구를 자율
호출해 근거를 모은 뒤 연출 장치 8개를 완성한다(LLM 1회 호출 — 그 호출 안에서 도구 왕복은
여러 번). 원래 이 파이프라인의 M3였다(사용자 요청 — "기존 m3 -> m2로 변경"). 이 파이프라인의
이전 설계(device_scout(LLM, 검색 없음) → retrieval(코드, 결정적 검색) → synthesis(LLM, 결과
반영) 3단계)를 한 단계로 합쳤다 — "검색할지·언제·몇 건"을 LLM 이 tool_use 로 스스로 판단하게
한다(사용자 요청 — pipeline 개편). system/user 프롬프트 문구는 전부 prompts/m2_*.md 에 있다
(이 파일은 프롬프트 조립·LLM 호출·파싱만 한다).
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader, tool_chat
from generation.retrieval_pipeline.schemas import DeviceGenerationOutput


def build_prompt(context: dict[str, Any], ad_length: str, concept_line: str = "",
                 log_prefix: str = "default") -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨).

    log_prefix 는 system 프롬프트에 그대로 박혀 들어간다 — search_chromadb 호출 로그
    (logs/search_chromadb/<log_prefix>.jsonl)를 프로젝트 제목별로 나누기 위함(사용자 요청).
    """
    system_template = prompt_loader.load("m2_common.md") + "\n\n---\n\n" + prompt_loader.load("m2_system.md")
    system = prompt_loader.fill(system_template, {"log_prefix": log_prefix})
    user_template = prompt_loader.load("m2_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line or "(제공되지 않음 — 아래 맥락에서 직접 도출하라)",
        "ad_length": ad_length,
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_device_generation(context: dict[str, Any], *, ad_length: str = "15초",
                          concept_line: str = "", backend: str = "cli", log_prefix: str = "default",
                          log_dir: str | None = None
                          ) -> tuple[DeviceGenerationOutput, dict[str, str]]:
    """프롬프트를 조립해 LLM(+도구)을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(context, ad_length, concept_line, log_prefix)
    raw = tool_chat.run(prompt["system"], prompt["user"], backend=backend,
                        log_prefix=log_prefix, log_dir=log_dir, stage="M2")
    if isinstance(raw, dict) and raw.get("error"):
        # LLM 호출·JSON 파싱 실패를 조용히 빈 스키마로 흘려보내지 않는다 — pydantic 은 결측
        # 필드를 기본값(빈 문자열/빈 배열)으로 채워 통과시키므로, 여기서 막지 않으면 실패가
        # "장치 0개짜리 정상 결과"로 둔갑해 다음 단계로 조용히 넘어간다.
        raise RuntimeError(f"M2(device_generation) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return DeviceGenerationOutput.model_validate(raw), prompt
