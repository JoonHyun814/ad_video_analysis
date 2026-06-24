"""파이프라인 입력 JSON 의 존재·유효성 검증 헬퍼.

각 파이프라인 단계는 이전 단계의 산출 JSON 을 입력으로 받는다.
파일이 없거나, JSON 파싱이 깨졌거나, `parse_failed` 항목이 섞여 있으면
하류 단계가 조용히 깨진 데이터를 소비하므로, CLI 진입점에서 미리 막는다.
"""
import json
from pathlib import Path
from typing import Any


def is_parse_failed(data: Any) -> bool:
    """dict 단건 또는 list 안의 항목 중 하나라도 `error == "parse_failed"` 이면 True."""
    if isinstance(data, dict):
        return data.get("error") == "parse_failed"
    if isinstance(data, list):
        return any(
            isinstance(item, dict) and item.get("error") == "parse_failed"
            for item in data
        )
    return False


def require_exists(path: Path, label: str) -> None:
    """파일이 없으면 SystemExit 으로 중단한다."""
    if not path.exists():
        raise SystemExit(f"[오류] {label} 없음: {path}")


def require_valid_json(path: Path, label: str) -> Any:
    """존재 + JSON 파싱 + parse_failed 미포함 을 모두 검증한 뒤 데이터 반환.

    하류 단계는 이 함수의 반환값을 그대로 사용한다. 한 번만 읽으면 되도록 파싱 결과를 돌려준다.
    """
    require_exists(path, label)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SystemExit(f"[오류] {label} JSON 파싱 실패: {path}\n  {e}")
    if is_parse_failed(data):
        raise SystemExit(
            f"[오류] {label} 에 parse_failed 항목 있음: {path}\n"
            f"  해당 단계를 재실행해 정상 결과를 만든 뒤 다시 시도하세요."
        )
    return data


def load_optional_valid(path: Path, label: str, default: Any) -> Any:
    """선택 입력 — 없으면 default, 있으면 유효성 검증 후 반환.

    optional 이지만 일단 존재하면 parse_failed 인 채로 통과시키지 않는다.
    """
    if not path.exists():
        return default
    return require_valid_json(path, label)
