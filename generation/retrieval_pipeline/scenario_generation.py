"""M4 — M2가 완성한 연출 장치 8개(근거 포함) 중 이 제품·광고 길이에 맞는 것을 골라 조합해
광고 전체 시나리오(scenario_analysis.json 과 동일한 구조: cast/scenes/key_messages/
production_notes)를 완성한다. device_generation.py(M2)와 같은 패턴 — LLM 호출 1회, 그 안에서
`search_chromadb` 도구 왕복은 선택적으로 여러 번(컷 구성·페이싱 참고용, 장치 자체의 근거는
이미 M2에서 끝난 일이라 의무는 아니다). system/user 프롬프트 문구는 전부 prompts/m4_*.md 에
있다(이 파일은 프롬프트 조립·LLM 호출·파싱만 한다). M3(scenario_draft.py, 러프 시나리오 초안
5개)와는 독립적인 별개 경로다 — 지금은 M2 산출물을 직접 받는다.
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader, tool_chat
from generation.retrieval_pipeline.schemas import AdScenarioOutput


def _patch_product_meta(context: dict[str, Any], module0: dict[str, Any]) -> dict[str, Any]:
    """context.py 가 만든 context 는 product.name/usp_candidates 를 module0 의
    "productname"/"uspcandidates"(언더바 없음) 키로 찾는데, 실제 module0 키는
    "product_name"/"usp_candidates"(언더바 있음)라 항상 비어 나온다(M2에도 이미 있던 기존
    버그 — context.py 는 M2 에서도 쓰이므로 여기서 고치지 않고, 이 프롬프트에 한해 module0
    원본에서 다시 채워 넣는다)."""
    patched = json.loads(json.dumps(context, ensure_ascii=False))
    product = patched.setdefault("product", {})
    if not product.get("name"):
        product["name"] = module0.get("product_name", "")
    if not product.get("usp_candidates"):
        product["usp_candidates"] = [
            (u.get("text", "") if isinstance(u, dict) else u)
            for u in (module0.get("usp_candidates") or [])[:5]
        ]
    return patched


def build_prompt(context: dict[str, Any], devices: list[dict[str, Any]], creative_problem: str,
                 module0: dict[str, Any], ad_length: str, concept_line: str = "",
                 log_prefix: str = "default") -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system_template = prompt_loader.load("m4_common.md") + "\n\n---\n\n" + prompt_loader.load("m4_system.md")
    system = prompt_loader.fill(system_template, {"log_prefix": log_prefix})
    user_template = prompt_loader.load("m4_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line or "(제공되지 않음 — 아래 맥락에서 직접 도출하라)",
        "ad_length": ad_length,
        "creative_problem": creative_problem,
        "devices_json": json.dumps(devices, ensure_ascii=False, indent=2),
        "context_json": json.dumps(_patch_product_meta(context, module0), ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_scenario_generation(context: dict[str, Any], devices: list[dict[str, Any]], creative_problem: str,
                            module0: dict[str, Any], *, ad_length: str = "15초", concept_line: str = "",
                            backend: str = "cli", log_prefix: str = "default",
                            log_dir: str | None = None) -> tuple[AdScenarioOutput, dict[str, str]]:
    """프롬프트를 조립해 LLM(+선택적 도구)을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(context, devices, creative_problem, module0, ad_length, concept_line, log_prefix)
    raw = tool_chat.run(prompt["system"], prompt["user"], backend=backend,
                        log_prefix=log_prefix, log_dir=log_dir)
    if isinstance(raw, dict) and raw.get("error"):
        # M2(device_generation.py)와 동일한 이유로 조용히 빈 스키마로 흘려보내지 않는다 —
        # pydantic 결측 필드 기본값(빈 문자열/빈 배열)이 실패를 "씬 0개짜리 정상 결과"로
        # 둔갑시켜 다음 단계로 넘기는 것을 막는다.
        raise RuntimeError(f"M4(scenario_generation) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return AdScenarioOutput.model_validate(raw), prompt
