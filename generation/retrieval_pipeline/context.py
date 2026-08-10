"""M0~M2 핸드오프(module0/m1/m2)에서 M3 프롬프트에 넣을 압축 맥락을 뽑는다.

module0/m1/m2 전체를 그대로 프롬프트에 붙이면 M3(컨셉 발산 다수)를 위해 설계된 필드까지
다 실려 불필요하게 길어진다 — M3가 실제로 참고하는 필드만 골라낸다(evaluation/ad_concept_production
/concept_prompt.py 가 같은 이유로 M1~M3 를 필요한 필드만 압축한 것과 같은 접근).
module0/m1/m2 필드 이름은 generation/v5_m0_m3/module0_ingest.py 반환 dict, modules_runner.py 의
M1(corejob/humantruth/target)·M2(positioningstatement/valueproposition/uniqueattributes) 출력과
정확히 일치해야 한다.

m1_insight(선택)는 위 legacy m1(JTBD 인사이트)과 다른, 이 파이프라인 전용 새 M1
(product_insight.py, cli_m1.py 가 만드는 m1.json)의 산출물이다 — 제품 종류/외관/사용법/기능/
재료/브랜드 이미지/타겟/기타사항처럼 M3가 구체적인 연출 장치를 만들 때 쓸 수 있는 물리적·
사실적 근거를 담고 있다. 아직 이 새 M1은 legacy m1/m2 를 대체하지 않으므로(M2 는 그대로
legacy 경로를 쓴다) 별도 선택적 인자로만 얹는다 — cli_m3.py 의 --m1_input 이 없으면 기존과
동일하게 동작한다(하위호환).
"""
from __future__ import annotations

from typing import Any


def build_context(module0: dict[str, Any], m1: dict[str, Any], m2: dict[str, Any], *,
                  m1_insight: dict[str, Any] | None = None) -> dict[str, Any]:
    """M3 프롬프트({{context_json}})에 그대로 직렬화해 넣을 dict."""
    humantruth = m1.get("humantruth") or {}
    target = m1.get("target") or {}
    context: dict[str, Any] = {
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
    if m1_insight:
        context["product_insight"] = {
            "product_type": m1_insight.get("product_type", ""),
            "appearance": m1_insight.get("appearance", ""),
            "usage_scenarios": m1_insight.get("usage_scenarios") or [],
            "features": m1_insight.get("features") or [],
            "materials": m1_insight.get("materials") or [],
            "current_brand_image": m1_insight.get("current_brand_image", ""),
            "aspirational_brand_image": m1_insight.get("aspirational_brand_image", ""),
            "target_group": m1_insight.get("target_group", ""),
            "misc_notes": m1_insight.get("misc_notes") or [],
        }
    return context
