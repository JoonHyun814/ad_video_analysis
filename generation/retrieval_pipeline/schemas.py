"""retrieval_pipeline M3~M7 산출물 스키마 — LLM 응답 검증·다음 단계 전달용 pydantic 모델.

M3(concept_scout, LLM 5회 — 컨셉 후보 1 + 페르소나 1 + 페르소나별 순위 3) → M3Output(생성/
docs/m3_concept.md 의 7개 발산 기법별 컨셉 후보 + 타깃 페르소나 3명이 각자 매긴 순위를 취합한
최종 순위) → M4(query_scout, LLM) → M4Output(creative_problem + queries[]) → M5(retrieval, 코드)
→ 쿼리별 검색 결과 → M6(device_synthesis, LLM) → 쿼리 1건당 QueryDevice 1개 → M7(storyline, LLM)
→ StorylineOutput(스토리라인 조립 + 자가진단 gap_assessment) → render_markdown(코드) → 최종 문서.
필드 네이밍은 이 파이프라인 전용이라 v5_m0_m3(언더바 금지 컨벤션)과 달리 snake_case 를 쓴다.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _coerce_str(v: Any) -> Any:
    """LLM이 문자열 필드에 리스트(예: `["...", "..."]`)를 넣을 때를 대비한 경계 방어 — 시스템
    경계(외부 LLM 출력)라 CLAUDE.md 의 "시스템 경계에서만 검증" 원칙에 해당한다. 리스트면 각
    항목을 " / " 로 이어붙인 문자열로 만든다."""
    if isinstance(v, list):
        return " / ".join(str(x) for x in v)
    return v


_SCORE_WORDS = (
    # 복합 표현(mid-high 등)을 그 부분 문자열(mid/high)보다 먼저 검사해야 한다 — 순서 중요.
    ("very high", 5), ("highest", 5),
    ("mid-high", 4), ("medium-high", 4),
    ("mid-low", 2), ("medium-low", 2),
    ("very low", 1),
    ("high", 4),
    ("medium", 3), ("mid", 3),
    ("low", 1),
)


def _coerce_score(v: Any) -> Any:
    """LLM이 1~5(또는 1~7) 정수 점수 필드에 "high — 반전의 감정선이 강하다" 처럼 설명이 섞인
    문자열을 넣을 때를 대비한 경계 방어(시스템 경계 — CLAUDE.md "시스템 경계에서만 검증" 원칙).
    문자열 안의 첫 숫자를 우선 쓰고, 숫자가 없으면 high/mid/low 류 표현을 정수로 매핑한다.
    둘 다 실패하면 원본을 그대로 반환해 pydantic 이 명확한 에러를 내게 둔다(무리한 추측 방지)."""
    if not isinstance(v, str):
        return v
    m = re.search(r"\d+", v)
    if m:
        return int(m.group())
    low = v.lower()
    for word, val in _SCORE_WORDS:
        if word in low:
            return val
    return v


class ConceptCandidate(BaseModel):
    """generation/docs/m3_concept.md 의 발산 기법 1개로 만든 한 줄 크리에이티브 컨셉 후보
    (아직 순위 없음 — 순위는 페르소나별 서브 에이전트가 매긴다)."""
    technique: str = ""       # 예: "경험 은유", "PAS 모델" — m3_concept.md 표의 기법명 그대로
    concept_line: str = ""    # "~을 보여주지 말고 ~을 보여줘라" 형식의 한 줄 원칙(M4 입력이 됨)
    grounding: str = ""       # 이 컨셉이 M0~M2 의 어느 근거(타깃/human truth/포지셔닝 등)에서 나왔는지 1문장


class ConceptScoutOutput(BaseModel):
    """concept_scout.run_candidates() 산출물 — 정확히 7개(발산 기법당 1개)."""
    concepts: list[ConceptCandidate] = Field(default_factory=list)


class Persona(BaseModel):
    """M3가 컨셉 순위를 매기기 위해 만든, 타깃 그룹 안의 서로 다른 관점을 대표하는 페르소나 1명."""
    name: str = ""       # 짧은 라벨(예: "따라가는 다수파", "손해회피 예민형")
    profile: str = ""    # 이 페르소나의 상황·특징 요약
    priorities: str = ""  # 광고를 볼 때 이 페르소나가 중요하게 여기는 것
    grounding: str = ""   # M1 target/human_truth 등 어느 근거에서 이 페르소나를 뽑았는지


class PersonaScoutOutput(BaseModel):
    """concept_scout.run_personas() 산출물 — 정확히 3명."""
    personas: list[Persona] = Field(default_factory=list)


class PersonaConceptRank(BaseModel):
    """페르소나 1명이 컨셉 후보 1개(technique 로 식별)에 매긴 순위."""
    technique: str = ""
    rank: int = 0                    # 1이 최우선, 7개가 서로 다른 순위(동점 없음)
    appropriateness_score: int = 0   # 1~5, 이 페르소나에게 얼마나 와닿는가
    evaluation_note: str = ""        # 이 페르소나 입장에서 왜 이 순위인지

    @field_validator("rank", "appropriateness_score", mode="before")
    @classmethod
    def _coerce_score_field(cls, v: Any) -> Any:
        return _coerce_score(v)


class PersonaRankingOutput(BaseModel):
    """concept_scout.run_persona_ranking() 산출물 — 페르소나 1명이 7개 컨셉 전부에 매긴 순위."""
    rankings: list[PersonaConceptRank] = Field(default_factory=list)


class RankedConcept(BaseModel):
    """M3 최종 산출물의 컨셉 1개 — 3명의 페르소나 순위를 코드가 평균으로 취합한 결과."""
    technique: str = ""
    concept_line: str = ""
    grounding: str = ""
    persona_ranks: list[dict[str, Any]] = Field(default_factory=list)  # [{persona,rank,appropriateness_score,evaluation_note}]
    aggregate_rank: int = 0     # 1이 최우선 — 취합 후 최종 순위(동점 없음)
    average_rank: float = 0.0   # 페르소나 3명의 rank 평균(낮을수록 좋음, 참고용 원값)
    average_score: float = 0.0  # 페르소나 3명의 appropriateness_score 평균(참고용 원값)


class M3Output(BaseModel):
    """M3 최종 산출물 — 페르소나 3명 + 컨셉 7개(aggregate_rank 오름차순 정렬)."""
    personas: list[Persona] = Field(default_factory=list)
    concepts: list[RankedConcept] = Field(default_factory=list)


class SearchQuery(BaseModel):
    """generation/docs/검색기준.txt·검색기준2.txt 의 축(구조·톤무드·샷기술) 중 하나에 속하는
    검색 쿼리 1건 — M7 의 gap_assessment.additional_queries 도 같은 스키마를 재사용한다(추가
    검색 라운드가 M4를 다시 부르지 않고 이 형태를 그대로 M5 입력으로 쓰기 위해)."""
    axis: str = ""  # "narrative_form" | "tone_mood" | "shot_technique"
    label: str = ""
    rationale: str = ""
    query_text: str = ""
    target_collection: str = "production"  # "production" | "concept"


class M4Output(BaseModel):
    """M4(query_scout) 산출물 — 아직 검색은 실행되지 않은 상태."""
    creative_problem: str = ""
    queries: list[SearchQuery] = Field(default_factory=list)


class ReferenceAdCitation(BaseModel):
    """장치 1개가 실제로 인용한 참조 광고 1건."""
    video_id: int | None = None
    how_it_relates: str = ""


class QueryDevice(BaseModel):
    """M6(device_synthesis) 이 쿼리 1건의 검색 결과로부터 만든 연출 장치 1개 — 그 쿼리의
    검색 결과에만 근거한다(다른 쿼리 결과와 섞지 않음)."""
    query_label: str = ""
    axis: str = ""
    name: str = ""
    mechanism: str = ""
    why_it_works: str = ""
    reference_ads: list[ReferenceAdCitation] = Field(default_factory=list)
    application_draft: str = ""
    impact: int = 0
    production_difficulty: str = ""  # "low" | "mid" | "high"
    concept_fit: int = 0

    @field_validator("impact", "concept_fit", mode="before")
    @classmethod
    def _coerce_score_field(cls, v: Any) -> Any:
        return _coerce_score(v)


class M6Output(BaseModel):
    """M6 산출물 — 입력 쿼리 개수만큼의 장치 목록(순서는 입력 쿼리 순서와 동일)."""
    devices: list[QueryDevice] = Field(default_factory=list)


class StorylineBeat(BaseModel):
    """스토리라인 1개 안의 시간 구간 1개."""
    time_range: str = ""
    content: str = ""
    device_tags: list[str] = Field(default_factory=list)


class Storyline(BaseModel):
    """대안 스토리라인 1안."""
    label: str = ""
    one_liner: str = ""
    devices_used: list[str] = Field(default_factory=list)
    structure: list[StorylineBeat] = Field(default_factory=list)
    strengths: str = ""
    weaknesses: str = ""
    difficulty: str = ""

    @field_validator("strengths", "weaknesses", mode="before")
    @classmethod
    def _coerce_list_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class ComparisonRow(BaseModel):
    """스토리라인 비교표 1행."""
    label: str = ""
    impact: int = 0
    concept_fit: int = 0
    difficulty: str = ""

    @field_validator("impact", "concept_fit", mode="before")
    @classmethod
    def _coerce_score_field(cls, v: Any) -> Any:
        return _coerce_score(v)


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


class GapAssessment(BaseModel):
    """M7(storyline) 이 지금 가진 장치만으로 스토리라인을 만들기 충분한지 스스로 판단한 결과.

    sufficient=False 면 additional_queries 를 근거로 M5~M6 를 한 번 더 돌려 장치를 보강한다
    (pipeline.run_m7() 의 재시도 루프가 이 필드를 읽는다 — 사용자 요청: "m7 가 끝난 후 LLM 이
    스스로 연출이 부족하다고 느낄 경우 추가 참조를 위한 retrieval을 할 수 있도록")."""
    sufficient: bool = True
    note: str = ""
    additional_queries: list[SearchQuery] = Field(default_factory=list)


class StorylineOutput(BaseModel):
    """M7 최종 산출물 — render_markdown.py 가 devices 와 함께 DBH 문서 형식으로 렌더링한다."""
    storylines: list[Storyline] = Field(default_factory=list)
    comparison: list[ComparisonRow] = Field(default_factory=list)
    recommendation: Recommendation = Field(default_factory=Recommendation)
    common_checks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    gap_assessment: GapAssessment = Field(default_factory=GapAssessment)
