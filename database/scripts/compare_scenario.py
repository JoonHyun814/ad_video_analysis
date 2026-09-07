"""완성 영상을 재분석한 scenario_analysis 와 원본(prompt+스토리보드+이미지)을 비교한다.

claude -p 에 스토리보드 이미지 디렉토리를 --add-dir 로 열어줘야 하므로 utils.llm_caller.call_claude
(공통 헬퍼)를 쓰지 않는다 — pipeline/cast_analysis.py·scene_analysis.py 와 동일한 예외(참고:
utils/README.md).
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils.json_utils import parse_json  # noqa: E402

from matching import MatchedUnit  # noqa: E402

_LLM_FACTOR_KEYS = (
    "cut_order", "character_count", "character_appearance",
    "scene_description", "dialogue", "text_overlay",
    "scene_duration", "brand_logo_exposure",
)

_SCHEMA = (
    '{"cut_order": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "character_count": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "character_appearance": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "scene_description": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "dialogue": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "text_overlay": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "scene_duration": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "brand_logo_exposure": {"match": true, "expected": "...", "actual": "...", "evidence": "..."},'
    ' "summary": "전체 비교 총평 2~3문장"}'
)


def compare_scenario(unit: MatchedUnit, scenario: dict[str, Any], images_dir: Path, timeout: int = 600) -> dict[str, Any]:
    """원본 스토리보드(이미지 포함)·prompt 와 생성된 scenario_analysis 를 비교해 요인별 판정을 반환한다.

    cut_count 는 스토리보드 shots 합계 vs scenario_analysis.scenes 개수로 코드에서 직접 계산한다
    (LLM 판단에 맡기면 셀 수 있는 값도 흔들려 신뢰도가 떨어지므로).
    """
    cut_count_factor = _judge_cut_count(unit, scenario)
    llm_result = _call_claude(unit, scenario, images_dir, timeout)

    factors = {"cut_count": cut_count_factor}
    for key in _LLM_FACTOR_KEYS:
        factors[key] = llm_result.get(key) or _missing_factor()

    matched = sum(1 for f in factors.values() if f.get("match") is True)
    return {
        "run_id": unit.run_id,
        "video_id": unit.video_id,
        "storyboard_id": unit.storyboard_id,
        "concept_index": unit.concept_index,
        "factors": factors,
        "overall_match_rate": round(matched / len(factors), 3),
        "summary": llm_result.get("summary", ""),
    }


def _judge_cut_count(unit: MatchedUnit, scenario: dict[str, Any]) -> dict[str, Any]:
    expected = unit.expected_cut_count
    actual = len(scenario.get("scenes", []))
    return {
        "match": expected == actual,
        "expected": expected,
        "actual": actual,
        "evidence": "스토리보드 씬의 shots(서브컷) 합계 vs scenario_analysis.scenes 개수",
    }


def _missing_factor() -> dict[str, Any]:
    return {"match": False, "expected": None, "actual": None, "evidence": "LLM 응답에 해당 요인 없음"}


def _call_claude(unit: MatchedUnit, scenario: dict[str, Any], images_dir: Path, timeout: int) -> dict[str, Any]:
    prompt = _build_prompt(unit, scenario, images_dir)
    result = subprocess.run(
        ["claude", "-p", prompt, "--add-dir", str(images_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    return parse_json(result.stdout)


def _build_prompt(unit: MatchedUnit, scenario: dict[str, Any], images_dir: Path) -> str:
    scene_lines = []
    for scene in unit.scenes:
        img_path = images_dir / f"scene{scene.get('no')}.png"
        shot_count = len(scene.get("shots") or []) or 1
        scene_lines.append(
            f"- Scene {scene.get('no')} ({scene.get('time')}): brief={scene.get('brief')} | "
            f"visual={scene.get('visual')} | audio={scene.get('audio')} | overlay={scene.get('overlay')} | "
            f"shots={shot_count}개 | 이미지파일={img_path}"
        )
    storyboard_block = "\n".join(scene_lines)

    return (
        "너는 광고 영상 제작 QA 전문가다. 아래는 광고 영상을 만들 때 쓴 원본 스토리보드(프롬프트·씬별 "
        "묘사·이미지)와, 완성된 영상을 다시 분석해서 만든 scenario_analysis 다. 둘을 비교해 영상이 "
        "원본 기획대로 만들어졌는지 요인별로 판정해라. 이미지 파일은 직접 읽어서 캐릭터 외형·장면 구성을 "
        "확인한다.\n첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[원본 영상 생성 프롬프트]\n{unit.prompt}\n\n"
        f"[원본 스토리보드 — 씬 {len(unit.scenes)}개]\n{storyboard_block}\n\n"
        f"[영상 재분석 결과 scenario_analysis]\n{json.dumps(scenario, ensure_ascii=False)}\n\n"
        "각 요인을 판정해라 (match: 일치 여부, expected: 원본 기준 내용 요약, actual: 재분석 결과 요약, "
        "evidence: 판단 근거):\n"
        "- cut_order: 스토리보드 씬 순서와 scenario_analysis 씬(scenes[].cut_index) 순서가 내용상 대응하는가\n"
        "- character_count: 등장 인물 수\n"
        "- character_appearance: 인물 외형 묘사 일치 여부\n"
        "- scene_description: 장면(배경·구도) 묘사 일치 여부\n"
        "- dialogue: 대사·나레이션(스토리보드 audio 중 VO) 내용 일치 여부\n"
        "- text_overlay: 화면 텍스트(overlay) 일치 여부\n"
        "- scene_duration: 씬별 길이(time) 비율이 유사한가\n"
        "- brand_logo_exposure: 브랜드/로고 노출 유무·타이밍 일치 여부\n\n"
        f"{_SCHEMA}"
    )
