"""G6 — 선정 컨셉을 분석 파이프라인과 동일한 scenario_analysis 스키마의 시나리오로 작성한다.

출력이 pipeline/scenario_analysis.py 의 스키마와 같아, 생성 결과를 기존 평가·적재 도구
(evaluation.cli / concept_cli)에 그대로 통과시킬 수 있다.
"""
import json

from utils.llm_dispatch import call_llm

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
    ' "production_notes": "연출·기술 특이사항 (클리셰 결정 반영 방식 포함)"}'
)


def build_prompt(brief: dict, g1: dict, concept: dict, g3: dict, duration: float) -> str:
    """선정 컨셉 1개를 촬영 가능한 시나리오로 확장하는 프롬프트를 만든다."""
    direction = g3.get("creative_direction", "")
    return (
        "너는 광고 시나리오 전문가다. 아래 선정 컨셉을 실제 촬영 가능한 수준의 "
        "완전한 광고 시나리오로 작성해라.\n\n"
        "규칙:\n"
        f"1. 영상 길이는 {round(duration, 1)}초다. 컷당 1.5~4초 기준으로 scenes 를 나누고 "
        "time 은 '0.00~3.90s' 형식으로 전체 길이를 정확히 채운다.\n"
        "2. cast 에 정의하지 않은 캐릭터 ID 를 beats 에서 쓰지 않는다.\n"
        "3. 컨셉의 hook 은 반드시 첫 1~2컷 안에 구현한다.\n"
        "4. applied_decisions 의 avoid 패턴이 연출·소구에 스며들지 않게 하고, "
        "follow/subvert 패턴은 어느 컷에서 어떻게 구현했는지 production_notes 에 명시한다.\n"
        "5. text_overlay 는 실제 화면에 띄울 자막·카피만 담는다. 없으면 beat 를 생략한다.\n\n"
        f"[브리프]\n{json.dumps(brief, ensure_ascii=False, indent=2)}\n\n"
        f"[타겟 전략 (G1)]\n{json.dumps(g1, ensure_ascii=False, indent=2)}\n\n"
        f"[선정 컨셉 (G4)]\n{json.dumps(concept, ensure_ascii=False, indent=2)}\n\n"
        f"[크리에이티브 방향 (G3)]\n{direction}\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    g1: dict,
    concept: dict,
    g3: dict,
    duration: float = 30.0,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """선정 컨셉을 scenario_analysis 스키마 시나리오(G6)로 작성한다."""
    return call_llm(build_prompt(brief, g1, concept, g3, duration),
                    backend=backend, gemini_model=gemini_model, codex_model=codex_model, timeout=600)
