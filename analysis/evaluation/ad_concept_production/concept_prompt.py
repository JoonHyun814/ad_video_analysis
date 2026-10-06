"""scenario_analysis.json → ad_concept_reference 용 컨셉 인사이트를 1회 호출로 역추출한다.

evaluation/strategy(M1→M2→M3 3단계 순차 호출)와는 별개의 새 프롬프트다 — ad_concept_reference
가 실제로 쓰는 필드(corejob·humantruth·valueproposition·lens·bigidea·provingwhy·job·
differentiation·claimtag·risk)만 추리면 3단계로 나눌 필요가 없어, 지연시간·비용을 줄이는
단일 호출로 재설계했다. 출력 모양은 evaluation/concept/concept_reference_store.py 가 그대로
소비할 수 있도록 {"m1":{...},"m2":{...},"m3":{"concepts":[...]}} 형태를 유지한다.
"""
import json

_LENS_POOL = (
    "반전·금기 깨기", "비유·은유", "데모·증거", "적(현상유지) 의인화", "사용자 증언",
    "정체성·소속", "기능적 Job 직격", "감정적 Job 직격", "비교·대조",
)

_SYSTEM = (
    "너는 DR-CTV(직접 반응형 커넥티드 TV) 영상 광고 전략 분석 전문가다.\n"
    "아래 [시나리오]는 이미 완성된 광고다. 이 광고가 기획될 당시 산출됐을 전략의 핵심만 역추론하라.\n\n"
    "[규칙]\n"
    "- 역추론은 창작이 아니다: 시나리오에 실제 등장하는 장면·대사·자막·연출과 부합하는 내용만 채운다.\n"
    "  이 광고에 없는 새 인사이트·메시지·컨셉을 지어내지 않는다.\n"
    "- 서술 어투는 광고 제작 '전에' 쓰인 전략 문서처럼 쓴다 — '이 광고는/영상을 보니/시나리오에서/\n"
    "  N번째 컷에서' 같은 분석·관찰 어투와 컷 번호 언급을 쓰지 않는다. 내용은 실제 광고와\n"
    "  부합하되 문장은 전략을 제안하는 형식이어야 한다.\n"
    "- humantruth: JTBD(Jobs to be Done) 관점에서 이 광고가 딛고 선 인간 진실 1문장 — 구체적이고,\n"
    "  미리 다 알려진 뻔한 말이 아니며, 내부에 모순(예: 알면서도 반복하는 습관)을 담아야 한다.\n"
    "- valueproposition: 이 광고가 실제로 약속하는 가치를 고객 언어 1문장으로, 광고 카피에 접지해 쓴다.\n"
    f"- lens: 아래 9개 전략 렌즈 풀에서 이 광고가 실제 쓴 것 1개를 정확히 그대로 옮겨 적는다(신규 렌즈 창작 금지):\n"
    f"  {' / '.join(_LENS_POOL)}\n"
    "- claimtag: 이 광고가 실제 의존한 근거 수준 — C0(효능 주장 없이 성립) / C1(범위 내 사실 언급 의존) /\n"
    "  C2(우월성·효능 단정 의존) 중 하나.\n"
    "- bigidea·provingwhy·job·differentiation·risk 는 컨셉을 제안하는 전략 문서 어투로,\n"
    "  실제 광고 내용과 부합하게 서술한다.\n"
    "  · provingwhy: valueproposition 을 이 컨셉이 어떻게 증명하는지 결과 표현으로 1문장.\n"
    "  · job: 이 컨셉이 충족하는 고객의 Job(기능적/감정적) 1문장.\n"
    "  · differentiation: 경쟁 관습·카테고리 문법 대비 무엇으로 차별화하는지 1문장.\n"
    "  · risk: 이 컨셉이 안고 가는 리스크 1문장.\n"
    "- 관찰로 확인 불가한 내용은 빈 문자열로 남긴다. 스키마의 키를 그대로 쓰고 새 키를 만들지 않는다.\n"
    "- 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n"
)

_SCHEMA = {
    "m1": {
        "corejob": "이 광고가 실제 다루는 고객의 핵심 Job 1문장(동사+목적어+맥락, 고객 언어)",
        "humantruth": {
            "truth": "광고 연출·대사가 실제로 딛고 선 구체적 인간 진실 1문장",
            "contradiction": "그 진실 안의 모순 1문장(예: 체념↔재구매)",
        },
    },
    "m2": {"valueproposition": "광고가 실제 약속하는 가치, 고객 언어 1문장"},
    "m3": {
        "concepts": [{
            "name": "컨셉명 1구",
            "lens": "|".join(_LENS_POOL),
            "claimtag": "C0|C1|C2",
            "bigidea": "빅 아이디어 1~3문장",
            "provingwhy": "valueproposition 을 증명하는 방식 1문장",
            "job": "충족하는 Job 1문장",
            "differentiation": "차별화 이유 1문장",
            "risk": "리스크 1문장",
        }]
    },
}


def _condense_scenario(scenario: dict) -> str:
    condensed = {
        "brand": scenario.get("brand", ""),
        "concept": scenario.get("concept", ""),
        "narrative": scenario.get("narrative", ""),
        "key_messages": scenario.get("key_messages", []),
        "production_notes": scenario.get("production_notes", ""),
        "cast": [c.get("description", "")[:120] for c in scenario.get("cast", [])[:4]],
        "scenes": [
            {
                "cut_index": s["cut_index"],
                "time": s.get("time", ""),
                "beats": [
                    {"type": b.get("type", ""), "desc": b["description"][:200]}
                    for b in s.get("beats", [])
                    if b.get("description")
                ],
            }
            for s in scenario.get("scenes", [])
        ],
    }
    return json.dumps(condensed, ensure_ascii=False, indent=2)


def build_concept_prompt(scenario: dict) -> str:
    """scenario_analysis.json 에서 ad_concept_reference 용 컨셉 인사이트를 뽑는 프롬프트를 만든다."""
    return (
        _SYSTEM
        + f"\n[시나리오]\n{_condense_scenario(scenario)}\n\n"
        + f"[출력 스키마 — 값으로 대체하여 채워라]\n{json.dumps(_SCHEMA, ensure_ascii=False, indent=2)}"
    )
