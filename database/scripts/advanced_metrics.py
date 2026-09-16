"""T2VScore-A(Wu et al. 2024)와 VBench-2.0(Zheng et al. 2025) 방법론을 기존 비교 결과에
추가하는 심화 지표. compare_scenario.py 의 9개 factor 판정과 별개로, comparison.json 에
"advanced_metrics" 키로 병합해서 쓴다(run_advanced_metrics.py 참고).

claude -p 호출 방식은 compare_scenario.py 와 동일(스토리보드 이미지 --add-dir, 텍스트는
scenario_analysis JSON) — 새 영상 생성이나 재분석 없이 이미 받아둔 assets/scenario 만
재사용한다.
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

from advanced_metrics_prompts import (  # noqa: E402
    SCHEMA, T2VSCORE_A_INSTRUCTION, VBENCH2_DIMENSION_INSTRUCTIONS,
)
from advanced_metrics_scoring import score_t2vscore_a, score_vbench2  # noqa: E402
from matching import MatchedUnit  # noqa: E402
from prompt_context import format_storyboard_block  # noqa: E402


def compute_advanced_metrics(
    unit: MatchedUnit, scenario: dict[str, Any], images_dir: Path, timeout: int = 600,
) -> dict[str, Any]:
    """스토리보드·scenario_analysis 를 claude -p 로 재평가해 T2VScore-A/VBench-2.0 결과를 반환한다."""
    raw = _call_claude(unit, scenario, images_dir, timeout)
    parse_failed = not raw.get("t2vscore_a") and not raw.get("vbench2")
    t2vscore_a = score_t2vscore_a(raw.get("t2vscore_a", {}).get("elements") or [])
    vbench2 = score_vbench2(raw.get("vbench2") or {})
    return {
        "parse_failed": parse_failed,
        "t2vscore_a": t2vscore_a,
        "vbench2": vbench2,
        "vbench2_summary": _summarize(vbench2),
    }


def _summarize(vbench2: dict[str, dict[str, Any]]) -> dict[str, Any]:
    applicable_scores = [v["score"] for v in vbench2.values() if v["applicable"] and v["score"] is not None]
    return {
        "applicable_dimensions": sum(1 for v in vbench2.values() if v["applicable"]),
        "total_dimensions": len(vbench2),
        "avg_score": round(sum(applicable_scores) / len(applicable_scores), 3) if applicable_scores else None,
    }


def _call_claude(unit: MatchedUnit, scenario: dict[str, Any], images_dir: Path, timeout: int) -> dict[str, Any]:
    prompt = _build_prompt(unit, scenario, images_dir)
    result = subprocess.run(
        ["claude", "-p", prompt, "--add-dir", str(images_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    return parse_json(result.stdout)


def _build_prompt(unit: MatchedUnit, scenario: dict[str, Any], images_dir: Path) -> str:
    storyboard_block = format_storyboard_block(unit, images_dir)
    dimension_lines = "\n".join(f"- {text}" for text in VBENCH2_DIMENSION_INSTRUCTIONS.values())
    return (
        "너는 T2VScore(Wu et al. 2024)와 VBench-2.0(Zheng et al. 2025) 논문의 평가 방법론을 "
        "그대로 적용해 광고 영상 QA 심화 판정을 하는 전문가다. 아래 원본 스토리보드(프롬프트·"
        "씬별 묘사·이미지)와 완성 영상을 재분석한 scenario_analysis 를 비교해라. 이미지 파일은 "
        "직접 읽어서 확인한다.\n\n"
        f"{T2VSCORE_A_INSTRUCTION}\n\n"
        "[VBench-2.0 세부 차원 — 각 차원마다 스토리보드가 해당 능력을 요구하는지 먼저 판단하고"
        "(applicable), 요구하지 않으면 곧바로 applicable=false 로 끝낸다]\n"
        f"{dimension_lines}\n\n"
        f"첫 글자가 반드시 '{{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[원본 영상 생성 프롬프트]\n{unit.prompt}\n\n"
        f"[원본 스토리보드 — 씬 {len(unit.scenes)}개]\n{storyboard_block}\n\n"
        f"[영상 재분석 결과 scenario_analysis]\n{json.dumps(scenario, ensure_ascii=False)}\n\n"
        f"{SCHEMA}"
    )
