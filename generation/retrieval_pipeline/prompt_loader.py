"""prompts/*.md 로더 — 코드와 프롬프트 문구를 분리해 "무엇이 모델에 입력되는지"를 파일만
보고 알 수 있게 한다(사용자 요청). generation/v5_m0_m3/md_parser.py 와 같은 `{{변수}}` 치환
방식을 쓰되, 이 파이프라인 전용 prompts/ 디렉터리를 따로 가리킨다(두 파이프라인은 서로
독립적으로 유지 — v5_m0_m3/README.md 의 "서로 참조하지 않는다" 원칙).
"""
from __future__ import annotations

import re
from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_VAR_RE = re.compile(r"\{\{([^}]+)\}\}")
_CACHE: dict[str, str] = {}


def load(name: str) -> str:
    """prompts/<name> 원문을 읽는다(파일당 1회 캐싱). 파일이 없으면 빈 문자열."""
    if name in _CACHE:
        return _CACHE[name]
    path = _PROMPT_DIR / name
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    _CACHE[name] = text
    return text


def fill(template: str, variables: dict[str, str]) -> str:
    """`{{변수명}}` 을 variables 값으로 치환한다. 미매칭 변수는 빈 문자열로 남긴다."""
    def _rep(m: re.Match) -> str:
        key = m.group(1).strip()
        return str(variables.get(key, ""))
    return _VAR_RE.sub(_rep, template)
