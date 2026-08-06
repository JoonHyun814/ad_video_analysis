"""retrieval_pipeline M4~M7 산출물 스키마 — LLM 응답 검증·다음 단계 전달용 pydantic 모델.

M4(device_scout, LLM) → DeviceScoutOutput → M5(retrieval, 코드) → M6(synthesis, LLM) →
M4SynthesisOutput → M7(render_markdown, 코드). 필드 네이밍은 이 파이프라인 전용이라
v5_m0_m3(언더바 금지 컨벤션)과 달리 snake_case 를 쓴다.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class DeviceQuery(BaseModel):
    """연출 장치 후보 1개 + 그 장치의 근거를 찾기 위한 검색 쿼리."""
    name: str = ""
    mechanism: str = ""
    query_text: str = ""
    target_collection: str = "production"  # "production" | "concept"


class DeviceScoutOutput(BaseModel):
    """1차 LLM 호출(device_scout) 산출물 — 아직 검색은 실행되지 않은 상태."""
    creative_problem: str = ""
    devices: list[DeviceQuery] = Field(default_factory=list)


class ReferenceAdCitation(BaseModel):
    """장치 1개가 실제로 인용한 참조 광고 1건."""
    video_id: int | None = None
    how_it_relates: str = ""


class SynthesizedDevice(BaseModel):
    """2차 LLM 호출이 완성한 장치 1개 — DBH 문서의 '장치 ①~⑧' 절에 대응."""
    name: str = ""
    mechanism: str = ""
    why_it_works: str = ""
    reference_ads: list[ReferenceAdCitation] = Field(default_factory=list)
    application_draft: str = ""
    impact: int = 0
    production_difficulty: str = ""  # "low" | "mid" | "high"
    concept_fit: int = 0


class StorylineBeat(BaseModel):
    """스토리라인 1개 안의 시간 구간 1개 — DBH 문서의 하이브리드 타임라인 표에 대응."""
    time_range: str = ""
    content: str = ""
    device_tags: list[str] = Field(default_factory=list)


class Storyline(BaseModel):
    """15초(또는 지정 길이) 대안 스토리라인 1안 — DBH 문서의 '안 A/B/C/D'에 대응."""
    label: str = ""
    one_liner: str = ""
    devices_used: list[str] = Field(default_factory=list)
    structure: list[StorylineBeat] = Field(default_factory=list)
    strengths: str = ""
    weaknesses: str = ""
    difficulty: str = ""


class ComparisonRow(BaseModel):
    """스토리라인 비교표 1행."""
    label: str = ""
    impact: int = 0
    concept_fit: int = 0
    difficulty: str = ""


class Recommendation(BaseModel):
    """최종 권고 — 하이브리드 조합 또는 단일 안 선택."""
    choice: str = ""
    rationale: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_plain_string(cls, v: Any) -> Any:
        """LLM이 프롬프트 지시(객체 형식)를 무시하고 문장 하나로 답할 때를 대비한 경계 방어
        — 시스템 경계(외부 LLM 출력)라 CLAUDE.md 의 "시스템 경계에서만 검증" 원칙에 해당한다."""
        return {"choice": "", "rationale": v} if isinstance(v, str) else v


class M4SynthesisOutput(BaseModel):
    """M4 최종 산출물 — render_markdown.py 가 이 구조를 DBH 문서 형식으로 렌더링한다."""
    creative_problem: str = ""
    devices: list[SynthesizedDevice] = Field(default_factory=list)
    storylines: list[Storyline] = Field(default_factory=list)
    comparison: list[ComparisonRow] = Field(default_factory=list)
    recommendation: Recommendation = Field(default_factory=Recommendation)
    common_checks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
