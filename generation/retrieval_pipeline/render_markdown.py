"""M7 부속 — QueryDevice 목록 + StorylineOutput(M7 산출물) → 사람이 읽는 문서로 렌더링한다(LLM 아님).

generation/docs/DBH_Creative_Reference_Ideas.md 와 같은 절 구성(문제 진단 → 장치별 레퍼런스 →
대안 스토리라인 → 비교/권고 → 공통 체크 → 다음 단계)을 그대로 따른다 — 이 파이프라인이 그
문서의 제작 과정을 재현한다는 것을 산출물 형태로도 보여주기 위해서다.
"""
from __future__ import annotations

from generation.retrieval_pipeline.schemas import QueryDevice, StorylineOutput

_STARS = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}
_AXIS_LABEL = {"narrative_form": "구조", "tone_mood": "톤·무드", "shot_technique": "샷·기술"}


def _stars(n: int) -> str:
    return _STARS.get(max(0, min(5, int(n or 0))), "☆")


def _device_section(idx: int, d: QueryDevice) -> str:
    circled = "①②③④⑤⑥⑦⑧⑨⑩"[idx] if idx < 10 else str(idx + 1)
    axis_label = _AXIS_LABEL.get(d.axis, d.axis or "-")
    if d.reference_ads:
        refs = "; ".join(f"video_id={r.video_id} — {r.how_it_relates}" for r in d.reference_ads)
    else:
        refs = "레퍼런스 미발견 — 원칙만 적용"
    return (
        f"### 장치 {circled} {d.name} [{axis_label} · {d.query_label}]\n"
        f"**메커니즘:** {d.mechanism}\n\n"
        f"**레퍼런스:** {refs}\n\n"
        f"**왜 강력한가:** {d.why_it_works}\n\n"
        f"**적용:** {d.application_draft}\n\n"
        "| 임팩트 | 제작 난도 | 컨셉 적합도 |\n|---|---|---|\n"
        f"| {_stars(d.impact)} | {d.production_difficulty} | {_stars(d.concept_fit)} |\n"
    )


def _storyline_section(s) -> str:
    rows = "\n".join(f"| {b.time_range} | {b.content} | {', '.join(b.device_tags)} |" for b in s.structure)
    header = "| 시간 | 내용 | 사용 장치 |\n|---|---|---|\n" if s.structure else ""
    return (
        f"### {s.label}\n"
        f"**한 줄:** {s.one_liner}\n\n"
        f"**사용 장치:** {', '.join(s.devices_used)}\n\n"
        f"{header}{rows}\n\n"
        f"- **강점:** {s.strengths}\n"
        f"- **약점:** {s.weaknesses}\n"
        f"- **난도:** {s.difficulty}\n"
    )


def render(concept_line: str, ad_length: str, creative_problem: str,
          devices: list[QueryDevice], output: StorylineOutput) -> str:
    """DBH_Creative_Reference_Ideas.md 형식의 Markdown 문서 전체를 문자열로 반환한다."""
    parts: list[str] = [
        "# 크리에이티브 레퍼런스 · 연출 아이디어",
        f"### 「{concept_line}」을 임팩트 있게 만드는 법 ({ad_length})\n",
        "> 작성: generation/retrieval_pipeline(자동 생성) · 근거: 자사 광고 벡터 DB 검색 결과\n",
        "---\n## 0. 우리가 풀어야 하는 크리에이티브 문제\n",
        f"> **「{concept_line}」**\n",
        f"{creative_problem}\n",
        "---\n## 1. 연출 장치 — 레퍼런스와 적용\n",
    ]
    for i, d in enumerate(devices):
        parts.append(_device_section(i, d))
    parts.append(f"\n---\n## 2. {ad_length} 대안 스토리라인\n")
    for s in output.storylines:
        parts.append(_storyline_section(s))
    parts.append("\n---\n## 3. 비교와 권고\n")
    if output.comparison:
        story_labels = [s.label for s in output.storylines]
        parts.append("| 안 | 임팩트 | 컨셉 적합도 | 제작 난도 |\n|---|---|---|---|")
        parts.extend(
            f"| {r.label or (story_labels[i] if i < len(story_labels) else '')} | "
            f"{_stars(r.impact)} | {_stars(r.concept_fit)} | {r.difficulty} |"
            for i, r in enumerate(output.comparison)
        )
    parts.append(f"\n**권고:** {output.recommendation.choice}\n\n{output.recommendation.rationale}\n")
    parts.append("\n---\n## 4. 공통 체크\n")
    parts.extend(f"- {c}" for c in output.common_checks)
    parts.append("\n---\n## 5. 다음 단계\n")
    parts.extend(f"{i + 1}. {step}" for i, step in enumerate(output.next_steps))
    if not output.gap_assessment.sufficient:
        parts.append("\n---\n## 부록. 추가 리서치 필요 노트\n")
        parts.append(f"{output.gap_assessment.note}\n")
    return "\n".join(parts) + "\n"
