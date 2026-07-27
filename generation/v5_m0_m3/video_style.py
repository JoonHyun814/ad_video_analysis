"""v5_m0_m3 영상 스타일(촬영/연출 포맷) 프리셋 — M9 콘티 생성기에 주입.

원본(593줄)에서 LLM 자동 선택 기능(pick_style_llm/ensure_style/_recent_styles/run_style 등,
"최근 다른 run 들의 스타일" 반-수렴을 위해 소스 프로젝트의 v5runs DB 테이블을 조회)은 제외했다 —
이 프로젝트엔 그 실행 이력 테이블이 없고, run 이력 자체가 없는 단발 CLI 라 반-수렴 자체가
의미가 없다. 대신 cli_m4_m9.py 의 `--style` 인자로 명시 지정하고(미지정 시 cinematic 기본값),
LLM 자동 선택은 생략했다. STYLES 레지스트리(스타일별 M9 콘티 단편)는 원본 그대로 이식했다.
"""
from __future__ import annotations

DEFAULT = "cinematic"


def _f(ko: str) -> str:
    return "\n\n" + ko


# ── 스타일 레지스트리 (촬영/연출 포맷). M9 콘티 단편만 이식(M10/M11 단편·vp 절은 그 모듈이 이 프로젝트 범위 밖이라 제외). ──
STYLES: dict[str, dict] = {
    "cinematic": {
        "pace": "medium",
        "desc": "premium cinematic look — refined lighting/composition, people optional. Best for luxury/high-price/brand-image.",
        9: _f("[★스타일 = CINEMATIC(프리미엄 시네마틱)]\n"
              "- 씬을 프리미엄 시네마틱하게 설계하라 — 정제된 조명·구도·색감, 높은 프로덕션 밸류.\n"
              "- 인물은 컨셉에 맞게 등장 가능(강제 배제 없음). 제품을 히어로로 두되 사람 있는/없는 구성 모두 허용.\n"
              "- 착용형 제품(시계·액세서리)은 몸에 착용한 모습도, 스탠드 위 모습도 컨셉에 맞게."),
    },
    "ugc": {
        "pace": "fast",
        "desc": "an ordinary user films themselves (selfie/handheld/phone) holding/using/talking about the product. Best for everyday/affordable/social-proof, low-involvement, beauty/food/lifestyle.",
        9: _f("[★스타일 = UGC(인물 중심 후기형)]\n"
              "- 광고티 나는 시네마틱이 아니라 '실사용자가 직접 찍은 후기 영상'처럼 씬을 설계하라.\n"
              "- 인물 1명이 제품을 직접 꺼내·사용·착용·소개. 기본은 핸드헬드/오버더숄더/1인칭 시야.\n"
              "  셀카(전면 카메라)는 ★인물이 카메라에 직접 말 걸거나 제품을 렌즈에 보여주는 순간(도입·리액션·마무리)에만 —\n"
              "  먹기·읽기·보기·작업 등 행동 중에는 셀카 금지(사람은 그런 행동을 하며 자신을 셀카로 찍지 않는다).\n"
              "- 공간은 일상(집·길거리·카페·차 안). 자연광, 약간의 손떨림, lo-fi 폰 카메라 질감. 토킹헤드(발화) 허용.\n"
              "- 톤은 친근·진정성·즉흥성. shot 은 핸드헬드/오버더숄더/POV 위주, 셀카 CU 는 토킹헤드 순간에만."),
    },
    "demo": {
        "pace": "fast",
        "desc": "hands-on demonstration / unboxing, using the product step by step. Best for gadgets/tools/appliances/wearables/function-driven products.",
        9: _f("[★스타일 = DEMO/언박싱]\n"
              "- 손이 제품을 직접 다루는 과정 중심으로 설계하라(개봉·작동·버튼·부착·기능 시연을 단계별로).\n"
              "- 깨끗한 데스크/표면, 또렷한 조명. shot 은 손+제품 클로즈업 위주, 인물 얼굴은 선택.\n"
              "- 제품이 실제로 작동/사용되는 모습을 단계적으로 보여라."),
    },
    "asmr": {
        "pace": "slow",
        "desc": "extreme macro, slow tactile/sensory. Best for texture/sensory products (food, cosmetics, materials).",
        9: _f("[★스타일 = ASMR]\n"
              "- 익스트림 매크로 + 느린 촉각적 동작(질감·표면·소재·따르기·두드리기·미끄러짐) 중심으로 설계하라.\n"
              "- 부드러운 균일 조명, 얕은 심도, 차분하고 느린 템포. 발화·빠른 동작 없음. 감각적·만족감 우선.\n"
              "- shot 은 매크로 CU 위주, 손은 느린 동작에만 등장.\n"
              "- ★사용 완결 컷 의무도 ASMR 톤으로 수행하라 — slow pour/도포 우선, 음식·음료는 입 부분샷의 "
              "느린 한 입/한 모금 1회(지속 씹기 금지)."),
    },
    "testimonial": {
        "pace": "medium",
        "desc": "one person speaks to camera as an interview/review. Best for trust-driven, high-consideration, services.",
        9: _f("[★스타일 = TESTIMONIAL/인터뷰]\n"
              "- 인물 1명이 카메라에 대고 제품 후기를 말하는 구성으로 설계하라(리뷰/인터뷰 톤).\n"
              "- 깔끔한 자연 공간(집·라이트 스튜디오), 아이레벨 미디엄샷, 소프트 자연광, 진정성·신뢰감.\n"
              "- 얼굴·상반신 노출·발화 허용. 제품을 들거나 보여줄 수 있음. UGC보다 정돈된 룩."),
    },
    "vlog": {
        "pace": "fast",
        "desc": "a personal day-in-the-life where the product appears across real daily moments. Best for lifestyle/habitual/relatable products.",
        9: _f("[★스타일 = VLOG(일상/데이인더라이프)]\n"
              "- 인물의 하루 일상 속에 제품이 자연스럽게 등장하는 브이로그식으로 설계하라.\n"
              "- 아침·이동·일·운동·저녁 등 일상 순간들. 1인칭/핸드헬드/오버더숄더, 자연광, 친근·진정성.\n"
              "- 제품을 '쓰는 일상'을 보여라. 얼굴·손·캐주얼 발화 허용."),
    },
    "comparison": {
        "pace": "fast",
        "desc": "side-by-side / split-screen comparison highlighting the product advantage (vs alternative or with-vs-without). Best when differentiation vs alternatives is the key message.",
        9: _f("[★스타일 = COMPARISON(비교/스플릿스크린)]\n"
              "- 제품의 우위를 좌우 분할(split-screen)·AB·순차컷으로 비교해 보여라.\n"
              "- 비교 대상(대안 또는 '없을 때')을 명확히, 제품이 주인공. 인물은 선택(있으면 손/얼굴 자연스럽게).\n"
              "- ★인물 서사(주인공 있는 콘티)라면 인물이 겪는 A/B(쓰기 전의 나 vs 쓴 후의 나)로 비교 구도를 "
              "세워라 — 비교 프레임 안에서 인물·얼굴 등장 허용.\n"
              "- '어느 쪽이 더 낫다'는 메시지는 자막/스크립트가 담당 — 여기선 비교 '구도'만 시각화."),
    },
    "reaction": {
        "pace": "fast",
        "desc": "a person genuinely reacting to the product (first try, surprise, satisfaction). Best for novelty/impulse/wow-factor products.",
        9: _f("[★스타일 = REACTION(반응/첫인상)]\n"
              "- 인물이 제품을 처음 보고/써보고 진짜 반응(놀람·만족)을 보이는 구성으로 설계하라.\n"
              "- 자연스러운 표정·즉흥 반응 포착, 일상 공간. 얼굴·발화 허용.\n"
              "- 제품의 '첫인상 임팩트'가 인물 반응으로 전달되게."),
    },
    "lifestyle": {
        "pace": "medium",
        "desc": "the product used in aspirational real-life situations. Best for brand-image + everyday desirability (fashion, home, F&B, lifestyle).",
        9: _f("[★스타일 = LIFESTYLE(상황 연출)]\n"
              "- 타깃의 실제 삶 속 상황·맥락에서 제품이 쓰이는 모습으로 설계하라.\n"
              "- 동경할 만한 라이프스타일 장면에 제품을 자연스럽게 녹여라. 인물은 맥락 속에.\n"
              "- 화보 느낌이되 자연스러운 상황. 얼굴·손·제품 사용 허용."),
    },
    "howto": {
        "pace": "fast",
        "desc": "step-by-step tutorial teaching how to set up/use the product. Best for products with a learning curve or setup.",
        9: _f("[★스타일 = HOW-TO(튜토리얼)]\n"
              "- 제품 사용/설정 방법을 단계별로 명확히 가르치는 구성으로 설계하라.\n"
              "- 순차적 스텝, 손이 각 단계를 또렷이 수행, 따라하기 쉬운 깔끔한 구도. 얼굴은 선택.\n"
              "- '이렇게 쓰면 된다'가 단계로 전달되게."),
    },
}

