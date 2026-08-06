"""M3 — generation/docs/m3_concept.md 의 발산 기법 7종으로 컨셉 후보를 만들고, 타깃 그룹에
맞는 페르소나 3명이 각자 독립적으로 순위를 매긴 뒤 코드가 취합한다(사용자 요청 — "컨셉 순위를
매길 때, target 그룹에 맞는 3종류의 페르소나 생성 -> 각 페르소나 별 서브 에이전트로 순위를
매김 -> 최종 결과 취합").

    1) run_candidates()      LLM 1회 — 발산 기법 7종 → 컨셉 후보 7개(아직 순위 없음)
    2) run_personas()        LLM 1회 — 타깃 그룹 안에서 서로 다른 페르소나 3명
    3) run_persona_ranking() LLM 1회 x3(페르소나마다) — "서브 에이전트": 각 호출이 그 페르소나
       하나의 시점만 가지고(다른 페르소나 존재를 모른 채) 7개 컨셉 전부에 독립적으로 순위를
       매긴다. 이 파이프라인은 Claude Code 의 Agent 툴이 아니라 generation.v5_m0_m3.llm_adapter
       를 통한 개별 LLM 호출로 "서브 에이전트"를 구현한다 — M4~M7 의 다른 LLM 호출들과 같은
       인프라를 쓴다(무상태·독립 호출이라는 점에서 서브 에이전트의 성격을 satisfy 한다).
    4) _aggregate()          코드, 결정적(LLM 아님) — 3명의 rank/score 를 평균해 최종 순위를
       정한다. retrieval.py(M5)가 "검색 실행은 코드가 결정적으로 한다"는 이 파이프라인의 원칙과
       같은 이유로, 최종 취합은 LLM 의 추가 판단이 아니라 코드가 명시적 규칙(평균 순위 오름차순,
       동점이면 평균 점수 내림차순)으로 수행해 결과를 항상 재현 가능하게 한다.

run_concept_scout() 이 위 네 단계를 순서대로 실행해 최종 M3Output 과, 각 단계가 실제로 보낸
프롬프트(투명성 유지) 를 함께 반환한다.
"""
from __future__ import annotations

import json
from typing import Any

from generation.retrieval_pipeline import prompt_loader
from generation.retrieval_pipeline.schemas import (
    ConceptCandidate,
    ConceptScoutOutput,
    M3Output,
    Persona,
    PersonaRankingOutput,
    PersonaScoutOutput,
    RankedConcept,
)
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M3"


