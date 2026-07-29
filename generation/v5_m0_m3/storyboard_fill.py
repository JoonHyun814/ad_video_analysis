"""AITIVE 스토리보드 HTML 양식에는 있지만 M0~M9 산출물 어디에도 없는 프로덕션 기획
필드(캐릭터 레퍼런스·제품 레퍼런스·환경·카메라 원칙·조명·메타데이터)만 LLM 1회 호출로
채운다. M9가 이미 갖고 있는 씬·샷·감정곡선·사용완결컷 등은 여기서 다시 만들지 않고
storyboard_render.py 가 M9 원본을 그대로 사용한다 — 이미 검증된 값을 LLM이 다시 지어내
드리프트를 만들 위험을 피하기 위함이다.
"""
from __future__ import annotations

import json

from generation.v5_m0_m3 import llm_adapter

_SYSTEM = (
    "당신은 AI 영상 생성 파이프라인(실제 카메라·크루 없이 이미지-투-비디오로 제작)의 "
    "프로덕션 기획자다. 이미 확정된 컨셉·스크립트·콘티(M1~M9 산출물 요약)를 보고, 그 "
    "산출물에는 없는 '스토리보드 제작 양식'의 나머지 기획 필드만 채운다. 이미 존재하는 "
    "값(제품명·타깃·스크립트·씬 내용)을 새로 지어내지 말고, 주어진 맥락과 정합되는 새 "
    "필드만 구체적으로 채워라. metadata.camerabody/metadata.lens 처럼 실물 카메라·렌즈 "
    "브랜드/모델을 뜻하는 필드만 이 프로젝트가 AI 생성이라는 점을 감안해 'N/A(AI "
    "이미지-투-비디오 생성)' 로 채우고, camera.lensbysize 는 실물 장비가 아니라 각 샷 "
    "사이즈(WS/MS/CU)에 맞는 화각 의도이므로 'N/A' 를 붙이지 말고 '24mm', '85mm' 처럼 "
    "짧게(5단어 이내) 화각 수치만 써라 — 씬마다 반복 표시되므로 길게 쓰면 표가 지저분해진다. "
    "enum 으로 표시된 필드는 제시된 값 중 정확히 하나만 그대로 써라. 이 파이프라인은 기본적으로 "
    "CTV(16:9) 광고를 만든다 — 맥락상 세로형·정방형이 뚜렷하지 않으면 aspectratio 는 "
    "16:9로 두고, adformat 문구도 그 값과 모순되지 않게 써라(예: adformat 에 9:16 을 "
    "언급했으면 aspectratio 도 9:16이어야 한다). 오직 JSON 객체 하나로만 응답하라."
)

_SCHEMA: dict = {
    "character": {"roleage": "", "identifier": "짧은 영문 대문자 토큰 1개(문장 금지) 예: BRAND_WOMAN_01",
                  "costumespec": "", "expressiondirection": "", "seednote": "", "fixedrules": ""},
    "product": {"appearance": "", "color": "", "producttype": "변형|설치|소품 중 하나",
                "negative": "", "referencesource": "실물 팩샷|생성 중 하나"},
    "environment": {"place": "", "indooroutdoor": "실내|실외 중 하나",
                     "timeofday": "아침|낮|저녁|매직아워 중 하나", "interiortone": "",
                     "blocking": "", "keylightdirection": ""},
    "camera": {"principle": "", "assignmentprinciple": "", "insertnote": "",
               "lensbysize": {"WS": "예: 24mm(짧게, 화각 수치+렌즈 성격만)",
                              "MS": "예: 35mm", "CU": "예: 85mm", "default": "예: 50mm"}},
    "lighting": {"setup": "", "moodkeywords": "", "forbidden": ""},
    "metadata": {"genre": "", "subgenre": "", "adformat": "", "productintegration": "",
                 "actors": "", "aspectratio": "16:9|9:16|1:1 중 하나 — adformat 과 반드시 일치시킬 것",
                 "shottype": "", "lenssize": "", "composition": "",
                 "lightingsummary": "", "lightingtype": "",
                 "locationtype": "세트|로케이션 중 하나", "set": "", "camerabody": "",
                 "lens": "", "filmstock": "", "tags": "", "palette": ["#hex 8개"]},
}


def _context(module0: dict, m1: dict, m2: dict, m4: dict, m5: dict, m9: dict) -> dict:
    selected = ((m4 or {}).get("selected") or [{}])[0]
    scenes = [s for s in ((m9 or {}).get("scenes") or []) if isinstance(s, dict)]
    return {
        "productname": (module0 or {}).get("productname", ""),
        "brand": (module0 or {}).get("brand", ""),
        "category": (module0 or {}).get("category", ""),
        "productappearance": (module0 or {}).get("productappearance", ""),
        "facts": ((module0 or {}).get("facts") or [])[:5],
        "target": ((m1 or {}).get("target") or {}).get("label", ""),
        "corejob": (m1 or {}).get("corejob", ""),
        "positioningstatement": (m2 or {}).get("positioningstatement", ""),
        "uniqueattributes": (m2 or {}).get("uniqueattributes", []),
        "selectedconcept": selected.get("concept", ""),
        "onesentence": selected.get("onesentence", ""),
        "hook": (m5 or {}).get("hook", ""), "toneregister": (m5 or {}).get("toneregister", ""),
        "engine": (m5 or {}).get("engine", ""), "narrativeform": (m5 or {}).get("narrativeform", ""),
        "cta": (m5 or {}).get("cta", {}),
        "emotioncurve": (m9 or {}).get("emotioncurve", ""),
        "visualkeywords": (m9 or {}).get("visualkeywords", []),
        "scenes": [{"no": s.get("no"), "time": s.get("time"), "brief": s.get("brief"),
                    "mood": s.get("mood"), "color": s.get("color"), "shot": s.get("shot")}
                   for s in scenes],
    }


def fill_extra_fields(module0: dict, m1: dict, m2: dict, m4: dict, m5: dict, m9: dict) -> dict:
    """스토리보드 HTML 렌더에 필요한 추가 기획 필드를 LLM 1회 호출로 채워 반환한다.

    반환 형태는 `_SCHEMA` 와 동일 — 실패 시(파싱 실패 등) 빈 값 스키마를 반환해
    렌더가 빈 칸으로 우아하게 degrade 하도록 한다.
    """
    ctx = _context(module0, m1, m2, m4, m5, m9)
    user = (json.dumps(ctx, ensure_ascii=False)
            + "\n\n위 맥락으로 아래 JSON 스키마의 모든 필드를 채워 그 JSON 객체로만 응답하라:\n"
            + json.dumps(_SCHEMA, ensure_ascii=False))
    out = llm_adapter.chat_json(_SYSTEM, user, stage="STORYBOARD_HTML")
    if not isinstance(out, dict) or out.get("error"):
        return json.loads(json.dumps(_SCHEMA))
    return out