VALID = tuple(STYLES.keys())

# ── 편집 페이스(컷 리듬) 프로파일 ──
_PACE_VP_FAST = (
    "- EDITING PACE = FAST (ad-speed cutting): the 15s must read as 8-12 distinct shots — average shot "
    "length 1.5-2s, the hook (first 3s) opens with at least TWO cuts, and only the final packshot may "
    "hold 2-3s. If a storyboard beat runs longer than 2.5s, SPLIT it with a detail-insert cutaway.\n"
)
_PACE_VP_MEDIUM = (
    "- EDITING PACE = MEDIUM (polished ad rhythm): average shot length 1.5-2.5s across the 15s, the "
    "hook (first 3s) contains at least two cuts, and only the final packshot may hold up to 3s.\n"
)
_PACE_VP_SLOW = ""  # 느린 템포가 스타일 정체성(asmr 등) — 페이싱 압박 없음
PACE_VP = {"fast": _PACE_VP_FAST, "medium": _PACE_VP_MEDIUM, "slow": _PACE_VP_SLOW}
DEFAULT_PACE = "medium"


def style_of(module0: dict | None) -> str:
    """이 run 의 스타일 — module0["videostyle"](CLI --style 이 채움). 미지정/무효면 DEFAULT."""
    s = str((module0 or {}).get("videostyle") or "").strip().lower()
    return s if s in STYLES else DEFAULT


