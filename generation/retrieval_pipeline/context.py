"""M0~M2 핸드오프(module0/m1/m2)에서 M3~M7 프롬프트에 넣을 압축 맥락을 뽑는다.

module0/m1/m2 전체를 그대로 프롬프트에 붙이면 M3(컨셉 발산 다수)를 위해 설계된 필드까지
다 실려 불필요하게 길어진다 — M3~M7가 실제로 참고하는 필드만 골라낸다(evaluation/ad_concept_production
/concept_prompt.py 가 같은 이유로 M1~M3 를 필요한 필드만 압축한 것과 같은 접근).
필드 이름은 generation/v5_m0_m3/module0_ingest.py 반환 dict, modules_runner.py 의
M1(corejob/humantruth/target)·M2(positioningstatement/valueproposition/uniqueattributes) 출력과
정확히 일치해야 한다.

`brand_guideline`: cli.py --guideline 로 지정한 브랜드 가이드라인 md 는 v5_m0_m3.modules_runner
가 module0["brandguideline"] 에 저장해 M1·M2 시스템 프롬프트에 최우선 지시로 삽입한다(M1·M2
전용). 이 파이프라인은 M3~M7 도 같은 가이드라인을 계속 참조할 수 있어야 한다는 사용자 요청에
따라, module0 에 이미 저장된 그 값을 여기서 context 로 실어 나른다 — context 는 M3~M7 모든
단계의 프롬프트에 {{context_json}} 으로 들어가므로, 이 한 곳만 고치면 별도 CLI 옵션 없이
자동으로 전 단계에 전파된다. 각 단계 시스템 프롬프트(prompts/common.md, prompts/m3_*.md)가
"brand_guideline 이 있으면 다른 지시보다 우선한다"고 명시한다.
"""
from __future__ import annotations

from typing import Any


def build_context(module0: dict[str, Any], m1: dict[str, Any], m2: dict[str, Any]) -> dict[str, Any]:
    """M3~M7 프롬프트({{context_json}})에 그대로 직렬화해 넣을 dict."""
    humantruth = m1.get("humantruth") or {}
    target = m1.get("target") or {}
    return {
        "brand_guideline": str(module0.get("brandguideline") or "").strip(),
        "product": {
            "name": module0.get("productname", ""),
            "brand": module0.get("brand", ""),
            "category": module0.get("category", ""),
            "tone": module0.get("tone", ""),
            "facts": (module0.get("facts") or [])[:6],
            "usp_candidates": (module0.get("uspcandidates") or [])[:5],
        },
        "insight": {
            "core_job": m1.get("corejob", ""),
            "human_truth": humantruth.get("truth", ""),
            "human_truth_contradiction": humantruth.get("contradiction", ""),
            "target_label": target.get("label", "") or target.get("who", ""),
        },
        "positioning": {
            "positioning_statement": m2.get("positioningstatement", ""),
            "value_proposition": m2.get("valueproposition", ""),
            "unique_attributes": (m2.get("uniqueattributes") or [])[:5],
        },
    }
