"""M5 — M4가 완성한 광고 시나리오(cast/scenes)를 스토리보드 이미지 슬롯 계획 + Seedance 영상
모션 프롬프트로 전환한다. device_generation.py(M3)·scenario_generation.py(M4)와 같은 패턴 —
LLM 호출 1회, search_chromadb 도구는 필요 없다(이 단계는 이미 완성된 시나리오를 이미지/영상
생성 지시문으로 옮기는 작업이라 근거 검색 대상이 아니다). system/user 프롬프트 문구는 전부
prompts/m5_*.md 에 있다(이 파일은 프롬프트 조립·LLM 호출·파싱만 한다).

이 단계의 산출물(StoryboardShotPlan)은 이미지를 생성하지 않는다 — 실제 이미지 소싱/생성은
storyboard_codex.py(Codex CLI, 별도 실행)가, 영상 생성은 Seedance가 이 계획을 받아 수행한다.
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader, tool_chat
from generation.retrieval_pipeline.schemas import StoryboardShotPlan

_SCENARIO_FIELDS = ("title", "brand", "concept", "narrative", "cast", "scenes",
                    "key_messages", "production_notes")


def _product_context(module0: dict[str, Any]) -> dict[str, Any]:
    """module0 원본에서 M5 프롬프트에 필요한 필드만 압축한다(context.py의 product 필드와
    같은 목적이지만, context.py는 module0 실제 키(product_name/usp_candidates, 언더바 있음)와
    어긋난 이름으로 찾아 항상 비어 나오는 기존 버그가 있다 — scenario_generation.py의
    _patch_product_meta와 같은 이유로 여기서도 module0에서 직접 다시 채운다)."""
    return {
        "name": module0.get("product_name", ""),
        "category": module0.get("category", ""),
        "tone": module0.get("tone", ""),
        "facts": (module0.get("facts") or [])[:6],
        "usp_candidates": [
            (u.get("text", "") if isinstance(u, dict) else u)
            for u in (module0.get("usp_candidates") or [])[:5]
        ],
        "product_image_url": module0.get("product_image_url", ""),
    }


def scenario_fields(m4_result: dict[str, Any]) -> dict[str, Any]:
    """m4.json(=pipeline.run_m4 반환값)에서 M5 프롬프트에 필요한 시나리오 필드만 뽑는다 —
    devices_applied 나 M0~M4 체이닝 메타데이터(module0~devices/prompt)는 다시 넣지 않는다
    (cli_m5.py가 이 함수로 만든 dict를 그대로 run_m5()에 넘긴다)."""
    return {k: m4_result.get(k) for k in _SCENARIO_FIELDS}


def build_prompt(scenario: dict[str, Any], module0: dict[str, Any]) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("m5_common.md") + "\n\n---\n\n" + prompt_loader.load("m5_system.md")
    user_template = prompt_loader.load("m5_user.md")
    user = prompt_loader.fill(user_template, {
        "scenario_json": json.dumps(scenario, ensure_ascii=False, indent=2),
        "product_json": json.dumps(_product_context(module0), ensure_ascii=False, indent=2),
    })
    return {"system": system, "user": user}


def run_storyboard_generation(scenario: dict[str, Any], module0: dict[str, Any], *, backend: str = "cli",
                              log_prefix: str = "default", log_dir: str | None = None
                              ) -> tuple[StoryboardShotPlan, dict[str, str]]:
    """프롬프트를 조립해 LLM을 호출하고 (파싱된 계획, 실제 전송한 프롬프트) 를 반환한다."""
    prompt = build_prompt(scenario, module0)
    raw = tool_chat.run(prompt["system"], prompt["user"], backend=backend,
                        log_prefix=log_prefix, log_dir=log_dir)
    if isinstance(raw, dict) and raw.get("error"):
        # M3·M4와 동일한 이유로 조용히 빈 스키마로 흘려보내지 않는다 — pydantic 결측 필드
        # 기본값(빈 문자열/빈 배열)이 실패를 "계획 0개짜리 정상 결과"로 둔갑시키는 것을 막는다.
        raise RuntimeError(f"M5(storyboard_generation) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return StoryboardShotPlan.model_validate(raw), prompt