def fragment(module_no: int, style: str | None = None) -> str:
    """M9 시스템 프롬프트에 덧붙일 스타일 콘티 단편."""
    return STYLES.get(style or DEFAULT, {}).get(module_no, "")


def pace_of(style: str | None = None) -> str:
    """이 스타일의 편집 페이스(fast|medium|slow). 미지정 스타일은 medium."""
    return str(STYLES.get(style or DEFAULT, STYLES[DEFAULT]).get("pace") or DEFAULT_PACE)


# ── 콘티 자유 구성(free-composition) — M9 콘티 강제(씬수·메타포/데모·제품중심) 완화. 원본 기본 on 고정. ──
_FREECOMPOSE_M9 = (
    "\n\n[★자유 구성 — 콘티 제약 완화]\n"
    "- 씬 수·컷 구성·전환은 콘셉트에 맞게 자유롭게(고정 개수 강제 없음). 단 0~15초를 빠짐없이 덮고 자막/나레이션과 1:1 정렬 유지.\n"
    "- 제품을 화면 중심에 둘지·인물/상황/스토리 중심으로 갈지는 자유(제품 등장 시 이미지의 실제 외형 유지).\n"
    "- 리터럴 시각 메타포·빠른 시연 동작을 '반드시' 넣을 필요 없음 — 콘셉트에 맞으면 쓰고 아니면 다른 연출"
    "(단 ★사용 완결 컷 최소 1컷 의무는 이 완화와 무관하게 유지).\n"
    "- 단 화면 글자 금지·15초·해부학 또렷·Seedance 제약·★편집 리듬(샷 밀도·컷 대비) 절은 그대로 유지."
)


def freecompose_fragment(module_no: int) -> str:
    """M9 콘티 자유구성 단편(씬수·중심·메타포/데모 강제 완화). 원본 V5_FREECOMPOSE 토글 기본값(on) 고정."""
    return _FREECOMPOSE_M9 if module_no == 9 else ""
