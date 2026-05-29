"""scenario_analysis 결과를 DB 저장용 parsed 구조로 정제한다 (claude 백엔드)."""
import json
from utils.json_utils import parse_json as _parse_json
from utils.llm_caller import call_claude

from pipeline.cuts import Cut
from pipeline.scenario_analysis import _summarize_audio

_SCHEMA_VERSION = "pipeline_v1"

_ENUMS = (
    "[허용 값 — 반드시 아래 값만 사용]\n"
    "narrative_type: NARRATIVE|NON_NARRATIVE\n"
    "narrative_structure: problem_agitation_solution|before_after_bridge|testimonial_arc|hook_body_close|functional_appeal|non_narrative\n"
    "creative_style: problem_solution|emotional_story|product_showcase|testimonial|comparison|humor|educational|lifestyle|event_promo|brand_film|ugc_style|emotional_appeal|storytelling\n"
    "hook_technique: question|shock|empathy|visual_impact|statement|story|no_hook|direct_benefit|celebrity_appearance|visual_surprise|social_proof_opening|problem_dramatization\n"
    "skip_resistance: curiosity_gap|immediate_value|emotional_hook|pattern_interrupt|social_proof|fear_of_missing\n"
    "voiceover_type: narrator|character|character_voice|none\n"
    "voiceover_tone: conversational|authoritative|warm|energetic|playful|informative|comedic\n"
    "music_role: background_mood|narrative_driver|rhythm_driver|emotional_peak|brand_signature|none\n"
    "music_tempo: slow|moderate|fast|upbeat|variable|none\n"
    "close_type: brand_emotion|conversion_heavy|promo_driven|product_showcase|app_download|minimal_logo\n"
    "end_card_elements(배열): logo|cta_text|app_badge|tagline|promo_text|qr_code|product_image\n"
    "cta_type: app_download_badge|qr_code|url_visit|phone_call|store_visit|custom|null\n"
    "narrative_role: HOOK|ESTABLISH_CONTEXT|PROBLEM|SOLUTION|FEATURE|PROOF|EXPERIENCE|OUTCOME|PROMO|CTA|EMOTIONAL_APPEAL|VISUAL_FILLER|BRAND\n"
    "sequence_label: hook|body|close\n"
    "intent: provoke_curiosity|create_urgency|build_trust|demonstrate_value|evoke_aspiration|deliver_information|drive_action|reinforce_brand\n"
    "delivery: voice_only|text_only|voice_and_text|visual_only\n"
    "brand_assets(배열): product|logo|app_ui|brand_icon|brand_character|packaging\n"
    "location: indoor|outdoor|studio|cgi|mixed\n"
    "subject: person|product|object|environment|person_with_product|abstract|text_graphic\n"
    "campaign_objective: awareness|consideration|conversion|retention|app_install|traffic\n"
    "industry_category: food_beverage|beauty_cosmetics|fashion_apparel|tech_electronics|finance_insurance|retail_ecommerce|health_wellness|automotive|travel_hospitality|education|real_estate|gaming_entertainment|telecom\n"
    "target_gender: male|female|all\n"
    "placement: ctv_6s|ctv_15s|ctv_30s|ctv_60s"
)

_OUT_TEMPLATE = json.dumps({
    "narrative_classification": {"narrative_type": "NARRATIVE|NON_NARRATIVE", "confidence": 0.0, "reasoning": "..."},
    "overall_strategy": {
        "narrative_structure": "...", "creative_style": "...",
        "hook_strategy": {
            "technique": "...", "skip_resistance_strategy": "...",
            "opening_device": "...", "first_frame_element": "...",
            "speech_in_first_scene": False, "text_in_first_scene": False, "brand_in_first_scene": False,
        },
        "audio_visual_strategy": {
            "voiceover_type": "...", "voiceover_tone": "...",
            "music_role": "...", "music_tempo": "...", "text_carries_primary_message": False,
        },
        "close_strategy": {"close_type": "...", "end_card_elements": ["..."], "cta_type": None, "promo_info": None},
        "tagline": None,
        "message_hierarchy": {"primary_message": "...", "supporting_messages": ["..."], "message_repetition_count": 0},
    },
    "sequences": [{"sequence_id": 1, "sequence_label": "hook|body|close", "start_sec": 0.0, "end_sec": 0.0, "intent": "...", "num_cuts": 0, "delivery": "...", "brand_visible": False, "product_visible": False}],
    "cuts": [{"cut_id": 1, "sequence_id": 1, "start_sec": 0.0, "end_sec": 0.0, "role": "...", "plot": "...", "narration": None, "text": None, "brand_visible": False, "product_visible": False, "brand_assets": []}],
    "key_scenes": [{"start_sec": 0.0, "end_sec": 0.0, "location": "...", "subject": "...", "key_scene_describe": "..."}],
    "role_sequence": "HOOK,ESTABLISH_CONTEXT,...",
    "narrative_summary": "...",
    "step1_has_problem": False,
    "step2_has_review": False,
    "brief": {"campaign_objective": "...", "industry_category": "...", "brand_name": "...", "target_gender": "...", "target_age_range": "25-44", "target_interest": ["..."], "placement": "...", "key_message": "..."},
}, ensure_ascii=False, indent=2)


