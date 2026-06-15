"""M5 DR 스크립트 — L0 진단 → L1 컨테이너 → L2 엔진 → L3 스크립트 → L4 측정 → L5 컴플라이언스."""
import json

from utils.llm_dispatch import call_llm

_SCENE_BEAT = (
    '{"cut_index": 1, "time": "0.00~3.90s", "beats": ['
    '{"type": "background", "description": "배경·공간"},'
    '{"type": "camera", "description": "앵글·무브먼트"},'
    '{"type": "action", "cast": "캐릭터ID", "description": "동작"},'
    '{"type": "dialogue", "cast": "캐릭터ID", "description": "대사"},'
    '{"type": "music", "description": "음악·사운드"},'
    '{"type": "text_overlay", "description": "화면 텍스트"}'
    ']}'
)

_SCHEMA = (
    '{"concept_id": "선정된 컨셉 ID",'
    ' "l0_diagnosis": {'
    '   "schwartz_segment": "안전|권력|쾌락|성취|자극|보편|박애|순응 중 주요 1~2개",'
    '   "elaboration_level": "low | high",'
    '   "motivation_frame": "pain_relief | aspiration | social_proof | authority | curiosity"'
    ' },'
    ' "l1_container": {'
    '   "format": "ABCD",'
    '   "A_attention": "후크 — 첫 3초 어떻게 주의를 잡는가",'
    '   "B_brand": "브랜드 연결 — 언제·어떻게 브랜드를 심는가",'
    '   "C_call_to_action": "CTA 문구·방식",'
    '   "D_duration": "15s | 30s | 60s"'
    ' },'
    ' "l2_engine": {'
    '   "type": "PAS | AIDA | BAB | 4P | StoryBrand",'
    '   "rationale": "L0 진단에 근거한 엔진 선택 이유",'
    '   "structure": "선택한 엔진의 단계별 내용 한 줄씩"'
    ' },'
    ' "l3_script": {'
    '   "title": "광고 제목", "brand": "브랜드/제품명", "concept": "핵심 컨셉 한 줄",'
    '   "narrative": "전체 서사 흐름 요약",'
    '   "cast": [{"id": "캐릭터1", "description": "외모·인상·역할"}],'
    f'   "scenes": [{_SCENE_BEAT}],'
    '   "key_messages": ["핵심 메시지"],'
    '   "production_notes": "연출·기술 특이사항"'
    ' },'
    ' "l4_measurement": {'
    '   "hook_rate_hypothesis": "후크율 가설 — 어떤 요소가 이탈을 막는가",'
    '   "hold_rate_hypothesis": "시청 완료율 가설 — 어떤 서사 장치가 끝까지 붙잡는가",'
    '   "key_metrics": ["측정 지표 목록"]'
    ' },'
    ' "l5_compliance": ['
    '   {"check": "검토 항목", "status": "pass | flag", "note": "플래그 시 상세"}'
    ' ]}'
)


def _extract_concept(m3: dict, m4: dict) -> dict:
    """M3에서 M4가 선정한 첫 번째 컨셉 객체를 꺼낸다."""
    selected_ids: list = m4.get("selected", [])
    concepts: list = m3.get("concepts", [])
    if selected_ids and concepts:
        target_id = selected_ids[0]
        for c in concepts:
            if c.get("id") == target_id:
                return c
    return concepts[0] if concepts else {}


def build_prompt(brief: dict, m3: dict, m4: dict) -> str:
    """선정된 컨셉에서 M5 DR 스크립트 프롬프트를 만든다."""
    concept = _extract_concept(m3, m4)
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    concept_text = json.dumps(concept, ensure_ascii=False, indent=2)
    selected_ids = m4.get("selected", [])
    return (
        "너는 DR(Direct Response) 광고 스크립트 전문가다.\n"
        "선정된 컨셉을 실제 방영 가능한 스크립트로 조립한다.\n\n"
        "작성 순서 (이 순서를 지켜야 한다):\n"
        "1. l0_diagnosis: Schwartz 가치 세그먼트 진단 → 정교화 수준(ELM) → 동기 프레임 결정\n"
        "2. l1_container: ABCD 컨테이너 — A(후크)·B(브랜드)·C(CTA)·D(길이) 설계\n"
        "3. l2_engine: l0 진단에 근거해 설득 엔진(PAS/AIDA/BAB 등) 선택·이유 기술\n"
        "4. l3_script: l2 엔진 구조에 맞게 씬·비트 단위로 스크립트 작성 (15~30초 기준)\n"
        "   - cast에 없는 캐릭터 ID를 beats에서 사용하지 않는다\n"
        "   - text_overlay beat은 화면 텍스트가 있을 때만 포함\n"
        "5. l4_measurement: Hook Rate·Hold Rate 가설 및 측정 지표\n"
        "6. l5_compliance: 광고심의·플랫폼 정책·브랜드 가이드 체크리스트\n\n"
        f"concept_id는 '{selected_ids[0] if selected_ids else 'C1'}'로 설정.\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[선정 컨셉]\n{concept_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    m3: dict,
    m4: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """DR 스크립트(M5)를 생성한다."""
    return call_llm(build_prompt(brief, m3, m4), backend=backend, gemini_model=gemini_model, codex_model=codex_model, timeout=600)
