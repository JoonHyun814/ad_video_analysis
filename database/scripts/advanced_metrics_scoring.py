"""advanced_metrics.py 의 claude -p 원시 응답에서 점수를 계산한다.

정답 판정(expected==actual, 순차 매칭 시 첫 불일치 지점, 전체 일치 여부)은 LLM 이 아니라
여기서 코드로 계산한다 — compare_scenario.py 의 cut_count 처리와 같은 원칙: 셀 수 있는 값을
LLM 산술에 맡기면 신뢰도가 떨어진다.
"""
from typing import Any

_SEQUENTIAL_DIMENSIONS = ("complex_plot", "complex_landscape")
_QA_DIMENSIONS = ("dynamic_attribute", "dynamic_spatial_relationship", "motion_rationality")
_DIMENSION_KEYS = _SEQUENTIAL_DIMENSIONS + _QA_DIMENSIONS + ("human_interaction", "motion_order_understanding")


def score_t2vscore_a(elements: list[dict[str, Any]]) -> dict[str, Any]:
    """T2VScore-A(Eq.1): 검증된 요소 수 / 전체 요소 수."""
    total = len(elements)
    verified = sum(1 for e in elements if e.get("verified") is True)
    return {
        "elements": elements,
        "verified_count": verified,
        "total_count": total,
        "score": round(verified / total, 3) if total else None,
    }


def score_vbench2(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """VBench-2.0 서브셋 7개 차원을 각각 채점한다."""
    return {key: _score_dimension(key, raw.get(key) or {}) for key in _DIMENSION_KEYS}


def _score_dimension(key: str, data: dict[str, Any]) -> dict[str, Any]:
    if not data.get("applicable"):
        return {"applicable": False, "score": None, "evidence": data.get("evidence", "")}
    if key in _SEQUENTIAL_DIMENSIONS:
        return _score_sequential(data)
    if key in _QA_DIMENSIONS:
        return _score_qa(data)
    if key == "human_interaction":
        return _score_binary(data)
    return _score_motion_order(data)


def _score_sequential(data: dict[str, Any]) -> dict[str, Any]:
    """VBench-2.0 Complex Plot/Landscape: 앞에서부터 순서대로 맞은 비트 비율(첫 불일치 지점에서 중단)."""
    elements = data.get("elements") or []
    matched = 0
    for e in elements:
        if e.get("matched") is not True:
            break
        matched += 1
    total = len(elements)
    return {
        "applicable": True,
        "elements": elements,
        "matched_count": matched,
        "total_count": total,
        "score": round(matched / total, 3) if total else None,
        "evidence": data.get("evidence", ""),
    }


def _score_qa(data: dict[str, Any]) -> dict[str, Any]:
    """VBench-2.0 Dynamic Attribute/Spatial Relationship/Motion Rationality: redundant Q&A 정답률."""
    questions = list(data.get("questions") or [])
    for q in questions:
        q["correct"] = q.get("expected") == q.get("actual")
    total = len(questions)
    correct = sum(1 for q in questions if q["correct"])
    result = {k: v for k, v in data.items() if k not in ("applicable", "questions")}
    result.update({
        "applicable": True,
        "questions": questions,
        "score": round(correct / total, 3) if total else None,
    })
    return result


def _score_binary(data: dict[str, Any]) -> dict[str, Any]:
    """VBench-2.0 Human Interaction: 단일 이진 판정."""
    return {
        "applicable": True,
        "expected": data.get("expected"),
        "actual": data.get("actual"),
        "score": 1.0 if data.get("match") is True else 0.0,
        "evidence": data.get("evidence", ""),
    }


def _score_motion_order(data: dict[str, Any]) -> dict[str, Any]:
    """VBench-2.0 Motion Order Understanding: 모든 동작이 순서대로 맞아야 1.0(paper 원칙)."""
    actions = data.get("actions") or []
    all_matched = bool(actions) and all(a.get("order_matched") is True for a in actions)
    return {
        "applicable": True,
        "actions": actions,
        "score": 1.0 if all_matched else 0.0,
        "evidence": data.get("evidence", ""),
    }
