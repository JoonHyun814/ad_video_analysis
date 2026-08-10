"""retrieval_pipeline M3(장치 생성) 산출물 스키마 — LLM 응답 검증·다음 단계 전달용 pydantic 모델.

M3(device_generation, LLM 1회 — 자체적으로 search_chromadb 도구를 여러 번 호출해 근거를 모은 뒤
장치 8개를 완성) 하나의 출력만 다룬다. 필드 네이밍은 이 파이프라인 전용이라 v5_m0_m3
(언더바 금지 컨벤션)과 달리 snake_case 를 쓴다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


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
