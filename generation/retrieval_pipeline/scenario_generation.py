"""M4 — M3가 만든 러프 시나리오 초안(drafts[]) 중 사용자가 고른 하나를 받아, 최소 5개 컷으로
구성된 광고 전체 시나리오(cast/scenes/key_messages/production_notes)로 정교화한다(사용자
요청 — "m3의 drafts 리스트 중 하나를 정해서 입력으로 넣으면 ... 컷별 화면구성, 동적 연출,
대사, 나레이션, 자막, 사운드가 들어간 5개 이상의 컷으로 구성된 결과"). device_generation.py
(M2)와 같은 패턴 — LLM 호출 1회, 그 안에서 `search_chromadb` 도구 왕복은 선택적으로 여러 번
(컷 구성·페이싱 참고용, 장치 자체의 근거는 이미 M2에서 끝난 일이라 의무는 아니다). system/
user 프롬프트 문구는 전부 prompts/m4_*.md 에 있다(이 파일은 프롬프트 조립·LLM 호출·파싱만
한다).

draft(선택된 M3 초안)가 없으면(레거시 호출 등) devices[] 8개 전체에서 자유롭게 골라 조합하는
이전 동작으로 폴백한다 — prompts/m4_system.md 의 조건부 지시 참고.

M1 인사이트는 context.product_insight(M2가 --m1_input 을 받았다면 이미 들어있다)를 통해
전달된다 — 이 파일이 별도로 다시 불러오지 않는다(context 가 이미 그 압축본을 담고 있으므로
중복 경로를 만들지 않는다).
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
                 module0: dict[str, Any], draft: dict[str, Any] | None, ad_length: str,
                 concept_line: str = "", log_prefix: str = "default") -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system_template = prompt_loader.load("m4_common.md") + "\n\n---\n\n" + prompt_loader.load("m4_system.md")
    system = prompt_loader.fill(system_template, {"log_prefix": log_prefix})
    user_template = prompt_loader.load("m4_user.md")
    user = prompt_loader.fill(user_template, {
        "concept_line": concept_line or "(제공되지 않음 — 아래 맥락에서 직접 도출하라)",
        "ad_length": ad_length,
        "creative_problem": creative_problem,
        "devices_json": json.dumps(devices, ensure_ascii=False, indent=2),
        "draft_json": json.dumps(draft, ensure_ascii=False, indent=2) if draft else "(제공되지 않음 — devices[] 중 자유롭게 골라 조합하라)",
        "context_json": json.dumps(_patch_product_meta(context, module0), ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_scenario_generation(context: dict[str, Any], devices: list[dict[str, Any]], creative_problem: str,
                            module0: dict[str, Any], draft: dict[str, Any] | None = None, *,
                            ad_length: str = "15초", concept_line: str = "", backend: str = "cli",
                            log_prefix: str = "default", log_dir: str | None = None
                            ) -> tuple[AdScenarioOutput, dict[str, str]]:
    """프롬프트를 조립해 LLM(+선택적 도구)을 호출하고 (파싱된 결과, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(context, devices, creative_problem, module0, draft, ad_length, concept_line, log_prefix)
    raw = tool_chat.run(prompt["system"], prompt["user"], backend=backend,
                        log_prefix=log_prefix, log_dir=log_dir)
    if isinstance(raw, dict) and raw.get("error"):
        # M2(device_generation.py)와 동일한 이유로 조용히 빈 스키마로 흘려보내지 않는다 —
        # pydantic 결측 필드 기본값(빈 문자열/빈 배열)이 실패를 "씬 0개짜리 정상 결과"로
        # 둔갑시켜 다음 단계로 넘기는 것을 막는다.
        raise RuntimeError(f"M4(scenario_generation) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return AdScenarioOutput.model_validate(raw), prompt
