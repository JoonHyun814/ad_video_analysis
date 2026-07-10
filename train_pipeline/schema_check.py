"""video_id 폴더의 scene/cut/scenario 분석이 cuts.json 기준 구조·완전성을 만족하는지 검사한다.

check_analysis.py 는 parse_failed(에러 마커) 여부만 본다. 컷 수 불일치, 시나리오 누락,
필드 공백 같은 "문법은 멀쩡한데 내용이 잘못된" 결함은 잡지 못한다. 이 모듈이 그 빈틈을 메운다.
"""

import json
from pathlib import Path

_SCENE_FIELDS = ("foreground", "background", "camera", "mood", "text_overlay")
_CUT_FIELDS = ("flow", "subjects", "cast", "camera", "text_flow", "mood_shift")
_SCENARIO_FIELDS = ("title", "brand", "concept", "narrative", "cast", "scenes", "key_messages", "production_notes")


def _load(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _valid_entries(entries) -> list[dict]:
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict) and not e.get("error")]


def _missing_fields(entry: dict, fields: tuple[str, ...]) -> list[str]:
    return [f for f in fields if not str(entry.get(f, "")).strip()]


def check_video_structure(video_dir: Path) -> dict:
    """video_dir 하나의 scene/cut/scenario 분석 구조를 cuts.json 기준으로 검사해 리포트를 반환한다."""
    cuts = _load(video_dir / "cuts.json") or []
    expected = len(cuts)

    scene = _valid_entries(_load(video_dir / "scene_analysis.json"))
    cut = _valid_entries(_load(video_dir / "cut_analysis.json"))
    scenario = _load(video_dir / "scenario_analysis.json")
    scenario_ok = isinstance(scenario, dict) and not scenario.get("error")

    return {
        "video_id": video_dir.name,
        "expected_cuts": expected,
        "scene_count": len(scene),
        "scene_count_ok": len(scene) == expected,
        "scene_field_gaps": sum(1 for e in scene if _missing_fields(e, _SCENE_FIELDS)),
        "cut_count": len(cut),
        "cut_count_ok": len(cut) == expected,
        "cut_field_gaps": sum(1 for e in cut if _missing_fields(e, _CUT_FIELDS)),
        "scenario_present": scenario_ok,
        "scenario_scenes_ok": scenario_ok and len(scenario.get("scenes", [])) == expected,
        "scenario_field_gaps": len(_missing_fields(scenario, _SCENARIO_FIELDS)) if scenario_ok else len(_SCENARIO_FIELDS),
    }
