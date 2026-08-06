"""M0~M2 핸드오프(module0/m1/m2)에서 M3~M7 프롬프트에 넣을 압축 맥락을 뽑는다.

module0/m1/m2 는 이 파이프라인 전용 독립 구현(module0.py/module1.py/module2.py, 사용자 요청 —
"m0-m2 를 v5_m0_m3 거를 import 하는게 아니라 독립적으로")이 만든 snake_case dict라, 이미 M3~M7가
참고할 필드만 담고 있어 v5_m0_m3 때처럼 무거운 압축이 필요하지 않다 — 여기서는 최상위 3단
구조(product/insight/positioning)로 재구성하고 usp_candidates/facts 를 상위 N개로만 자른다.

`brand_guideline`: module0.py 가 --guideline 원문을 module0["guideline_text"] 에 그대로 담아
둔다(M0 자체가 이미 가이드라인을 1차 소스로 쓰지만, M4~M7 은 M0가 구조화하며 놓쳤을 수 있는
구체적 표현·예시 장면을 원문에서 직접 볼 수 있어야 한다는 사용자 요청). context 는 M3~M7 모든
단계의 프롬프트에 {{context_json}} 으로 들어가므로, 이 한 곳만 채우면 별도 CLI 옵션 없이 자동
전파된다. 각 단계 시스템 프롬프트(prompts/common.md, prompts/m3_*.md)가 "brand_guideline 이
있으면 다른 지시보다 우선한다"고 명시한다.
"""
from __future__ import annotations

from typing import Any


def build_context(module0: dict[str, Any], m1: dict[str, Any], m2: dict[str, Any]) -> dict[str, Any]:
    """M3~M7 프롬프트({{context_json}})에 그대로 직렬화해 넣을 dict."""
    return {
        "brand_guideline": module0.get("guideline_text", ""),
        "product": {
            "name": module0.get("product_name", ""),
            "brand": module0.get("brand", ""),
            "category": module0.get("category", ""),
            "product_image_url": module0.get("product_image_url", ""),
            "tone": module0.get("tone", ""),
            "facts": (module0.get("facts") or [])[:6],
            "usp_candidates": (module0.get("usp_candidates") or [])[:5],
        },
        "insight": {
            "core_job": m1.get("core_job", ""),
            "human_truth": m1.get("human_truth", ""),
            "human_truth_contradiction": m1.get("human_truth_contradiction", ""),
            "target_label": m1.get("target_label", ""),
        },
        "positioning": {
            "positioning_statement": m2.get("positioning_statement", ""),
            "value_proposition": m2.get("value_proposition", ""),
            "unique_attributes": (m2.get("unique_attributes") or [])[:5],
        },
    }