def _call_json(system: str, user: str) -> dict[str, Any]:
    raw = llm_adapter.chat_json(system, user, stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        # query_scout.run_query_scout() 와 동일한 이유로 조용히 빈 결과를 만들지 않는다.
        raise RuntimeError(f"M3 LLM 호출 실패: {raw.get('error')} - {str(raw.get('raw', ''))[:300]}")
    return raw


def run_candidates(context: dict[str, Any]) -> tuple[ConceptScoutOutput, dict[str, str]]:
    """1단계 — 발산 기법 7종으로 컨셉 후보 7개를 만든다(순위 없음)."""
    system = prompt_loader.load("m3_concepts_system.md")
    user = prompt_loader.fill(prompt_loader.load("m3_concepts_user.md"), {
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
    })
    raw = _call_json(system, user)
    return ConceptScoutOutput.model_validate(raw), {"system": system, "user": user}


def run_personas(context: dict[str, Any]) -> tuple[PersonaScoutOutput, dict[str, str]]:
    """2단계 — 타깃 그룹 안에서 서로 다른 관점을 가진 페르소나 3명을 만든다."""
    system = prompt_loader.load("m3_personas_system.md")
    user = prompt_loader.fill(prompt_loader.load("m3_personas_user.md"), {
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
    })
    raw = _call_json(system, user)
    return PersonaScoutOutput.model_validate(raw), {"system": system, "user": user}


def run_persona_ranking(persona: Persona, candidates: list[ConceptCandidate], context: dict[str, Any]
                        ) -> tuple[PersonaRankingOutput, dict[str, str]]:
    """3단계(서브 에이전트) — 페르소나 1명의 시점으로 컨셉 후보 7개 전부에 순위를 매긴다."""
    system = prompt_loader.load("m3_persona_rank_system.md")
    user = prompt_loader.fill(prompt_loader.load("m3_persona_rank_user.md"), {
        "persona_json": json.dumps(persona.model_dump(), ensure_ascii=False, indent=2),
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
        "concepts_json": json.dumps([c.model_dump() for c in candidates], ensure_ascii=False, indent=2),
    })
    raw = _call_json(system, user)
    return PersonaRankingOutput.model_validate(raw), {"system": system, "user": user}


def _aggregate(candidates: list[ConceptCandidate], personas: list[Persona],
               persona_rankings: list[PersonaRankingOutput]) -> list[RankedConcept]:
    """4단계 — 페르소나별 순위를 평균해 최종 순위를 매긴다(결정적, LLM 아님).

    평균 순위(낮을수록 좋음)가 우선 기준, 동점이면 평균 적절성 점수(높을수록 좋음)로 가른다.
    페르소나가 그 컨셉에 순위를 안 남겼으면(모델이 누락) 그 컨셉은 최하위로 취급한다.
    """
    by_technique: dict[str, list[dict[str, Any]]] = {c.technique: [] for c in candidates}
    for persona, ranking in zip(personas, persona_rankings):
        for r in ranking.rankings:
            if r.technique in by_technique:
                by_technique[r.technique].append({
                    "persona": persona.name, "rank": r.rank,
                    "appropriateness_score": r.appropriateness_score,
                    "evaluation_note": r.evaluation_note,
                })

    n_personas = max(len(personas), 1)
    worst_rank = len(candidates) + 1
    scored: list[tuple[float, float, ConceptCandidate, list[dict[str, Any]], float, float]] = []
    for c in candidates:
        entries = by_technique.get(c.technique, [])
        avg_rank = sum(e["rank"] for e in entries) / len(entries) if entries else float(worst_rank)
        avg_score = sum(e["appropriateness_score"] for e in entries) / len(entries) if entries else 0.0
        scored.append((avg_rank, -avg_score, c, entries, avg_rank, avg_score))
    scored.sort(key=lambda t: (t[0], t[1]))

    return [
        RankedConcept(
            technique=c.technique, concept_line=c.concept_line, grounding=c.grounding,
            persona_ranks=entries, aggregate_rank=i + 1,
            average_rank=round(avg_rank, 2), average_score=round(avg_score, 2),
        )
        for i, (_, _, c, entries, avg_rank, avg_score) in enumerate(scored)
    ]


def run_concept_scout(context: dict[str, Any]) -> tuple[M3Output, dict[str, Any]]:
    """M3 전체 흐름(컨셉 생성 → 페르소나 생성 → 페르소나별 순위 → 취합)을 순서대로 실행한다."""
    cand_output, cand_prompt = run_candidates(context)
    persona_output, persona_prompt = run_personas(context)

    persona_rankings: list[PersonaRankingOutput] = []
    ranking_prompts: list[dict[str, str]] = []
    for persona in persona_output.personas:
        ranking, prompt = run_persona_ranking(persona, cand_output.concepts, context)
        persona_rankings.append(ranking)
        ranking_prompts.append({"persona": persona.name, **prompt})

    ranked = _aggregate(cand_output.concepts, persona_output.personas, persona_rankings)
    output = M3Output(personas=persona_output.personas, concepts=ranked)
    prompts = {
        "candidates_prompt": cand_prompt,
        "personas_prompt": persona_prompt,
        "persona_ranking_prompts": ranking_prompts,
    }
    return output, prompts