def build_prompt(
    scenario: dict,
    cuts: list[Cut],
    cut_analysis: list[dict],
    scene_analysis: list[dict],
    stt_segments: list[dict],
    audio_data: dict | None,
) -> str:
    """3개 백엔드가 공통으로 사용하는 프롬프트를 생성한다."""
    n_cuts = len([c for c in cut_analysis if not c.get("error")])
    context = _build_context(scenario, cuts, cut_analysis, scene_analysis, stt_segments, audio_data)
    return (
        "광고 분석 데이터를 보고 DB 저장용 JSON을 생성하라. 첫 글자는 반드시 '{'. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        "규칙:\n"
        f"1. cuts: 컷별 분석의 모든 컷 {n_cuts}개를 포함. cut_id는 cut_index와 일치.\n"
        "2. sequences: 컷들을 hook/body/close로 묶어 3~5개 생성. sequence_id는 1부터.\n"
        "3. cuts[].sequence_id는 해당 컷이 속한 sequences[].sequence_id와 일치.\n"
        "4. role_sequence: cuts[].role을 컷 순서대로 콤마로 나열.\n"
        "5. key_scenes: 광고에서 가장 중요한 장면 2~4개만 선정.\n"
        "6. step1_has_problem: 문제 상황 제시 컷 존재 여부. step2_has_review: 사용 후기·증언 컷 존재 여부.\n"
        "7. 모든 enum 필드는 [허용 값] 목록에서만 선택.\n\n"
        f"{_ENUMS}\n\n"
        f"{context}\n\n"
        "아래 JSON 구조를 실제 내용으로 채워 출력하라 (플레이스홀더 문자 그대로 출력 금지):\n"
        f"{_OUT_TEMPLATE}"
    )


def _build_context(
    scenario: dict,
    cuts: list[Cut],
    cut_analysis: list[dict],
    scene_analysis: list[dict],
    stt_segments: list[dict],
    audio_data: dict | None,
) -> str:
    parts: list[str] = []

    if scenario and not scenario.get("error"):
        sc_lines = []
        for key, label in [("brand", "브랜드"), ("title", "제목"), ("concept", "컨셉"), ("narrative", "서사")]:
            if scenario.get(key):
                sc_lines.append(f"{label}: {scenario[key]}")
        if scenario.get("key_messages"):
            msgs = scenario["key_messages"]
            sc_lines.append("핵심메시지: " + (" / ".join(msgs) if isinstance(msgs, list) else msgs))
        if sc_lines:
            parts.append("[시나리오]\n" + "\n".join(sc_lines))

    if cut_analysis:
        lines = []
        for c in cut_analysis:
            if c.get("error"):
                continue
            line = f"컷{c['cut_index']} ({c['start_sec']:.2f}~{c['end_sec']:.2f}s): {c.get('flow', '')}"
            if c.get("cast") and c["cast"] not in ("없음", "none"):
                line += f" | 인물: {c['cast']}"
            if c.get("text_flow") and c["text_flow"] not in ("없음", "none", "없음."):
                line += f" | 텍스트: {c['text_flow']}"
            lines.append(line)
        if lines:
            parts.append(f"[컷별 분석 ({len(lines)}개)]\n" + "\n".join(lines))

    if scene_analysis:
        s0 = scene_analysis[0]
        desc = " / ".join(v for k in ("foreground", "background", "mood") if (v := s0.get(k)))
        if desc:
            parts.append(f"[첫 컷 비주얼]\n{desc}")

    if stt_segments:
        stt = " / ".join(f'{s["start_sec"]:.1f}s: "{s["text"]}"' for s in stt_segments[:20])
        parts.append(f"[STT]\n{stt}")

    if audio_data:
        summary = _summarize_audio(audio_data)
        if summary:
            parts.append(f"[오디오]\n{summary}")

    return "\n\n".join(parts)


def analyze_parsed(
    scenario: dict,
    cuts: list[Cut],
    cut_analysis: list[dict],
    scene_analysis: list[dict],
    stt_segments: list[dict],
    audio_data: dict | None,
    llm_model: str = "claude-sonnet-4-6",
) -> dict:
    """claude -p 로 parsed 구조를 생성한다."""
    prompt = build_prompt(scenario, cuts, cut_analysis, scene_analysis, stt_segments, audio_data)
    result = _call_claude(prompt)
    _inject_meta(result, cuts, llm_model)
    return result


def _inject_meta(result: dict, cuts: list[Cut], model: str) -> None:
    """LLM 출력에 프로그래매틱으로 결정되는 필드를 추가한다."""
    result.setdefault("ad_id", "")
    result["duration"] = round(max((c.end_sec for c in cuts), default=0.0), 3)
    result["schema_version"] = _SCHEMA_VERSION
    result["pipeline_inputs"] = {"model": model, "transnet_threshold": None, "stt_model": None, "max_cuts": None}
    nc = result.get("narrative_classification", {})
    result.setdefault("narrative_type", nc.get("narrative_type"))
    result.setdefault("confidence", nc.get("confidence"))
    result.setdefault("narrative_structure", result.get("overall_strategy", {}).get("narrative_structure"))


def _call_claude(prompt: str) -> dict:
    return call_claude(prompt, timeout=600)

