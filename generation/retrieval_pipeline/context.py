"""M0~M2 핸드오프(module0/m1/m2)에서 M4 프롬프트에 넣을 압축 맥락을 뽑는다.

module0/m1/m2 전체를 그대로 프롬프트에 붙이면 M3(컨셉 발산 다수)를 위해 설계된 필드까지
다 실려 불필요하게 길어진다 — M4가 실제로 참고하는 필드만 골라낸다(evaluation/ad_concept_production
/concept_prompt.py 가 같은 이유로 M1~M3 를 필요한 필드만 압축한 것과 같은 접근).
필드 이름은 generation/v5_m0_m3/module0_ingest.py 반환 dict, modules_runner.py 의
M1(corejob/humantruth/target)·M2(positioningstatement/valueproposition/uniqueattributes) 출력과
정확히 일치해야 한다.
"""
from __future__ import annotations

from typing import Any


def build_context(module0: dict[str, Any], m1: dict[str, Any], m2: dict[str, Any]) -> dict[str, Any]:
    """M4 프롬프트({{context_json}})에 그대로 직렬화해 넣을 dict."""
    humantruth = m1.get("humantruth") or {}
    target = m1.get("target") or {}
    return {
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
