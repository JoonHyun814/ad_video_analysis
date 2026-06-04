"""브리프 기반 광고 시나리오 생성 (claude 백엔드)."""
import json

from utils.llm_caller import call_claude as _call_claude

_SCHEMA = (
    '{"title": "광고 제목", "brand": "브랜드/제품명", "concept": "광고 핵심 컨셉 한 줄",'
    ' "narrative": "전체 서사 흐름 요약",'
    ' "cast": [{"id": "캐릭터1", "description": "외모·인상·역할 묘사"}],'
    ' "scenes": [{"cut_index": 1, "time": "0.00~3.90s",'
    ' "beats": ['
    '{"type": "background", "description": "화면 구성·배경·공간 묘사"},'
    '{"type": "camera", "description": "카메라 앵글·무브먼트"},'
    '{"type": "action", "cast": "캐릭터1", "description": "동작·움직임 묘사"},'
    '{"type": "music", "description": "음악·사운드 묘사"},'
    '{"type": "dialogue", "cast": "캐릭터1", "description": "대사 내용"},'
    '{"type": "text_overlay", "description": "화면에 표시된 텍스트"}'
    ']}],'
    ' "key_messages": ["핵심 메시지"],'
    ' "production_notes": "재제작 시 참고할 연출·기술 특이사항"}'
)


def build_scenario_prompt(brief: dict) -> str:
    """브리프에서 시나리오 생성 프롬프트를 만든다."""
    brief_text = json.dumps(
        {k: v for k, v in brief.items() if not k.startswith("_")},
        ensure_ascii=False, indent=2
    )
    return (
        "너는 광고 시나리오 전문가다. 아래 광고 브리프를 바탕으로 15~30초 분량의 "
        "재제작 가능한 완전한 광고 시나리오를 JSON으로 작성해라.\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        "규칙:\n"
        "1. cast: 타겟 페르소나·포지셔닝에 맞는 모델을 직접 설정한다. "
        "동일 인물은 하나의 캐릭터 ID('캐릭터1', '캐릭터2' 등)로 통합한다.\n"
        "2. scenes[].beats: 각 컷 안의 시간 순 사건을 beat 단위로 나열한다.\n"
        "   - type=background: 배경·공간 변화 묘사\n"
        "   - type=camera: 카메라 앵글·무브먼트 묘사\n"
        "   - type=action: cast에 정의된 캐릭터 ID를 cast 필드에 적고 동작 묘사\n"
        "   - type=dialogue: 대사·나레이션, cast 필드에 캐릭터 ID\n"
        "   - type=music: 음악·사운드 묘사\n"
        "   - type=text_overlay: 화면에 표시된 텍스트. 없으면 beat 자체를 생략\n"
        "3. cast에 없는 캐릭터 ID를 beats에서 사용하지 않는다.\n"
        "4. 브리프의 USP·슬로건·타겟 페르소나·포지셔닝을 시나리오에 반드시 반영한다.\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def generate_scenario(brief: dict) -> dict:
    """브리프에서 시나리오를 생성한다 (claude 백엔드)."""
    return _call_claude(build_scenario_prompt(brief), timeout=600)



