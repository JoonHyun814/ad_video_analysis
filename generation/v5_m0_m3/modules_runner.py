"""v5_m0_m3 MODULE 1~9 LLM 러너 — 원본 modules.py(1698줄, M1~M11 전체)에서 M1~M9 실행
경로(M8 은 원본에도 결번)에 실제로 쓰이는 함수만 발췌 이식했다. M10/M11(비주얼 디렉터·통합
스토리보드)·M12(영상 생성) 전용 로직은 이 파이프라인 범위 밖이라 제외했다.

원본과 다른 점(사용자 승인/설계 결정):
  - llm_chat(app.services.llm_client) → llm_adapter.chat_json(claude -p). temperature/
    max_tokens/finish_reason 은 claude -p 에 대응 개념이 없어 제거했다.
  - _gate_model/_GATE_MODULES(게이트 M4/M6/M7 에 상위 모델 opt-in) — claude -p 는 모델 스위칭이
    없어 제외. 모든 모듈이 같은 claude -p 호출을 쓴다.
  - _recent_engines(M5 설득엔진 반-수렴, 소스 DB `v5moduleoutputs` 조회) — 이 프로젝트엔 run
    이력 테이블이 없고 단발 CLI 라 "최근 다른 run" 개념 자체가 없어 제외.
  - video_style 자동선택(pick_style_llm 등, DB 기반) 대신 CLI --style 명시 인자만 지원
    (video_style.py 참고).
  - messages 배열(대화 히스토리) 대신 system+user 두 문자열만 다룬다 — "빈 골격 응답 1회
    재생성"/"M9 계약 위반 1회 재생성" 재시도는 assistant 턴을 남기는 대신 user 텍스트에
    재시도 지시를 이어붙인다.

[신규] --retrieval 옵션(llm_adapter.set_retrieval)이 켜져 있으면 stage 별로 정확히 한 종류의
참조 검색 도구 안내를 시스템 프롬프트에 덧붙인다 — M3 는 ad_concept_reference 검색
(search_concept_reference/list_concept_segment_columns, 전략·소구 참고), M4~M9 는
ad_production_reference 검색(search_production_reference/list_production_segment_columns,
연출·촬영 기법 참고). M1/M2 는 도구 안내를 받지 않는다. 실제 도구 연결(어느 stage 에 어느
kind 를 줄지)은 llm_adapter.py._STAGE_TOOL_KIND 가 담당한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from generation.v5_m0_m3 import llm_adapter, md_parser, video_style

logger = logging.getLogger(__name__)

_TEMP = {1: 0.4, 2: 0.4, 3: 0.85, 4: 0.3, 5: 0.6, 6: 0.6, 7: 0.4, 9: 0.6}  # 참고용 보존(claude -p 는 temperature 인자 없음)

_OVERRIDE_BASE: dict[int, str] = {
    1: '{"corejob":"핵심 Job 한 문장",'
       '"humantruth":{"truth":"구체적 인간 진실 1문장(구체·미말·모순 3성질 통과, 경쟁사 킬 테스트 통과)","source":"어느 verbatim/과거행동에서 왔나","contradiction":"담은 모순 1문장(예: 체념↔재구매)"},'
       '"culturalcodes":[{"code":"관용구·펀·이중의미·장르·의례","overlap":"제품 진실의 어느 지점과 겹치나"}],'
       '"marketscopes":[{"level":"broad|mid|narrow","marketdefinition":"[카테고리]+[직접·간접 경쟁대안]+[비소비 포함 구매자 풀] 1문장",'
       '"targetpreview":"이 시장의 타깃 1줄","rationale":"이 경계를 잡은 근거","recommended":true}],'
       '"marketdefinition":"(marketscopes 중 recommended scope 의 정의문 = 하위호환)",'
       '"target":{"label":"한 줄 정의: 정체+원하는 것 융합(화면 노출)","exclusion":["…내부용, 화면 비노출"],"who":"타깃 한 줄",'
       '"aio":{"activities":"","interests":"","opinions":"","lifestyle":""},'
       '"tension":"타깃 내부의 모순·긴장 1문장(→ humantruth 로 증류되는 씨앗)","ceplink":"연결 CEP·트리거",'
       '"evidence":"AIO 각 항목 근거 소스","confidence":"[가설·신뢰도]"},'
       '"forces":{"push":"","pull":"","anxiety":"","habit":""},'
       '"triggers":["CEP 후보 트리거"],"opportunitytop3":[{"outcome":"","hypothesis":"[가설·신뢰도]"}],'
       '"assumptiontop3":["검증 필요 가정"],"verbatim":["고객 실제 표현"]}',
    2: '{"messagecandidates":[{"angle":"가치 앵글 라벨","cep":"연결 CEP","statement":"핵심 메시지 1문장","recommended":true}],'
       '"positioningstatement":"(messagecandidates 중 recommended 의 statement = 하위호환)",'
       '"valueproposition":"고객언어 1문장","ownedceps":[{"cep":"","dba":""}],'
       '"topcompetitor":"(현상유지 여부 포함)","category":"리더추격|재정의|새카테고리","cepcoverage":"시장 경계 내 상황 커버리지 방침",'
       '"demandspace":"수요맥락","uniqueattributes":["차별속성"]}',
    3: '{"seeds":["전략렌즈 씨앗"],"fixedwhy":"M2 valueproposition 에서 옮긴 공통 why 1줄",'
       '"concepts":[{"name":"","lens":"","claimtag":"C0|C1|C2","compliancenote":"효능·비방 사전경고 1줄(카드 확인할 점)","bigidea":"","provingwhy":"고정 why 증명 1문장(결과 표현)","job":"","differentiation":"","risk":"",'
       '"referencedvideoid":"검색 결과에서 실제로 기법을 차용했다면 그 video_id(정수), 아니면 null","referencedelement":"차용한 구체적 연출 기법과 이 컨셉에서 어떻게 변형했는지 1줄(원본 기법 → 변형). 차용 없으면 빈 문자열"}]}',
    4: '{"verdict":"go|reject","scores":[{"concept":"","comment":"[판단·근거]"}],'
       '"killed":[{"concept":"","reason":"킬 사유"}],'
       '"shortlist":[{"concept":"","onesentence":"","assumptions":[],"traps":[],"recommended":true}],'
       '"selected":"(shortlist 중 recommended = 하위호환, 코드가 파생)",'
       '"reason":"Go/Reject 근거"}',
    5: '{"awareness":"Unaware~Most Aware","sophistication":"1~5","l0conclusion":"L0 제약 1문장",'
       '"container":"ABCD+Hook-Body-CTA","timeallocation":["0~2초 Attract.."],"engine":"PAS|AIDA|BAB|Demo|Story|4Ps|SocialProof|UniqueMechanism|FAB",'
       '"enginereason":"왜 이 엔진인가 + 왜 PAS/BAB(또는 비문제-프레임)가 아닌가 1문장",'
       '"narrativeform":"미니드라마|비네트|대조|열거|반전|원샷|POV|모큐멘터리|은유세계|데모스펙터클|부조리|일상몽타주",'
       '"toneregister":"카테고리 디폴트 대비 반전한 톤 + 어느 진실에서 도출",'
       '"hook":"최종 Hook","modulematrix":{"hook":[],"angle":[],"proof":[],"cta":[]},'
       '"script":[{"line":"순수 자막/대사 텍스트만; 앞에 [태그] 접두·M1/m5 등 모듈명 금지","tag":"Hook|Brand|Demo|P|A|S|CTA"}],"cta":{"text":"","action":"QR스캔 등"},'
       '"hookhold":["Hook/Hold 가설"],"compliance":["AI표기/기능성/비방 체크"],'
       '"referencedvideoid":"검색 결과에서 실제로 훅·서사·연출 기법을 차용했다면 그 video_id(정수), 아니면 null","referencedelement":"차용한 구체적 기법과 이 스크립트에서 어떻게 변형했는지 1줄. 차용 없으면 빈 문자열"}',
    6: '{"failuremodes":[{"mode":"","severity":"Critical|Major|Minor","module":"M1~M7"}],'
       '"killswitch":"pass|conditional|block",'
       '"unresolvedcritical":["완화 불가한 확정 결함만(검증 가능한 가정은 제외→prioritytop3로). 생성이 규칙 지켰으면 보통 빈 배열)"],'
       '"prioritytop3":["검증 가능한 위험 가정(GATE C 우선검증)"],'
       '"reason":"킬스위치 근거"}',
    7: '{"personas":[{"definition":"","scoring":""}],"variantresults":[{"variant":"","relativerank":""}],'
       '"passed":["통과 변형"],"synthlimits":["합성이 못 본 리스크"],'
       '"humantest":{"artifact":"컨셉카드|애니매틱|Hook A/B","gonogo":"사전 기준"},'
       '"verdict":"go|nogo","branch":"No-Go시 M5|GATEA 반송"}',
    9: '{"scenes":[{"no":1,"time":"0~3초","role":"story|ending","brief":"씬 고객용 요약 1문장(~40자, 촬영/전문용어 금지)","mood":"무드(BGM/분위기)","shot":"CU|MS|WS+무브","visual":"화면묘사(QR·자막·로고·배지·카피 등 글자 요소 금지 — 글자는 overlay 에만)","audio":"내레이션/BGM/SFX",'
       '"overlay":"텍스트(후반합성)","emotion":"","color":"자연광|상황광(색온도 쿨/웜 대비 금지)","transition":"컷",'
       '"shots":[{"desc":"마이크로샷 화면묘사(피사체+동작 — 직전 샷과 사이즈|앵글|피사체 중 1개+ 뚜렷이 대비, 글자 요소 금지)","size":"WS|MS|CU","angle":"eye|low|high|top|pov","sec":1.5,"cut":"hard|insert"}]}],'
       '"emotioncurve":"0초[..]→..","visualkeywords":[],'
       '"usagecutscene":"사용 완결 컷(제품을 실제로 사용/섭취/도포/착용/작동하는 순간이 보이는 씬)의 씬 번호(정수). 앱·디지털 서비스는 마지막 팩샷 씬 번호",'
       '"referencedads":[{"videoid":"검색 결과에서 실제로 차용한 광고의 video_id(정수). 콘티 전체에서 실제로 참고한 광고마다 이 배열에 항목을 1개씩 추가한다(같은 광고를 여러 항목으로 중복하지 않는다). 참고한 광고가 하나도 없으면 referencedads 자체를 빈 배열([])로 둔다",'
       '"element":"차용한 구체적 기법과 이 콘티에서 어떻게 변형했는지 1줄(원본 기법 → 변형)",'
       '"scenenos":[1,3]}]}',
}


def _tone(module0: dict, review: dict | None) -> str:
    return (review or {}).get("tone") or module0.get("tone") or "진정성 있는"


def _bgm(module0: dict) -> str:
    return str((module0 or {}).get("bgminstruction") or "").strip()


def _build_vars(n: int, module0: dict, handoffs: dict, review: dict | None) -> dict:
    """MD `{{변수}}` 치환용 (부분매칭 키)."""
    prod = module0.get("productname") or ""
    brand = module0.get("brand") or ""
    return {
        "상품명": f"{prod} ({brand})" if brand else prod,
        "카테고리": module0.get("category") or "",
        "현재 타깃": "; ".join(str(x) for x in (module0.get("targethints") or [])) or "미정",
        "현재 타겟": "; ".join(str(x) for x in (module0.get("targethints") or [])) or "미정",
        "타깃 후보": json.dumps(module0.get("targetcandidate"), ensure_ascii=False) if module0.get("targetcandidate") else "미정",
        "시장정의 후보": module0.get("marketdefinitioncand") or "미정",
        "가용 데이터 소스": "제품 상세페이지만(리뷰 미발견→[가설] 추정)",
        "경쟁": ", ".join(c.get("name", "") for c in (module0.get("competitorcandidates") or []) if isinstance(c, dict)) or "조사 요청",
        "광고 길이": "15초",
        "플랫폼": "CTV+모바일",
        "톤앤무드": _tone(module0, review),
        "BGM지시": _bgm(module0),
        "브랜드 단계": "성장",
        "M1 핸드오프": json.dumps(handoffs.get(1, {}), ensure_ascii=False),
        "M1 타깃 정의": json.dumps((handoffs.get(1, {}) or {}).get("target"), ensure_ascii=False) if (handoffs.get(1, {}) or {}).get("target") else "",
        "M2 핸드오프": json.dumps(handoffs.get(2, {}), ensure_ascii=False),
        "M2 Demand Space": json.dumps((handoffs.get(2, {}) or {}).get("demandspace", ""), ensure_ascii=False),
        "GATE A 핸드오프": json.dumps(handoffs.get(4, {}), ensure_ascii=False),
        "M4 핸드오프": json.dumps(handoffs.get(4, {}), ensure_ascii=False),
        "M5 핸드오프": json.dumps(handoffs.get(5, {}), ensure_ascii=False),
        "M5 최종 스크립트": json.dumps((handoffs.get(5, {}) or {}).get("script", []), ensure_ascii=False),
        "전략 패스포트": _strategy_passport(handoffs),
        "M9 씬 분할표": json.dumps(handoffs.get(9, {}), ensure_ascii=False),
        "M1 검증필요 가정": json.dumps((handoffs.get(1, {}) or {}).get("assumptiontop3", []), ensure_ascii=False),
    }


def _narrative_brief(handoffs: dict) -> str:
    """핵심 전략(M1 Job·M2 포지셔닝·고객표현·차별속성)을 서술형으로 — JSON handoff 의 맥락 손실 보완."""
    m1 = handoffs.get(1, {}) or {}
    m2 = handoffs.get(2, {}) or {}
    parts = []
    if m1.get("corejob"):
        parts.append(f"핵심 Job: {m1['corejob']}")
    _ht = m1.get("humantruth")
    if isinstance(_ht, dict) and _ht.get("truth"):
        parts.append(f"인간 진실(모순): {_ht['truth']}")
    elif isinstance(_ht, str) and _ht:
        parts.append(f"인간 진실(모순): {_ht}")
    _codes = [c.get("code") for c in (m1.get("culturalcodes") or []) if isinstance(c, dict) and c.get("code")]
    if _codes:
        parts.append("문화 코드 후보: " + " / ".join(str(x) for x in _codes[:5]))
    if m2.get("positioningstatement"):
        parts.append(f"포지셔닝: {m2['positioningstatement']}")
    vb = [str(v) for v in (m1.get("verbatim") or []) if v][:3]
    if vb:
        parts.append("고객 실제 표현: " + " / ".join(vb))
    ua = [str(a) for a in (m2.get("uniqueattributes") or []) if a][:4]
    if ua:
        parts.append("차별 속성: " + ", ".join(ua))
    if not parts:
        return ""
    return ("\n\n[전략 맥락 — 아래 제품 고유 자산을 카피·장면에 구체적으로 반영하라. "
            "일반론·placeholder([브랜드/제품명] 등) 금지]\n- " + "\n- ".join(parts))


def _strategy_passport(handoffs: dict) -> str:
    """M1 Job·M2 가치제안 + 선정 컨셉(M4)·서사 형식(M5) 압축 요약 — handoffs 에서 매번 파생."""
    m1 = handoffs.get(1, {}) or {}
    m2 = handoffs.get(2, {}) or {}
    m3 = handoffs.get(3, {}) or {}
    m4 = handoffs.get(4, {}) or {}
    m5 = handoffs.get(5, {}) or {}
    parts: list[str] = []
    if m1.get("corejob"):
        parts.append(f"핵심 Job: {m1['corejob']}")
    if m2.get("valueproposition"):
        parts.append(f"가치 제안: {m2['valueproposition']}")
    sel = m4.get("selected") or []
    sel0 = sel[0] if sel and isinstance(sel[0], dict) else {}
    if sel0.get("onesentence"):
        parts.append(f"선정 컨셉: {sel0['onesentence']}")
    selname = str(sel0.get("concept") or "").strip()
    if selname:
        for c in (m3.get("concepts") or []):
            if isinstance(c, dict) and str(c.get("name") or "").strip() == selname:
                pw = str(c.get("provingwhy") or "").strip()
                if pw:
                    parts.append(f"증명 방식(왜 믿게 되는가): {pw}")
                break
    if m5.get("narrativeform"):
        parts.append(f"서사 형식: {m5['narrativeform']}")
    if m5.get("toneregister"):
        parts.append(f"톤 레지스터: {m5['toneregister']}")
    if m5.get("hook"):
        parts.append(f"핵심 Hook: {m5['hook']}")
    _nf = str(m5.get("narrativeform") or "")
    _twistform = any(k in _nf for k in ("반전", "부조리", "은유세계", "모큐멘터리"))
    _ht = m1.get("humantruth")
    _contra = _ht.get("contradiction") if isinstance(_ht, dict) else None
    if _twistform and _contra and str(_contra).strip():
        parts.append(f"비틀 지점(인간 진실의 모순 — 관습을 깨는 의외성의 근거): {str(_contra).strip()}")
    if not parts:
        return ""
    return ("[전략 패스포트 — 이 컨셉이 '왜·어떤 서사로' 다른지의 핵심. 콘티가 표준 구조로 "
            "평준화되지 않게 이 의도(특히 서사 형식)를 씬 설계에 반영하라]\n- " + "\n- ".join(parts))


def _m1_voc_note(level: str) -> str:
    """M1 가드레일 — VoC level 에 따른 지시(출처 결속·[가설] 라벨)."""
    if level == "brand":
        return ("voc.reviews 는 이 제품의 실제 후기다. forces/verbatim/opportunity 를 이 실제 표현에 "
                "근거해 작성하고, 제공된 verbatim 외에는 지어내지 마라. evidencelevel='brand'.")
    if level == "category":
        return ("voc.reviews 는 같은 카테고리 일반 후기(자사 아님)다. 이를 근거로 쓰되 forces/verbatim/"
                "triggers/opportunity 를 전부 [가설] 로 라벨하라. 자사 데이터로 단정하지 마라. 제공된 "
                "verbatim 외에는 지어내지 마라. evidencelevel='category'.")
    return ("실제 리뷰 데이터 없음. 카테고리 일반론으로 추정하되 전부 [가설] 로 라벨하고 verbatim 을 "
            "지어내지 마라(빈 배열 허용). evidencelevel='none'.")


def _build_user(n: int, module0: dict, handoffs: dict, review: dict | None, rerun_hint: dict | None = None) -> str:
    """모듈별 구조화 입력 JSON."""
    h = handoffs
    base = {"productname": module0.get("productname", ""), "brand": module0.get("brand", ""),
            "category": module0.get("category", "")}
    if n == 1:
        d = {**base, "uspcandidates": module0.get("uspcandidates", []), "facts": module0.get("facts", []),
             "claimedfacts": module0.get("claimedfacts", []),
             "productanchor": module0.get("productanchor", ""),
             "targethints": module0.get("targethints", []), "competitorcandidates": module0.get("competitorcandidates", []),
             "targetcandidate": module0.get("targetcandidate") or {},
             "marketdefinitioncand": module0.get("marketdefinitioncand", ""),
             "note": "리뷰 마이닝 데이터가 제한적이면 [가설] 태그로 명시"}
        voc = module0.get("voc")
        if voc:
            level = voc.get("level") or "none"
            d["voc"] = {"level": level, "reviews": (voc.get("reviews") or [])[:20], "summary": voc.get("summary", "")}
            d["note"] = _m1_voc_note(level)
    elif n == 2:
        d = {**base, "competitorcandidates": module0.get("competitorcandidates", []), "brandstage": "성장", "m1": h.get(1, {}),
             "productappearance": module0.get("productappearance", "")}
    elif n == 3:
        d = {"m2": h.get(2, {}), "adlength": "15초"}
    elif n == 4:
        d = {"concepts": (h.get(3, {}) or {}).get("concepts", []),
             "fixedwhy": (h.get(3, {}) or {}).get("fixedwhy", ""),
             "m1corejob": (h.get(1, {}) or {}).get("corejob", "")}
    elif n == 5:
        d = {"selectedconcept": ((h.get(4, {}) or {}).get("selected") or [{}])[0],
             "m1": h.get(1, {}), "m2": h.get(2, {}),
             "adlength": "15초", "platform": "CTV+모바일"}
    elif n == 6:
        d = {"m1assumptions": (h.get(1, {}) or {}).get("assumptiontop3", []), "m2": h.get(2, {}),
             "m4selected": (h.get(4, {}) or {}).get("selected", []), "m5": h.get(5, {})}
    elif n == 7:
        d = {"m5": h.get(5, {}), "m6priority": (h.get(6, {}) or {}).get("prioritytop3", [])}
    elif n == 9:
        d = {"m5script": (h.get(5, {}) or {}).get("script", []), "m5": h.get(5, {}),
             "adlength": "15초", "tone": _tone(module0, review),
             "brandlogourl": module0.get("brandlogourl", ""),
             "productappearance": module0.get("productappearance", ""),
             "productfacts": module0.get("facts", []),
             "productreferences": module0.get("productreferences", [])}
    else:
        d = base
    if rerun_hint:
        d["rerunhint"] = rerun_hint
    if review and n in (5, 9):
        d["review"] = {k: review.get(k) for k in ("tone", "note", "framework", "brandcolor") if review.get(k)}
    ctx = _narrative_brief(handoffs) if n in (3, 4, 5, 6, 9) else ""
    return (
        json.dumps(d, ensure_ascii=False) + ctx
        + "\n\n위 입력으로 지시를 수행하고, 지정된 JSON 객체로만 응답하세요(코드펜스·설명·머리말 없이)."
    )


def _override(n: int, review: dict | None) -> str:
    base = _OVERRIDE_BASE.get(n, "")
    if not base:
        return ""
    head = (
        "\n\n[v5 오버라이드 — 반드시 준수]\n"
        "- 설명/표/머리말 없이 아래 JSON 객체 하나로만 응답한다.\n"
        "- 아래 스키마의 키 이름을 그대로 사용하고, 스키마에 없는 키를 새로 만들지 않는다.\n"
        "- 모든 최상위 키를 빠짐없이 포함한다(값이 없으면 빈 배열/빈 문자열).\n"
        "JSON 스키마:\n"
    )
    if n == 5:
        head += (
            "- M5 script 규칙: script[].line 은 순수 발화/자막 텍스트만 쓴다.\n"
            "- line 앞에 [Hook]/[Brand]/[Body/Demo] 같은 태그 접두를 넣지 않는다(태그는 tag 필드에만).\n"
            "- line 에 M1/M2/M5·m1·handoff·GATE A/B/C 등 내부 모듈명·키를 절대 쓰지 않는다.\n"
        )
    if n == 5 and review:
        fw = (review.get("framework") or "").strip().lower()
        if fw and fw not in ("auto", ""):
            head += f"- [검수 확정] L2 설득 엔진은 {fw.upper()} 를 우선 고려(L0 진단과 충돌 시 근거 남길 것).\n"
    if n == 9:
        head += (
            "- 마지막 씬은 엔딩용 Final Shot으로 설계한다. 제품을 명확한 주체로 두고, locked camera로 "
            "잠기는 최종 구도를 만든다. 제품의 실루엣·재질·색·패키지 디테일은 참조 이미지와 일관되게 유지한다.\n"
        )
    return head + base


_M5_LINE_TAG_RE = re.compile(r"^\s*\[[^\]]*\]\s*")
_M5_LINE_MODULE_RE = re.compile(r"^\s*M\d+\s*(?:의\s*)?", re.IGNORECASE)


def _sanitize_m5_script(out: dict) -> dict:
    """M5 script line 방어 — 선행 [태그] 접두 + 'M\\d' 모듈명 누수 제거(프롬프트 차단의 코드 안전망)."""
    script = out.get("script")
    if not isinstance(script, list):
        return out
    for row in script:
        if not isinstance(row, dict):
            continue
        line = str(row.get("line") or "")
        line = _M5_LINE_TAG_RE.sub("", line)
        line = _M5_LINE_MODULE_RE.sub("", line)
        row["line"] = line.strip()
    return out


_SCENE_TC_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)")


def _fmt_scene_sec(value: float) -> str:
    return f"{value:g}"


def _normalize_scene_times(out: dict, total: float = 15) -> bool:
    """M9 씬 타임코드 코드검증·보정 — 0→total 연속 보장(첫=0/연속/끝=total/각 씬≥1s)."""
    scenes = out.get("scenes") or out.get("scenelist")
    if not isinstance(scenes, list) or not scenes:
        return False
    n = len(scenes)
    durs: list[float | None] = []
    for s in scenes:
        d = None
        if isinstance(s, dict):
            m = _SCENE_TC_RE.search(str(s.get("time") or s.get("timecode") or ""))
            if m:
                a, b = float(m.group(1)), float(m.group(2))
                if 0 < b - a <= total:
                    d = b - a
        durs.append(d)
    known = sum(d for d in durs if d)
    holes = sum(1 for d in durs if not d)
    if holes:
        share = max(1, (total - known) // holes) if total > known else 1
        durs = [d if d else share for d in durs]
    cur, changed = 0.0, False
    for i, s in enumerate(scenes):
        if not isinstance(s, dict):
            continue
        start = cur
        if i == n - 1:
            end = total
        else:
            end = min(start + (durs[i] or 1), total - (n - 1 - i))
            end = max(end, start + 1)
        new_tc = f"{_fmt_scene_sec(start)}~{_fmt_scene_sec(end)}초"
        old = str(s.get("time") or s.get("timecode") or "").replace(" ", "")
        start_s, end_s = _fmt_scene_sec(start), _fmt_scene_sec(end)
        if f"{start_s}~{end_s}" not in old and f"{start_s}-{end_s}" not in old:
            changed = True
        s["time"] = new_tc
        if "timecode" in s:
            s["timecode"] = new_tc
        cur = end
    return changed


_MIN_SHOT_SEC = 0.8


def _normalize_shot_times(out: dict) -> bool:
    """M9 씬 내부 shots(마이크로샷) 타임코드 코드보정 — 씬 시간 범위를 정확히 채우는 절대 타임코드 부여."""
    scenes = out.get("scenes") or out.get("scenelist")
    if not isinstance(scenes, list):
        return False
    changed = False
    for s in scenes:
        if not isinstance(s, dict):
            continue
        rawshots = s.get("shots")
        if not isinstance(rawshots, list) or not rawshots:
            continue
        shots = [sh for sh in rawshots if isinstance(sh, dict)]
        if not shots:
            s["shots"] = []
            changed = True
            continue
        m = _SCENE_TC_RE.search(str(s.get("time") or s.get("timecode") or ""))
        if not m:
            continue
        start, end = float(m.group(1)), float(m.group(2))
        dur = end - start
        if dur <= 0:
            continue
        maxn = max(1, int((dur + 1e-6) // _MIN_SHOT_SEC))
        if len(shots) > maxn:
            shots, changed = shots[:maxn], True
        n = len(shots)
        share = dur / n
        weights = []
        for sh in shots:
            try:
                v = float(sh.get("sec") or 0)
            except Exception:
                v = 0.0
            weights.append(v if v > 0 else share)
        extra = dur - _MIN_SHOT_SEC * n
        wsum = sum(weights)
        durs = [_MIN_SHOT_SEC + (extra * w / wsum if wsum > 0 else extra / n) for w in weights]
        cum, cur = start, start
        for i, sh in enumerate(shots):
            cum += durs[i]
            b = end if i == n - 1 else min(max(round(cum, 1), cur), end)
            tc = f"{_fmt_scene_sec(cur)}~{_fmt_scene_sec(b)}초"
            if sh.get("time") != tc:
                changed = True
            sh["time"] = tc
            sh["sec"] = round(b - cur, 2)
            cur = b
        s["shots"] = shots
    return changed


_SHOT_SIZE_MAP = {"EWS": "WS", "LS": "WS", "FS": "WS", "WS": "WS", "와이드": "WS",
                  "MCU": "MS", "MS": "MS", "미디엄": "MS",
                  "ECU": "CU", "BCU": "CU", "CU": "CU", "클로즈업": "CU", "매크로": "CU"}
_SHOT_ANGLE_MAP = {"eye": "eye", "eyelevel": "eye", "eye-level": "eye", "아이레벨": "eye",
                   "low": "low", "로우": "low", "high": "high", "하이": "high",
                   "top": "top", "topdown": "top", "top-down": "top", "overhead": "top",
                   "bird": "top", "탑다운": "top", "부감": "top",
                   "pov": "pov", "1인칭": "pov", "dutch": "dutch", "더치": "dutch"}


def _normalize_shot_fields(out: dict) -> bool:
    """M9 shots[].size/angle 표기 정규화 — size 는 WS|MS|CU 로, angle 은 소문자 표준어로."""
    changed = False
    for s in ((out or {}).get("scenes") or []):
        if not isinstance(s, dict):
            continue
        for sh in (s.get("shots") or []):
            if not isinstance(sh, dict):
                continue
            rawsize = str(sh.get("size") or "").strip()
            if rawsize:
                key = rawsize.upper().replace(" ", "")
                norm = next((v for k, v in _SHOT_SIZE_MAP.items() if k in key), rawsize)
                if norm != rawsize:
                    sh["size"], changed = norm, True
            rawangle = str(sh.get("angle") or "").strip()
            if rawangle:
                key = rawangle.lower().replace(" ", "")
                norm = next((v for k, v in _SHOT_ANGLE_MAP.items() if k in key), rawangle.lower())
                if norm != rawangle:
                    sh["angle"], changed = norm, True
    return changed


def _bigram_jaccard(a: str, b: str) -> float:
    """문자 바이그램 자카드 유사도 — 가짜 컷(거의 같은 화면묘사) 휴리스틱용."""
    sa = {a[i:i + 2] for i in range(len(a) - 1)} if len(a) > 1 else set(a)
    sb = {b[i:i + 2] for i in range(len(b) - 1)} if len(b) > 1 else set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _reserve_terminal_ending_shot(out: dict) -> bool:
    """13~15초를 Seedance 친화적인 엔딩 팩샷으로 예약."""
    scenes = out.get("scenes")
    if not isinstance(scenes, list) or not scenes or not all(isinstance(scene, dict) for scene in scenes):
        return False

    if len(scenes) == 1:
        scenes.append(dict(scenes[0]))

    _normalize_scene_times({"scenes": scenes[:-1]}, total=13)
    ending = scenes[-1]
    ending.update({
        "time": "13~15초", "role": "ending", "shot": "MS locked camera",
        "visual": (
            "제품이 프리미엄 표면 중앙에 정면으로 놓인다. 조명 반사만 제품 표면을 천천히 스치고, "
            "주변 환경의 작은 움직임만 이어진다. 제품 실루엣·재질·색·패키지 디테일은 참조 이미지와 일관되게 유지한다."
        ),
        "audio": "BGM과 주변 소리가 남은 에너지를 정리하며 마무리된다",
        "overlay": "", "transition": "컷",
        "shots": [{
            "desc": (
                "Final Shot: 제품이 프리미엄 표면 중앙에 정면으로 놓인다. MS locked camera, 조명 반사만 "
                "제품 표면을 천천히 스치고 주변 환경의 작은 움직임만 이어진다. 제품 실루엣·재질·색·패키지 "
                "디테일을 참조 이미지와 일관되게 유지한다."
            ),
            "sec": 2.0, "cut": "hard",
        }],
    })
    for index, scene in enumerate(scenes, 1):
        scene["no"] = index
    out["scenes"] = scenes
    return True


def count_scene_shots(m9: dict) -> int:
    """M9 핸드오프의 총 샷 수 — shots 있는 씬은 샷 수, 없는 씬은 1로 센다(기대 비트 수)."""
    n = 0
    for s in ((m9 or {}).get("scenes") or []):
        if not isinstance(s, dict):
            continue
        shots = s.get("shots")
        k = len([sh for sh in shots if isinstance(sh, dict)]) if isinstance(shots, list) else 0
        n += k if k > 0 else 1
    return n


def _ensure_scene_count(out: dict, handoffs: dict) -> bool:
    """M9 씬 개수가 M5 스크립트 라인 수보다 적으면, 가장 긴 씬을 반으로 나눈다."""
    scenes = out.get("scenes") or out.get("scenelist")
    if not isinstance(scenes, list) or not scenes:
        return False
    m5 = handoffs.get(5, {}) or {}
    script = m5.get("script") or []
    expected = len(script)
    n = len(scenes)
    if expected <= 0 or n >= expected:
        return False

    changed = False
    while len(scenes) < expected:
        durs = []
        for s in scenes:
            if not isinstance(s, dict):
                durs.append(0)
                continue
            m = _SCENE_TC_RE.search(str(s.get("time") or s.get("timecode") or ""))
            durs.append(float(m.group(2)) - float(m.group(1)) if m else 0)

        longest_idx = max(range(len(durs)), key=lambda i: durs[i])
        longest_dur = durs[longest_idx]
        if longest_dur < 2:
            break

        longest = scenes[longest_idx]
        m = _SCENE_TC_RE.search(str(longest.get("time") or longest.get("timecode") or ""))
        if not m:
            break
        start, end = float(m.group(1)), float(m.group(2))
        mid = round(start + (end - start) / 2, 1)
        if mid <= start or mid >= end:
            break

        new_scene = dict(longest)
        longest["time"] = f"{_fmt_scene_sec(start)}~{_fmt_scene_sec(mid)}초"
        new_scene["time"] = f"{_fmt_scene_sec(mid)}~{_fmt_scene_sec(end)}초"
        _shots = longest.get("shots")
        if isinstance(_shots, list) and _shots:
            _half = max(1, len(_shots) // 2)
            longest["shots"] = _shots[:_half]
            if _shots[_half:]:
                new_scene["shots"] = _shots[_half:]
            else:
                new_scene.pop("shots", None)

        scenes.insert(longest_idx + 1, new_scene)
        try:
            uc = int(out.get("usagecutscene") or 0)
            if uc > longest_idx + 1:
                out["usagecutscene"] = uc + 1
        except Exception:
            pass
        changed = True

    if changed:
        for i, s in enumerate(scenes, 1):
            if isinstance(s, dict):
                s["no"] = i
        out["scenes"] = scenes
        _normalize_scene_times(out)
    return changed


def _usagecut_violation(out: dict) -> str:
    """M9 사용 완결 컷 계약검증 — 위반 사유 문자열("" = 통과)."""
    scenes = out.get("scenes") or out.get("scenelist") or []
    if not isinstance(scenes, list) or not scenes:
        return ""
    try:
        uc = int(out.get("usagecutscene") or 0)
    except (TypeError, ValueError):
        uc = 0
    if uc < 1 or uc > len(scenes):
        return f"usagecutscene 누락/무효(값={out.get('usagecutscene')!r}, 씬 {len(scenes)}개)"
    return ""


_USAGECUT_RETRY_HINT = (
    "직전 응답에 usagecutscene(사용 완결 컷 씬 번호)이 누락되었거나 유효한 씬 번호가 아니다. "
    "씬 중 최소 1컷은 제품을 실제로 사용하는 완결 순간(음식·음료=입가로 가져가는 lift-to-lips 순간, "
    "뷰티=도포 순간, 착용물=착용 순간, 기기=작동 순간; 해소/After 구간 배치, 앱·디지털은 마지막 팩샷 씬)을 "
    "넣고, 그 씬 번호를 usagecutscene 에 정수로 명시해 같은 JSON 스키마로 다시 작성하라."
)


def _shot_contrast_violation(out: dict) -> str:
    """M9 shots 컷 대비 계약검증 — 위반 사유 문자열("" = 통과)."""
    scenes = out.get("scenes") or out.get("scenelist") or []
    if not isinstance(scenes, list) or not scenes:
        return ""
    _normalize_shot_fields(out)
    allshots, chains, cur = [], [], []
    for s in scenes:
        shots = [sh for sh in (s.get("shots") or []) if isinstance(sh, dict)] if isinstance(s, dict) else []
        if not shots:
            if len(cur) > 1:
                chains.append(cur)
            cur = []
            continue
        allshots.extend(shots)
        cur.extend(shots)
    if len(cur) > 1:
        chains.append(cur)
    if not allshots:
        return ""
    missing = sum(1 for sh in allshots if not str(sh.get("size") or "").strip())
    if missing * 2 > len(allshots):
        return f"shots size/angle 필드 누락 다수({missing}/{len(allshots)}샷)"
    fakes = []
    for chain in chains:
        for a, b in zip(chain, chain[1:]):
            asize, bsize = str(a.get("size") or "").strip(), str(b.get("size") or "").strip()
            aang, bang = str(a.get("angle") or "").strip(), str(b.get("angle") or "").strip()
            if not (asize and bsize and asize == bsize and aang and bang and aang == bang):
                continue
            if _bigram_jaccard(str(a.get("desc") or ""), str(b.get("desc") or "")) >= 0.5:
                fakes.append(f"[{asize}/{aang}] {str(a.get('desc') or '')[:20]} ~ {str(b.get('desc') or '')[:20]}")
    if fakes:
        return "가짜 컷(같은 size·angle·유사 묘사 인접 샷): " + " / ".join(fakes[:3])
    return ""


_SHOT_CONTRAST_RETRY_HINT = (
    "직전 응답의 shots(마이크로샷)가 컷 대비 계약을 위반했다. 모든 샷에 size(WS|MS|CU)와 "
    "angle(eye|low|high|top|pov)을 필드로 채우고, 인접 샷은 size·angle 중 최소 1개가 다르거나 "
    "피사체(화면묘사)가 뚜렷이 다르게 하라 — '같은 손, 같은 각도, 미세 변화' 식 가짜 컷을 제거하고 "
    "같은 JSON 스키마로 다시 작성하라."
)


def _referencedads_violation(out: dict) -> str:
    """M9 레퍼런스 인용 계약검증(사용자 요청) — --retrieval 켜진 상태에서는 referencedads 가
    최소 1건이어야 한다. --retrieval 꺼져 있으면(도구 자체가 없음) 검증하지 않는다."""
    if not llm_adapter.get_retrieval():
        return ""
    ads = out.get("referencedads")
    if isinstance(ads, list) and any(isinstance(a, dict) and a.get("videoid") for a in ads):
        return ""
    return "referencedads 비어 있음(--retrieval 켜진 상태에서는 최소 1건 인용 필수)"


_REFERENCEDADS_RETRY_HINT = (
    "직전 응답의 referencedads 가 비어 있다. --retrieval 이 켜져 있으므로 이 콘티는 "
    "search_production_reference 로 최소 1건은 실제로 검색해, 그 결과 중 씬 구도·카메라워크·"
    "전환 기법 하나 이상을 실제로 반영해야 한다(빈 배열 금지). 검색 결과에서 이 콘티와 맞닿는 "
    "지점을 찾아 반영하고, referencedads 에 그 video_id·element(원본 기법 → 이 콘티에서의 "
    "변형)·scenenos(영향받은 씬 번호들)를 최소 1개 항목으로 채워 같은 JSON 스키마로 다시 "
    "작성하라."
)

_CRITICAL_KEY = {1: "corejob", 2: "messagecandidates", 3: "concepts", 5: "script", 9: "scenes"}

_EMPTY_RETRY_HINT = (
    "직전 응답이 핵심 값이 모두 빈 JSON 골격이었다. 입력에 있는 실제 데이터를 근거로 "
    "핵심 필드를 반드시 채워서 다시 작성하라. 근거가 약한 항목은 [가설] 라벨을 붙여 추정하되, "
    "빈 골격 응답은 금지다. 같은 JSON 스키마로만 응답한다."
)


def _rec_item(items) -> dict:
    """recommended=True 인 첫 항목, 없으면 첫 dict, 비면 {}."""
    if not isinstance(items, list) or not items:
        return {}
    for it in items:
        if isinstance(it, dict) and it.get("recommended"):
            return it
    return items[0] if isinstance(items[0], dict) else {}


def _backfill_legacy(n: int, out: dict) -> dict:
    """신규 후보 배열의 recommended 로 구 단일 필드를 파생(하위호환). 이미 값이 있으면 유지."""
    if not isinstance(out, dict):
        return out
    if n == 1:
        rec = _rec_item(out.get("marketscopes"))
        if rec and not str(out.get("marketdefinition") or "").strip():
            out["marketdefinition"] = rec.get("marketdefinition", "")
    elif n == 2:
        rec = _rec_item(out.get("messagecandidates"))
        if rec and not str(out.get("positioningstatement") or "").strip():
            out["positioningstatement"] = rec.get("statement", "")
    elif n == 4:
        sl = out.get("shortlist")
        cur = out.get("selected")
        if isinstance(sl, list) and sl and not (isinstance(cur, list) and cur):
            rec = _rec_item(sl)
            out["selected"] = [rec] if rec else []
    return out


def _is_empty_output(n: int, out: dict) -> bool:
    """모듈 핵심 키가 빈 값인지 — 빈 골격 응답 판정. 게이트(4/6/7)는 빈 selected 등이 정당한 판정이라 제외."""
    key = _CRITICAL_KEY.get(n)
    if not key or not isinstance(out, dict):
        return False
    v = out.get(key)
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return v is None


def _norm_concept(s) -> str:
    """컨셉명 정규화(매칭용) — 공백 압축 + 끝 부연 괄호 제거 + 양끝 따옴표 제거 + casefold."""
    t = re.sub(r"\s+", " ", str(s or "")).strip()
    t = re.sub(r"\s*[\(（][^()（）]*[\)）]\s*$", "", t).strip()
    return t.strip("\"'“”‘’").casefold()


def annotate_concepts_with_verdict(m3: dict | None, m4: dict | None) -> dict | None:
    """M4 비평 결과(selected/killed/scores)를 M3 concepts[] 각 항목에 컨셉명 매칭으로 역주입."""
    concepts = (m3 or {}).get("concepts")
    if not isinstance(concepts, list) or not concepts:
        return None
    sel = {_norm_concept(c.get("concept") or c.get("name")): c
           for c in ((m4 or {}).get("selected") or []) if isinstance(c, dict)}
    kil = {_norm_concept(c.get("concept")): c
           for c in ((m4 or {}).get("killed") or []) if isinstance(c, dict)}
    sco = {_norm_concept(c.get("concept")): c
           for c in ((m4 or {}).get("scores") or []) if isinstance(c, dict)}
    if not (sel or kil):
        return None
    new_concepts = []
    for c in concepts:
        if not isinstance(c, dict):
            new_concepts.append(c)
            continue
        key = _norm_concept(c.get("name"))
        nc = dict(c)
        if key in sel:
            nc["selected"], nc["verdict"] = True, "selected"
            nc["verdictreason"] = str(sel[key].get("onesentence") or "").strip()
        elif key in kil:
            nc["selected"], nc["verdict"] = False, "killed"
            nc["verdictreason"] = str(kil[key].get("reason") or "").strip()
        else:
            nc["selected"], nc["verdict"] = False, "holdover"
            nc["verdictreason"] = str((sco.get(key) or {}).get("comment") or "").strip()
        new_concepts.append(nc)
    m3a = dict(m3 or {})
    m3a["concepts"] = new_concepts
    return m3a


def gate_a(m4: dict) -> str:
    """GATE A: shortlist(신규) 1개+ 면 go, 없으면 reject. 구 run 하위호환으로 selected 도 본다."""
    cands = (m4 or {}).get("shortlist")
    if not isinstance(cands, list) or not cands:
        cands = (m4 or {}).get("selected") or []
    return "go" if len(cands) >= 1 else "reject"


def gate_b(m6: dict) -> str:
    """GATE B: unresolvedcritical 1개+ 면 block, Major 있으면 conditional, 아니면 pass."""
    criticals = (m6 or {}).get("unresolvedcritical") or []
    if len(criticals) >= 1:
        return "block"
    fms = (m6 or {}).get("failuremodes") or []
    has_major = any(isinstance(fm, dict) and str(fm.get("severity", "")).strip().lower() == "major" for fm in fms)
    return "conditional" if has_major else "pass"


def gate_c(m7: dict) -> str:
    """GATE C: 합성 verdict 정규화. go|nogo (최종은 인간 검수 — 이 파이프라인은 CLI 라 기록만 하고 계속 진행)."""
    v = str((m7 or {}).get("verdict", "go")).strip().lower()
    return "nogo" if v in ("nogo", "no-go", "reject") else "go"


# prompts/module3.md "전략 렌즈 풀"과 반드시 동일하게 유지 — 여기서만 바뀌면 emergent lens
# 판별(중복 배제)이 그 md 파일과 어긋난다.
_FIXED_LENS_POOL = (
    "반전·금기 깨기", "비유·은유", "데모·증거", "적(현상유지) 의인화", "사용자 증언",
    "정체성·소속", "기능적 Job 직격", "감정적 Job 직격", "비교·대조(전후 / 우리 vs 경쟁)",
)

_LENS_SCOUT_SCHEMA = (
    '{"emergentlenses":[{"name":"기존 9개 풀에 없는 새 전략 렌즈 이름(짧은 구)",'
    '"rationale":"이 렌즈가 왜 이 제품·카테고리에 통하는지 1문장",'
    '"sourcedvideoid":"근거가 된 검색 결과의 video_id(정수), 없으면 null"}]}'
)

_LENS_SCOUT_MIN = 3  # 사용자 요청: 적어도 3개는 채우도록 시도(부족하면 1회 재검색 유도)
_LENS_SCOUT_MAX = 5

_LENS_SCOUT_RETRY_HINT = (
    "\n\n직전 검색으로는 서로 다른 렌즈를 {found}개밖에 못 찾았다 — 최소 {min_n}개가 목표다. "
    "지금까지와 다른 세그먼트 컬럼(appeal_type/positioning_category/usp_category 등)이나 "
    "다른 쿼리로 추가 검색해서 더 찾아라. 여러 번 나눠 검색해도 된다. 다만 억지로 지어내지는 "
    "마라 — 최선을 다해 검색했는데도 {min_n}개 미만이면 실제로 찾은 만큼만 반환해도 된다."
)


def _scout_emergent_lenses(module0: dict, handoffs: dict) -> list[dict]:
    """M3 발산 직전 사전 조사(사용자 피드백 반영) — 기존엔 M3 의 retrieval 이 '이미 고른 렌즈에
    맞는 사례 찾기'에만 쓰여서 module3.md 의 고정 9렌즈 풀 밖으로 발산을 못 넓혔다. 여기서는
    본 M3 호출 전에 ad_concept_reference 를 렌즈 특정 없이 넓게 검색해, 그 9개 풀에 없는(중복
    아닌) 전략 각도를 찾는다. 최소 _LENS_SCOUT_MIN(3)개를 목표로 하고, 미달이면 다른
    세그먼트/쿼리로 1회 더 검색하게 한다(사용자 요청) — 그래도 못 채우면 있는 만큼만 반환한다
    (근거 없는 지어내기는 금지). 반환값은 M3 시스템 프롬프트에 '추가 렌즈 후보'로 얹을 때
    (`_format_emergent_lenses`)와, M3 출력 JSON 에 어느 광고가 어느 렌즈의 근거였는지 남길 때
    (`_tag_lens_origin`) 양쪽에 쓰인다. --retrieval 꺼져 있으면 빈 리스트."""
    if not llm_adapter.get_retrieval():
        return []
    m2 = handoffs.get(2, {}) or {}
    system = (
        "당신은 광고 전략 렌즈 스카우트다. search_concept_reference/list_concept_segment_columns "
        "도구로 이 제품과 유사한 카테고리·타깃·포지셔닝의 기존 광고를 특정 렌즈에 매이지 말고 "
        "포괄적으로 검색해, 아래 '기존 고정 렌즈 풀'에 없는 새로운 전략 각도를 찾아라.\n\n"
        "기존 고정 렌즈 풀(이미 커버됨 — 이것과 겹치면 제안하지 마라):\n"
        + "\n".join(f"- {lens}" for lens in _FIXED_LENS_POOL) + "\n\n"
        "검색 결과에서 반복 관찰되는 패턴(appeal_type/positioning_category/summary)이 위 9개 "
        "풀 중 하나로 이미 설명되면 제안하지 마라 — 정말 새로운 각도만 제안하라. 근거 없이 "
        "지어내지 마라. 검색해서 실제로 참고한 광고가 있다면 sourcedvideoid 에 반드시 그 "
        f"video_id 를 적어라(근거 없이 null 로 비우지 말 것 — 검색 결과 기반 제안이면 항상 "
        f"출처가 있어야 한다). 서로 다른 렌즈를 최소 {_LENS_SCOUT_MIN}개, 최대 {_LENS_SCOUT_MAX}개 "
        "찾는 게 목표다 — 한 번의 포괄적 검색으로 부족하면 세그먼트 컬럼(appeal_type/"
        f"positioning_category/usp_category 등)을 바꿔가며 여러 번 검색하라. 그래도 {_LENS_SCOUT_MIN}개를 "
        "못 채우면(정말 더는 없으면) 찾은 만큼만 반환해도 된다 — 억지로 채우기보다 정확성이 "
        "우선이다.\n\n"
        "JSON 스키마: " + _LENS_SCOUT_SCHEMA
    )
    user = (
        json.dumps({
            "productname": module0.get("productname", ""), "category": module0.get("category", ""),
            "m2positioning": m2.get("positioningstatement", ""),
            "m2valueproposition": m2.get("valueproposition", ""),
        }, ensure_ascii=False)
        + "\n\n위 입력으로 지시를 수행하고, 지정된 JSON 객체로만 응답하세요(코드펜스·설명 없이)."
    )
    lenses: list[dict] = []
    for attempt in (1, 2):
        out = llm_adapter.chat_json(system, user, stage="M3_LENS_SCOUT")
        lenses = [lens for lens in (out.get("emergentlenses") or []) if isinstance(lens, dict) and lens.get("name")]
        if len(lenses) >= _LENS_SCOUT_MIN or attempt == 2:
            break
        logger.info(f"[v5_m0_m3 M3_LENS_SCOUT] {len(lenses)}개만 찾음(목표 {_LENS_SCOUT_MIN}) -> 1회 재검색")
        user = user + _LENS_SCOUT_RETRY_HINT.format(found=len(lenses), min_n=_LENS_SCOUT_MIN)
    return lenses[:_LENS_SCOUT_MAX]


def _format_emergent_lenses(lenses: list[dict]) -> str:
    """_scout_emergent_lenses() 결과를 M3 시스템 프롬프트에 얹을 텍스트 블록으로 변환."""
    if not lenses:
        return ""
    lines = []
    for lens in lenses:
        src = f"(참고 video_id={lens['sourcedvideoid']})" if lens.get("sourcedvideoid") else ""
        lines.append(f"- {lens['name']}: {lens.get('rationale', '')} {src}".strip())
    return (
        "\n\n---\n\n[레퍼런스 발굴 렌즈 후보 — 사전 검색으로 찾은, 위 9개 고정 풀에 없는 추가 "
        "전략 렌즈. 아래도 '전략 렌즈 풀'의 일부로 취급해 선택할 수 있다(강제 아님, 적합하면 "
        "쓰고 아니면 무시). 앵커링 방지 프로토콜(서로 다른 렌즈 사용)은 고정 풀+아래 후보 "
        "전체를 대상으로 동일하게 적용한다]\n" + "\n".join(lines)
    )


def _tag_lens_origin(out: dict, emergent_lenses: list[dict]) -> None:
    """M3 concepts[] 각 항목의 lens 가 emergent lens 후보(스카우트 결과)에서 왔는지, 왔다면
    어느 video_id 가 근거였는지 이름 매칭으로 코드가 직접 태깅한다(LLM 판단에 맡기지 않음 —
    referencedvideoid/referencedelement 는 '이 컨셉이 어느 광고를 어떻게 변형했나'를 이미
    다루지만, '이 렌즈 자체가 어느 광고에서 나왔나'는 별개 추적 축이라 새로 추가했다. 사용자
    요청). `_norm_concept` 로 정규화해 매칭한다 — concepts[].lens 에는 emergentlenses[].name 의
    부연 괄호(예: "라인업 핏 개런티(맞춤 옵션 보장)")가 생략된 채 적히는 경우가 실측됐다(모델이
    렌즈명을 그대로 복사하지 않고 축약). concepts[] 가 비었거나 dict 가 아니면 아무 것도
    하지 않는다."""
    concepts = out.get("concepts")
    if not isinstance(concepts, list):
        return
    by_name = {_norm_concept(lens.get("name")): lens for lens in emergent_lenses}
    for c in concepts:
        if not isinstance(c, dict):
            continue
        src = by_name.get(_norm_concept(c.get("lens")))
        c["lensorigin"] = "emergent" if src else "fixed"
        c["lenssourcedvideoid"] = src.get("sourcedvideoid") if src else None


def _run_module_core(n: int, *, module0: dict, handoffs: dict, review: dict | None = None,
                     rerun_hint: dict | None = None) -> dict:
    """MODULE n(1~7,9) 단일 실행. 동기(호출부가 asyncio.to_thread)."""
    if n not in md_parser.MODULE_WHITELIST:
        raise ValueError(f"module {n} not in whitelist {md_parser.MODULE_WHITELIST}")

    filled = md_parser.fill_vars(md_parser.get_module_prompt(n), _build_vars(n, module0, handoffs, review))
    system = md_parser.get_common() + "\n\n---\n\n" + filled + _override(n, review)
    if n == 9:
        system += video_style.fragment(9, video_style.style_of(module0))
        system += video_style.freecompose_fragment(9)
        if video_style.pace_of(video_style.style_of(module0)) == "slow":
            system += (
                "\n\n---\n\n[PACE=slow — 이 절이 위의 편집 리듬(페이싱) 절보다 우선한다] "
                "이 run 의 스타일은 느린 템포가 정체성이다. '15초 총 샷 8~12개'와 '훅 1~1.5초 컷 2개+' "
                "규칙을 적용하지 마라 — 씬당 shots 0~1개, 전체 4~7샷, 평균 샷 2초 이상으로 느리게 "
                "설계하고, 자체검증의 페이싱 항목도 이 기준으로 대체하라. "
                "shots 를 쓰는 경우 size·angle 필드 기입 의무는 그대로 유지된다.")

    # [--retrieval] 참조 벡터 DB 검색 도구 안내 — 도구 자체는 백엔드가 붙인다(cli: claude -p
    # --mcp-config, api: llm_adapter 의 Anthropic tool_use 루프). 어느 stage 에 실제로 어느
    # 도구가 붙는지는 llm_adapter._STAGE_TOOL_KIND 가 결정한다 — M3=concept(ad_concept_reference,
    # 전략/소구 참고), M4~M9=production(ad_production_reference, 연출/촬영 기법 참고). M1/M2 는
    # retrieval 이 켜져 있어도 도구를 받지 않는다(evaluation/README.md 스키마 통합 계획 참고).
    # 언제·왜 쓸지는 LLM 이 판단한다(강제 아님). M6(레드팀)·M7(합성검증)은 리스크 진단·평가가
    # 목적이라 검색이 구조적으로 덜 유용하지만, 다른 production 단계와 동일하게 advisory 로만
    # 열어두고 실사용 여부는 로그로 관찰한다(강제로 막을 이유가 없다 — 안 쓰면 그것도 정보다).
    emergent_lenses: list[dict] = []
    if n == 3 and llm_adapter.get_retrieval():
        emergent_lenses = _scout_emergent_lenses(module0, handoffs)
        system += _format_emergent_lenses(emergent_lenses)
        system += (
            "\n\n---\n\n[전략 레퍼런스 검색 도구 사용 가능]\n"
            "search_concept_reference / list_concept_segment_columns 도구가 제공되면, 이 제품과 "
            "유사한 산업·타깃·USP·포지셔닝의 기존 광고가 어떤 소구·전략을 썼는지 참고할 때 "
            "사용해도 된다. 몇 건을 검색할지(top_k)와 어떤 세그먼트 컬럼/값으로 좁힐지는 "
            "네가 이 제품 맥락에 맞게 직접 판단하라.\n"
            "**포괄적인 검색 1회로 끝내지 마라 — 렌즈별로 나눠 여러 번 검색하는 "
            "편이 낫다.** 선택한 전략 렌즈 각각이 필요로 하는 '증명 방식'은 서로 "
            "다르므로(예: 데모·증거 렌즈 → '실측 비교로 우월성을 증명한 광고', 적 "
            "의인화 렌즈 → '경쟁·현상유지를 캐릭터화한 광고', 비유·은유 렌즈 → "
            "'문화적 관용구·상징을 전략으로 쓴 광고'), 유망한 렌즈 2~3개 이상을 골라 "
            "그 렌즈에 맞는 구체적인 쿼리로 각각 따로 검색하라(포괄적 쿼리 1개보다 "
            "렌즈별 좁은 쿼리 여러 개가 그 렌즈에 맞는 선례를 찾을 확률이 높다). "
            "검색 결과가 과도해지지 않도록 검색 1건당 top_k 는 2~4 정도로 작게 잡아라.\n"
            "검색 도구를 호출했다면, 그대로 베끼는 게 아니라 발산한 컨셉 중 "
            "**가능한 한 여러 개(1개에 그치지 말고)에는 그 컨셉의 렌즈로 검색한 결과의 "
            "summary/appeal_type/usp_category/positioning_category 중 구체적인 전략적 착안점 "
            "하나를 이 제품 맥락에 맞게 변형해 실제로 반영**하라 — '참고한 느낌'만 주지 말고, "
            "어떤 video_id의 어떤 전략을 어떻게 바꿔 썼는지 알 수 있어야 한다(연출·촬영 기법은 "
            "이 도구가 다루지 않는다 — 그건 M5~M9 단계 몫이다). 그렇게 반영한 컨셉마다 "
            "referencedvideoid/referencedelement 필드에 그 video_id와 (원본 전략 → 이 "
            "컨셉에서의 변형)을 1줄로 적어라. 검색은 했지만 특정 전략을 구체적으로 "
            "반영한 컨셉이 아니라면 그 컨셉의 두 필드는 비워 두라(반영한 척 지어내지 "
            "말 것 — 반영한 컨셉 수보다 정확성이 우선이다). 검색 도구를 아예 호출하지 "
            "않았다면 모든 컨셉의 두 필드를 비워 둔다. 반드시 호출할 필요는 없다."
        )
    elif n in (4, 5, 6, 7, 9) and llm_adapter.get_retrieval():
        system += (
            "\n\n---\n\n[연출 레퍼런스 검색 도구 사용 가능]\n"
            "search_production_reference / list_production_segment_columns 도구가 제공되면, "
            "이 컨셉·스크립트와 비슷하게 연출된 기존 광고가 어떤 촬영기법·캐스팅·구도를 썼는지 "
            "참고할 때 사용해도 된다. 몇 건을 검색할지(top_k)와 어떤 세그먼트 컬럼/값으로 "
            "좁힐지는 네가 이 맥락에 맞게 직접 판단하라."
        )
        if n == 5:
            system += (
                "\n이미 선정된 컨셉(M4 selected)을 실제 스크립트(훅·바디·CTA)로 구체화하는 "
                "단계다. notable_elements 중 훅 오프닝·카피 장치·톤 전환 기법 하나를 검색해 "
                "참고할 수 있다면 활용하라. 실제로 반영했다면 top-level "
                "referencedvideoid/referencedelement 필드에 그 video_id와 (원본 기법 → 이 "
                "스크립트에서의 변형)을 1줄로 적어라. 반영하지 않았다면(또는 검색 자체를 "
                "안 했다면) 두 필드를 비워 두라 — 반영한 척 지어내지 말 것."
            )
        elif n == 9:
            system += (
                "\n스크립트를 씬·샷 단위 콘티로 푸는 단계다. **이 단계에서는 검색 도구 호출이 "
                "선택이 아니라 필수다 — search_production_reference 로 최소 1건은 반드시 검색해, "
                "그 결과 중 특정 씬의 구도·카메라워크·전환 기법을 검색 결과 notable_elements"
                "(opening_hook/casting_direction/narrative_pattern/sensory_demo_shot)에서 찾아 "
                "이 콘티에 실제로 반영하라.** 씬마다 따로 적지 말고, 콘티 전체를 다 쓴 뒤 "
                "top-level referencedads 배열에 **실제로 참고한 광고 단위로** 정리하라 — 참고한 "
                "광고 1건당 항목 1개(videoid, 원본 기법 → 이 콘티에서의 변형을 적은 element, "
                "그 기법이 영향을 준 모든 씬 번호를 모은 scenenos 배열). 같은 광고를 여러 씬에서 "
                "참고했어도 항목을 반복하지 말고 scenenos 에 씬 번호를 모아 담아라. "
                "referencedads 는 **최소 1개 항목 이상**이어야 한다(빈 배열 금지) — 다만 억지로 "
                "안 맞는 기법을 끼워 맞추지 말고, 검색 결과 중 이 콘티와 실제로 맞닿는 지점을 "
                "찾아 반영하라(지어내는 것과는 다르다 — 검색은 실제로 하고, 그 결과에서 진짜 "
                "쓸 만한 것을 골라라)."
            )
        else:
            system += (
                " 검색 결과는 참고 자료일 뿐이다 — 그대로 베끼지 말고, 시장에 이미 있는 "
                "연출 관행과 겹치지 않는지 점검하는 용도로 활용하라."
            )
        if n != 9:
            system += " 반드시 호출할 필요는 없다."

    try:
        cps = []
        for c in (module0.get("customprompts") or []):
            if not isinstance(c, dict):
                continue
            try:
                cm = int(c.get("module"))
            except (TypeError, ValueError):
                continue
            cp = str(c.get("prompt") or "").strip()
            if cm == n and cp:
                cps.append(cp)
        if cps:
            system += (f"\n\n---\n\n[사용자 커스텀 지시 — MODULE {n} · 아래 지시는 위의 지시와 충돌하면 우선한다. "
                       "단, 출력 JSON 스키마·형식 규칙은 그대로 유지한다]\n" + "\n\n".join(cps))
    except Exception:
        pass

    # [사용자 요청] 브랜드 광고 목표 가이드라인(cli.py --guideline) — M1(인사이트)·M2(포지셔닝)에만
    # 적용. 시스템 프롬프트의 맨 끝(공통 지침·모듈 지시문·오버라이드·커스텀 지시 뒤)에 붙여
    # 그 위 모든 지시보다 우선하도록 명시한다 — 크롤로 추출된 module0 원시 정보가 이 가이드라인의
    # 공식 타깃/포지셔닝과 어긋나도 가이드라인이 이긴다.
    brandguideline = str(module0.get("brandguideline") or "").strip()
    if n in (1, 2) and brandguideline:
        system += (
            f"\n\n---\n\n[브랜드 광고 목표 가이드라인 — MODULE {n} 최우선 고정 지시. 위의 모든 "
            "지시(공통 운영 지침·모듈 지시문·오버라이드·사용자 커스텀 지시 포함)와 내용이 "
            "충돌하면 이 가이드라인을 따른다. 단, 출력 JSON 스키마·형식 규칙은 그대로 유지한다]\n"
            + brandguideline
        )

    user = _build_user(n, module0, handoffs, review, rerun_hint)

    for attempt in (1, 2):
        try:
            out = llm_adapter.chat_json(system, user, stage=f"M{n}")
            if isinstance(out, dict):
                out = _backfill_legacy(n, out)
            if isinstance(out, dict) and n == 5:
                out = _sanitize_m5_script(out)
            if isinstance(out, dict) and n == 3:
                out["emergentlenses"] = emergent_lenses
                _tag_lens_origin(out, emergent_lenses)
            if isinstance(out, dict) and n == 9 and _normalize_scene_times(out):
                logger.info("[v5_m0_m3 module9] 씬 타임코드 보정됨(0->15 연속 스냅)")
            if isinstance(out, dict) and n == 9 and _ensure_scene_count(out, handoffs):
                logger.info(f"[v5_m0_m3 module9] 씬 개수 보정됨: {len(out.get('scenes') or [])} scenes")
            if isinstance(out, dict) and n == 9 and _reserve_terminal_ending_shot(out):
                logger.info("[v5_m0_m3 module9] Final Shot 예약됨(13->15초)")
            if isinstance(out, dict) and n == 9 and _normalize_shot_times(out):
                logger.info("[v5_m0_m3 module9] 샷(마이크로샷) 타임코드 보정됨(씬 범위 스냅)")
            if isinstance(out, dict) and n == 1 and module0.get("voc"):
                out["evidencelevel"] = (module0.get("voc") or {}).get("level") or "none"

            if attempt == 1 and isinstance(out, dict) and _is_empty_output(n, out):
                logger.warning(f"[v5_m0_m3 module{n}] 빈 골격 응답 감지 -> 채움 지시로 1회 재생성")
                user = user + "\n\n" + _EMPTY_RETRY_HINT
                continue

            if isinstance(out, dict) and n == 9:
                ucv = _usagecut_violation(out)
                scv = _shot_contrast_violation(out)
                rav = _referencedads_violation(out)
                slow9 = video_style.pace_of(video_style.style_of(module0)) == "slow"
                retryviols = "; ".join(v for v in (ucv, "" if slow9 else scv, rav) if v)
                if retryviols and attempt == 1 and not rerun_hint:
                    logger.warning(f"[v5_m0_m3 module9] 계약 위반 -> 1회 재생성: {retryviols}")
                    hint = " ".join(h for v, h in ((ucv, _USAGECUT_RETRY_HINT),
                                                  ("" if slow9 else scv, _SHOT_CONTRAST_RETRY_HINT),
                                                  (rav, _REFERENCEDADS_RETRY_HINT)) if v)
                    user = user + "\n\n" + hint
                    continue
                viols = "; ".join(v for v in (ucv, scv, rav) if v)
                if viols:
                    logger.warning(f"[v5_m0_m3 module9] 계약 미충족(경고만, 통과): {viols}")

            logger.info(f"[v5_m0_m3 module{n}] done: keys={list(out)[:8]}")
            return out if isinstance(out, dict) else {}
        except Exception as e:
            logger.warning(f"[v5_m0_m3 module{n}] err attempt={attempt}: {type(e).__name__}: {e}")
            if attempt == 1:
                continue
        break
    logger.error(f"[v5_m0_m3 module{n}] FAILED after retry -> empty (graceful)")
    return {}


async def run_module(n: int, *, module0: dict, handoffs: dict, review: dict | None = None,
                     rerun_hint: dict | None = None) -> dict:
    """MODULE n 단일 실행 → JSON 핸드오프 dict."""
    return await asyncio.to_thread(
        _run_module_core, n, module0=module0, handoffs=handoffs, review=review, rerun_hint=rerun_hint)
