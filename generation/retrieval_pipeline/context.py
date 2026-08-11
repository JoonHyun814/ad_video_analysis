"""M0~M2 핸드오프(module0/m1/m2, 선택)와 M1 인사이트(m1_insight, 이 파이프라인의 새 M1)에서
M2 프롬프트에 넣을 압축 맥락을 뽑는다(build_context 를 쓰는 단계가 원래 이 파이프라인의
M3였다가 사용자 요청으로 M2 로 재번호됐다 — pipeline.py 모듈 docstring 참고).

module0/m1/m2 전체를 그대로 프롬프트에 붙이면 M2(컨셉 발산 다수)를 위해 설계된 필드까지
다 실려 불필요하게 길어진다 — M2가 실제로 참고하는 필드만 골라낸다(evaluation/ad_concept_production
/concept_prompt.py 가 같은 이유로 M1~M3 를 필요한 필드만 압축한 것과 같은 접근).
module0/m1/m2 필드 이름은 generation/v5_m0_m3/module0_ingest.py 반환 dict, modules_runner.py 의
M1(corejob/humantruth/target)·M2(positioningstatement/valueproposition/uniqueattributes) 출력과
정확히 일치해야 한다(이 M1/M2 는 legacy v5_m0_m3 모듈 번호이지 이 파이프라인의 M1/M2 가
아니다 — 이름이 겹치는 점에 주의).

module0/m1/m2(legacy, v5_m0_m3 M0~M2 재사용 경로)는 이제 전부 선택이다(사용자 요청 — "M2는
이제 m0_m2 말고 m1을 토대로 작동"). m1_insight(cli_m1.py 가 만드는 m1.json, product_insight.py
산출물)만으로도 M2를 돌릴 수 있어야 하므로, module0/m1/m2 가 비어 있으면 product.name/
category, insight.target_label 을 m1_insight 의 대응 필드로 채운다(둘 다 있으면 legacy 값을
우선한다 — 더 구조화된 소스이므로). legacy m1(JTBD 인사이트)과 m1_insight(제품·브랜드
인사이트)는 서로 다른 산출물이라 대체 관계가 아니라 보강 관계다.
"""
from __future__ import annotations

from typing import Any


def build_context(module0: dict[str, Any] | None = None, m1: dict[str, Any] | None = None,
                  m2: dict[str, Any] | None = None, *,
                  m1_insight: dict[str, Any] | None = None) -> dict[str, Any]:
    """M2 프롬프트({{context_json}})에 그대로 직렬화해 넣을 dict.

    module0/m1/m2 는 전부 생략 가능(legacy m0~m2 없이 m1_insight 만으로 호출 가능) — 생략 시
    빈 dict 로 취급한다.
    """
    module0 = module0 or {}
    m1 = m1 or {}
    m2 = m2 or {}
    m1_insight = m1_insight or {}
    humantruth = m1.get("humantruth") or {}
    target = m1.get("target") or {}
    context: dict[str, Any] = {
        "product": {
            "name": module0.get("productname", "") or m1_insight.get("product_name", ""),
            "brand": module0.get("brand", ""),
            "category": module0.get("category", "") or m1_insight.get("product_type", ""),
            "tone": module0.get("tone", ""),
            "facts": (module0.get("facts") or [])[:6],
            "usp_candidates": (module0.get("uspcandidates") or [])[:5],
        },
        "insight": {
            "core_job": m1.get("corejob", ""),
            "human_truth": humantruth.get("truth", ""),
            "human_truth_contradiction": humantruth.get("contradiction", ""),
            "target_label": target.get("label", "") or target.get("who", "") or m1_insight.get("target_group", ""),
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
