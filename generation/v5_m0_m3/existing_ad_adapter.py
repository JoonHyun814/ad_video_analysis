"""이미 분석된 기존 방영 광고(`data/ad_concept_production/<video_id>/`)를 v5_m0_m3
파이프라인의 입출력 스키마로 변환하는 브릿지.

사용자 요청(video_id 86/25 비교 실험)으로 추가됐다 — URL 크롤(M0) 대신, 이미
`evaluation.ad_concept_production` 이 만들어 둔 실제 방영 광고의 분석 결과를 그대로
재료로 쓴다. 두 모드를 지원한다.

  build_m0_m3(video_id)      — module0/m1/m2/m3 조립(LLM 미호출, 순수 데이터 매핑).
                                concept_analysis.json 의 m1/m2/m3 를 그대로 쓴다 —
                                이미 이 광고에서 "추출"된 값이라 다시 생성하지 않는다.
                                cli_m4_m9.py 입력으로 써서 M4~M9 전체 파이프라인을 돈다.
  build_direct_creative(...) — {m4,m5,m9} 1회 LLM 호출로 조립. M4~M9 재생성 없이 실제
                                scenario_analysis.json(컷·비트)을 그대로 스토리보드
                                스키마로 재구성만 한다("바로 생성" 비교군).

두 결과 모두 cli_storyboard.py 가 그대로 읽을 수 있는 모양이다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from generation.v5_m0_m3 import llm_adapter

_DEFAULT_DATA_ROOT = Path("data/ad_concept_production")


def _load(data_root: Path, video_id: int, name: str) -> dict[str, Any]:
    path = data_root / str(video_id) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{name}.json 없음: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_m0_m3(video_id: int, data_root: Path = _DEFAULT_DATA_ROOT) -> dict[str, Any]:
    """기존 광고 분석 3종(category/concept/production_analysis.json)에서 module0/m1/m2/m3 조립.

    m1/m2/m3 는 concept_analysis.json 값을 그대로 쓴다(이미 이 광고에서 추출된 값).
    module0(제품 사실)만 category_analysis.json + production_analysis.json 요약에서
    새로 구성한다 — module0_ingest.ingest() 가 URL 크롤로 만드는 것과 같은 모양이되
    출처는 "기존 방영 광고 분석"이다.
    """
    category = _load(data_root, video_id, "category_analysis")
    concept = _load(data_root, video_id, "concept_analysis")
    production = _load(data_root, video_id, "production_analysis")
    scenario = _load(data_root, video_id, "scenario_analysis")

    productname = category.get("brand_name") or scenario.get("brand") or ""
    facts = [m for m in (scenario.get("key_messages") or []) if isinstance(m, str)]
    if category.get("key_message"):
        facts.append(str(category["key_message"]))

    usp_texts = [
        t for t in (category.get("usp"), (production.get("profile") or {}).get("usp_summary"))
        if isinstance(t, str) and t.strip()
    ]
    uspcandidates = [
        {"text": t, "source": "existing_ad_analysis", "trust": "evidence"} for t in usp_texts
    ]

    target_persona = str(category.get("target_persona") or "").strip()
    module0: dict[str, Any] = {
        "productname": productname,
        "brand": "",
        "category": " / ".join(
            x for x in (category.get("industry_category"), category.get("product_category")) if x
        ),
        "producttype": "",
        "uspcandidates": uspcandidates,
        "facts": facts,
        "claimedfacts": [scenario["production_notes"]] if scenario.get("production_notes") else [],
        "targethints": [target_persona] if target_persona else [],
        "competitorcandidates": [],
        "tone": category.get("creative_style") or "",
        "visualmotifs": [],
        "brandlogourl": "",
        "sourceurl": f"internal://ad_video_analysis/data/ad_concept_production/{video_id}",
        "targetcandidate": {
            "who": target_persona,
            "aio": {"activities": "", "interests": "", "opinions": "", "lifestyle": ""},
            "note": "기존 방영 광고 분석(category_analysis.json)에서 가져온 타깃 서술 — [가설] 아님, "
                    "실제 집행된 광고의 타깃 정의. M1 확정값으로 그대로 신뢰 가능.",
        },
        "marketdefinitioncand": (
            f"[카테고리] {category.get('industry_category', '')}/{category.get('product_category', '')} "
            f"+ [직접·간접 경쟁대안] 조사 안 됨(기존 광고 분석 범위 밖) "
            f"+ [비소비 포함 전체 구매자 풀] — 기존 방영 광고 분석 기반, M1이 검증·확정"
        ),
    }

    return {
        "module0": module0,
        "m1": concept.get("m1") or {},
        "m2": concept.get("m2") or {},
        "m3": concept.get("m3") or {},
        "_meta": {"video_id": video_id, "source": "existing_ad_analysis", "mode": "m3_extract"},
    }


_DIRECT_SYSTEM = (
    "당신은 이미 방영된 실제 광고 1편의 분석 데이터를, 다른 파이프라인이 읽는 스토리보드 JSON "
    "스키마로 옮겨 적는 포맷 변환기다. 창작·재해석·개선을 하지 마라 — 주어진 컷·비트·연출 요소를 "
    "빠짐없이 그대로 요약해 스키마 필드에 채워 넣기만 한다(사실 재구성/포맷 변환, 새 컨셉 발산 아님). "
    "장면 수·순서·핵심 대사·혜택 숫자·브랜드명은 입력과 정확히 일치해야 한다. 입력에 없는 세부는 "
    "지어내지 말고 비워두거나 관찰 가능한 범위에서만 합리적으로 요약하라. 오직 JSON 객체 하나로만 "
    "응답하라."
)

_DIRECT_SCHEMA = {
    "m4": {
        "selected": [{"concept": "m3 concepts[0].name 그대로", "onesentence": "m3 concepts[0].bigidea 요약"}],
    },
    "m5": {
        "hook": "이 광고의 실제 오프닝 훅 1문장",
        "toneregister": "이 광고의 실제 톤(예: 코믹/진지/데드팬 등, production_analysis tone_register 참고)",
        "engine": "PAS|AIDA|BAB|Demo|Story|4Ps|SocialProof|UniqueMechanism|FAB 중 이 광고에 가장 맞는 것",
        "narrativeform": "미니드라마|비네트|대조|열거|반전|원샷|POV|모큐멘터리|은유세계|데모스펙터클|부조리|일상몽타주 중 하나",
        "cta": {"text": "이 광고의 실제 CTA/엔딩 카피(없으면 빈 문자열)", "action": "이 광고의 실제 행동 유도(없으면 빈 문자열)"},
    },
    "m9": {
        "scenes": [{
            "no": 1, "time": "0~3초(scenario_analysis 의 cut_index/time 그대로 매핑)",
            "role": "story|ending",
            "brief": "이 컷에서 실제로 벌어지는 일 1문장(~40자, 촬영 전문용어 금지)",
            "mood": "이 컷의 실제 음악/분위기(beats의 music 비트 참고)",
            "shot": "CU|MS|WS+무브(beats의 camera 비트에서 그대로 읽어 요약)",
            "visual": "이 컷의 실제 화면 묘사(beats의 background/action 비트 요약, 지어내지 말 것)",
            "audio": "이 컷의 실제 대사/내레이션/SFX(beats의 dialogue/music 비트 그대로)",
            "overlay": "이 컷의 실제 화면 텍스트(beats의 text_overlay 비트 그대로)",
            "emotion": "", "color": "", "transition": "컷",
            "shots": [],
        }],
        "emotioncurve": "scenario_analysis 전체 흐름에서 관찰되는 감정 곡선 요약",
        "visualkeywords": ["이 광고의 실제 핵심 비주얼 키워드"],
        "usagecutscene": "제품을 실제로 사용/제시하는 컷 번호(정수, scenario_analysis 기준)",
    },
}


def build_direct_creative(video_id: int, data_root: Path = _DEFAULT_DATA_ROOT) -> dict[str, Any]:
    """M4~M9 재생성 없이, 실제 scenario_analysis.json 을 1회 LLM 호출로 스토리보드 스키마에
    맞춰 재구성한다("바로 생성" 비교군). llm_adapter.set_backend() 를 먼저 호출해 둘 것.
    """
    concept = _load(data_root, video_id, "concept_analysis")
    production = _load(data_root, video_id, "production_analysis")
    scenario = _load(data_root, video_id, "scenario_analysis")

    m3 = concept.get("m3") or {}
    concepts = [c for c in (m3.get("concepts") or []) if isinstance(c, dict)]
    selected_name = concepts[0].get("name", "") if concepts else scenario.get("title", "")

    source = {
        "selected_concept_name": selected_name,
        "selected_concept_bigidea": concepts[0].get("bigidea", "") if concepts else scenario.get("concept", ""),
        "scenario_analysis": scenario,
        "production_elements": [
            e for e in (production.get("elements") or [])
            if isinstance(e, dict) and e.get("element_type") in (
                "narrative_pattern", "tone_register", "cta_device", "opening_hook", "persuasion_engine",
            )
        ],
    }
    user = (
        json.dumps(source, ensure_ascii=False)
        + "\n\n위 실제 광고 데이터를 아래 JSON 스키마 그대로(필드 구조 유지, scenes 배열은 "
          "scenario_analysis.scenes 개수만큼) 채워 그 JSON 객체 하나로만 응답하라:\n"
        + json.dumps(_DIRECT_SCHEMA, ensure_ascii=False)
    )
    out = llm_adapter.chat_json(_DIRECT_SYSTEM, user, stage="M9:direct_from_scenario_analysis")
    if not isinstance(out, dict) or out.get("error") or not all(k in out for k in ("m4", "m5", "m9")):
        raise RuntimeError(f"direct creative 변환 실패(LLM 응답 불충분): {out!r}")

    return {
        "m3": m3,
        "m4": out["m4"],
        "m5": out["m5"],
        "m9": out["m9"],
        "gates": {"a": "direct", "b": "direct", "c": "direct"},
        "_meta": {"video_id": video_id, "source": "existing_ad_analysis", "mode": "direct_from_scenario_analysis"},
    }
