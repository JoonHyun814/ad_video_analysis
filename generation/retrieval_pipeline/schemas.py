"""retrieval_pipeline M1(제품·브랜드 인사이트 조사)·M3(장치 생성)·M4(시나리오 완성)·
M5(스토리보드 이미지 생성 계획) 산출물 스키마 — LLM 응답 검증·다음 단계 전달용 pydantic 모델.

M1(product_insight, LLM 1회 — 크롤링/웹 검색/참조 이미지 분석 결과를 종합해 제품 종류·외관·
사용법·기능·재료·브랜드 이미지·타겟을 완성), M3(device_generation, LLM 1회 — 자체적으로
search_chromadb 도구를 여러 번 호출해 근거를 모은 뒤 장치 8개를 완성), M4(scenario_generation,
LLM 1회 — M3 장치 중 골라 조합해 광고 전체 시나리오를 완성), M5(storyboard_generation, LLM 1회 —
M4 시나리오를 스토리보드 이미지 슬롯마다 채울 생성 프롬프트로 전환) 넷의 출력을 다룬다. 필드
네이밍은 이 파이프라인 전용이라 v5_m0_m3(언더바 금지 컨벤션)과 달리 snake_case 를 쓴다.

AdScenarioOutput 은 output/total/*/scenario_analysis.json (기존 분석 산출물) 과 같은 구조
(title/brand/concept/narrative/cast/scenes/key_messages/production_notes)를 그대로 따른다 —
M4 산출물을 그 데이터셋과 같은 형태로 비교·재사용할 수 있게 하기 위해서다(devices_applied 만
이 파이프라인이 추가한 필드).

StoryboardShotPlan 은 generation/AITIVE_스토리보드_틀.html(1.인물/2.제품/3.Environment/4.컷별
4개 섹션만 남긴 이미지 슬롯 중심 틀 — 사용자 요청으로 카메라·조명·촬영 기법·크레딧·메타데이터
는 제외)의 이미지 슬롯 하나하나에 대응하는 "무엇을 채울지" 계획만 담는다. 그 틀 자체는
텍스트를 거의 담지 않으므로(슬롯 캡션 하나가 전부), 실제 지시문은 이 스키마가 들고 있다가
storyboard_codex.py 가 Codex CLI 호출 프롬프트에 그대로 박아 넣는다 — 슬롯 캡션 문자열(예:
"인물1 · 정면", "제품 · 컷1", "컷3")이 이 스키마와 HTML 슬롯을 잇는 매칭 키다.

이 스토리보드의 최종 목적은 Seedance(영상 생성 모델)에 "스토리보드(이미지)" + "프롬프트
(텍스트)"를 함께 넣어 영상을 만드는 것이다(사용자 요청) — 그래서 이 스키마는 두 가지를
분리해서 담는다:
  - 이미지 소싱/생성 브리프(characters/product/environment/cuts[].keyframe_image_prompt):
    스토리보드 틀의 이미지 슬롯을 채우는 데 쓰인다. 인물·환경은 실존하지 않는 콘셉트라
    이미지 생성 프롬프트로 채우지만, 제품은 실물이어야 하므로(사용자 요청 — 사용자가 공급한
    제품 사진을 우선 쓰고, 부족한 각도는 크롤링으로 찾는다) "생성 프롬프트"가 아니라 "이
    슬롯이 무엇을 보여줘야 하는가"를 정하는 소싱 브리프(ProductShotBriefs)로 둔다 — 실물
    자료가 끝내 없을 때만 최후 수단으로 이미지 생성에 쓰인다.
  - 영상 모션 텍스트 프롬프트(cuts[].seedance_prompt): 스토리보드 이미지에는 담기지 않는
    시간에 따른 변화(카메라 무브먼트·인물 동작)만 서술한다. 인물·제품의 외형은 이미 위
    이미지들이 앵커링하므로 여기서 다시 묘사하지 않는다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProductInsight(BaseModel):
    """M1 산출물 — 제품명/URL/가이드 문서/참조 이미지로 조사한 제품·브랜드 인사이트.

    features/materials 는 객관적 사실만 담는다는 전제다(product_insight.py의 프롬프트가
    근거 없는 값 생성을 금지) — 근거가 없으면 빈 배열이 정상이다."""
    product_type: str = ""
    appearance: str = ""
    usage_scenarios: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    current_brand_image: str = ""
    aspirational_brand_image: str = ""
    target_group: str = ""
    misc_notes: list[str] = Field(default_factory=list)
    # 위 7개 필드에 안 들어가는 그 외 객관적 특이사항(예: "추석 기획전", "모델이 출현하지
    # 않음") — 캠페인/시즌 맥락, 참조 자료의 모델 유무 등 뒤 단계(연출 장치·시나리오)가
    # 알아야 할 사실을 캐치올로 담는다.


class ReferenceAdCitation(BaseModel):
    """장치 1개가 실제로 search_chromadb 도구 호출 결과에서 인용한 참조 광고 1건."""
    video_id: int | None = None
    collection: str = ""  # "category_analysis" | "scenario_analysis"


class Device(BaseModel):
    """연출 장치 1개 — 눈에 보이지 않는 가치를 보이는 물리적 사건으로 바꾸는 장치."""
    name: str = ""
    mechanism: str = ""
    why_it_works: str = ""
    reference_ads: list[ReferenceAdCitation] = Field(default_factory=list)
    reference_thinking: str = ""  # "참조광고를 보니 ~하므로 ~의 ~를 가지고와서 ~하게 적용" 형식
    application_draft: str = ""
    impact: int = 0
    production_difficulty: str = ""  # "low" | "mid" | "high"
    concept_fit: int = 0


class DeviceGenerationOutput(BaseModel):
    """M3 산출물 — 크리에이티브 문제 진단 + 장치 8개(근거 포함)."""
    creative_problem: str = ""
    devices: list[Device] = Field(default_factory=list)


class CastMember(BaseModel):
    """등장인물 1명 — scenario_analysis.json 의 cast[] 원소와 동일한 형태."""
    id: str = ""
    description: str = ""


class SceneBeat(BaseModel):
    """컷 1개 안에서 동시에 일어나는 요소 1개(background/camera/action/music/dialogue/
    text_overlay 중 하나). cast 는 action/dialogue 처럼 인물이 결부될 때만 채워진다(쉼표로
    복수 인물 표기, 예: "캐릭터11,캐릭터12") — scenario_analysis.json 의 beats[] 관례와 동일."""
    type: str = ""
    cast: str = ""
    description: str = ""


class Scene(BaseModel):
    """컷 1개 — scenario_analysis.json 의 scenes[] 원소와 동일한 형태."""
    cut_index: int = 0
    time: str = ""  # "0.00~1.10s" 형식
    beats: list[SceneBeat] = Field(default_factory=list)


class DeviceUsage(BaseModel):
    """M3 devices[] 중 이 시나리오가 실제로 골라 쓴 장치 1개 — 어느 컷에서 어떻게 구현됐는지
    추적하기 위한 필드(scenario_analysis.json 원 데이터셋에는 없는, 이 파이프라인 전용 확장)."""
    device_name: str = ""  # devices[].name 그대로
    cut_indices: list[int] = Field(default_factory=list)
    how_applied: str = ""


class AdScenarioOutput(BaseModel):
    """M4 산출물 — M3 장치 중 고른 것을 조합한 광고 전체 시나리오.

    title/brand/concept/narrative/cast/scenes/key_messages/production_notes 는
    output/total/*/scenario_analysis.json 과 동일한 구조(모듈 docstring 참고)."""
    title: str = ""
    brand: str = ""
    concept: str = ""
    narrative: str = ""
    cast: list[CastMember] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    key_messages: list[str] = Field(default_factory=list)
    production_notes: str = ""
    devices_applied: list[DeviceUsage] = Field(default_factory=list)


class CharacterShotPrompts(BaseModel):
    """M4 cast[] 인물 1명에 대해 스토리보드 틀의 이미지 슬롯 3개(정면/측면/의상 착용)를 채울
    이미지 생성 프롬프트 — 인물은 실존하지 않는 콘셉트 캐스팅이라 소싱이 아니라 생성으로
    채운다. 세 프롬프트 모두 같은 사람으로 보이도록 핵심 외형 묘사(헤어·체형·인상·의상)를
    반복하고, 슬롯마다 각도/구도만 바꾼다 — 이미지 생성 모델은 슬롯 간 기억을 공유하지
    않으므로 매 프롬프트가 그 자체로 완결돼야 한다."""
    id: str = ""  # M4 cast[].id 그대로 재사용 — 틀의 슬롯 캡션("인물{n} · 정면" 등)과 매칭되는 키
    front_prompt: str = ""    # 정면 — 표정이 잘 보이는 구도
    profile_prompt: str = ""  # 측면 — 옆모습·목선이 보이는 구도
    costume_prompt: str = ""  # 의상 착용 — 소재·색·핏이 잘 보이는 상반신/전신 구도


class ProductShotBriefs(BaseModel):
    """제품 이미지 슬롯(컷1~3 + 로고) 소싱 브리프 — "무엇을 생성할지"가 아니라 "이 슬롯이
    무엇을 보여줘야 하는지"를 정한다(사용자 요청 — 제품은 실물이어야 하므로 사용자가 공급한
    제품 사진을 우선 배치하고, 브리프가 요구하는 각도가 빠져 있으면 크롤링으로 실제 제품
    사진을 찾아 채운다). shot_briefs 는 정확히 3개 — 서로 다른 각도/사용 상태(정면 히어로·
    라벨 디테일·사용 순간 등)로 다양화한다. 실물 자료를 끝내 확보하지 못했을 때만
    storyboard_codex.py 가 최후 수단으로 이미지 생성에 이 브리프를 쓴다."""
    shot_briefs: list[str] = Field(default_factory=list)
    logo_brief: str = ""  # 브랜드 로고 슬롯 요구사항 — "실물 그대로, 왜곡·재창작 금지"가 기본 전제


class EnvironmentShotPrompt(BaseModel):
    """보드 전체가 공유하는 공간 이미지 슬롯 1개 생성 프롬프트(장소·실내외·시간대·톤 종합) —
    특정 실존 로케이션이 아니라면 인물과 마찬가지로 생성으로 채운다."""
    prompt: str = ""


class CutShotPlan(BaseModel):
    """M4 scenes[] 컷 1개에 대응하는 스토리보드 슬롯 1개 분량의 계획 — 이미지(정지 키프레임)와
    영상 모션 텍스트(Seedance 프롬프트)를 분리해서 담는다(모듈 docstring 참고)."""
    cut_index: int = 0  # M4 scenes[].cut_index 그대로 — 틀의 "컷{n}" 슬롯 캡션과 매칭되는 키
    keyframe_image_prompt: str = ""
    # 이 컷의 스토리보드 슬롯을 채울 정지 이미지 생성 프롬프트 — 그 컷에서 실제로 벌어지는
    # 장면의 대표 순간 하나를 그린다. 등장 인물/제품/공간 묘사는 위 characters/product/
    # environment 에서 이미 고정한 것과 반드시 일치시킨다.
    seedance_prompt: str = ""
    # 위 키프레임 이미지를 시작점으로 영상이 어떻게 움직이는지만 서술하는 모션 텍스트
    # 프롬프트(카메라 무브먼트·인물 동작의 시간적 전개) — 인물/제품의 정적 외형은 이미지가
    # 이미 앵커링하므로 여기서 다시 묘사하지 않는다.


class StoryboardShotPlan(BaseModel):
    """M5 산출물 — generation/AITIVE_스토리보드_틀.html 의 이미지 슬롯마다 채울 계획(모듈
    docstring 참고). 이 스키마 자체는 계획만 정할 뿐 이미지를 생성하거나 영상을 만들지 않는다
    — 실제 이미지 소싱/생성은 storyboard_codex.py(Codex CLI)가, 영상 생성은 Seedance가
    이 계획을 받아 별도로 수행한다."""
    characters: list[CharacterShotPrompts] = Field(default_factory=list)
    product: ProductShotBriefs = Field(default_factory=ProductShotBriefs)
    environment: EnvironmentShotPrompt = Field(default_factory=EnvironmentShotPrompt)
    cuts: list[CutShotPlan] = Field(default_factory=list)
