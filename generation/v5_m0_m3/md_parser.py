"""v5_m0_m3 프롬프트 로더 — prompts/ 의 common.md·module{1,2,3,4,5,6,7,9}.md 를 로드한다.

원본의 관리 화면용 함수(list_prompts/save_prompt/valid_keys/clear_cache, MODULE_META/GATE_META)
는 이 프로젝트에 설정 UI 가 없어 이식하지 않았다.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

MODULE_WHITELIST = (1, 2, 3, 4, 5, 6, 7, 9)  # M8 은 원본에도 결번(v5-module-roles.md)

_VAR_RE = re.compile(r"\{\{([^}]+)\}\}")
_CACHE: dict[str, str] = {}


def _read(fname: str) -> str:
    if fname in _CACHE:
        return _CACHE[fname]
    p = _PROMPT_DIR / fname
    if not p.exists():
        logger.warning(f"[v5_m0_m3 md_parser] missing prompt file: {p}")
        _CACHE[fname] = ""
        return ""
    txt = p.read_text(encoding="utf-8")
    _CACHE[fname] = txt
    return txt


def get_common() -> str:
    """공통 운영 프롬프트(common.md)."""
    return _read("common.md")


def get_module_prompt(n: int) -> str:
    """MODULE n 지시문(module{n}.md). 없으면 빈 문자열."""
    return _read(f"module{n}.md")


def fill_vars(template: str, variables: dict) -> str:
    """`{{변수}}` 치환. 변수명이 설명형이라 부분일치(키 in 표현 / 표현 in 키)로 매칭. 미매칭은 빈 문자열."""
    def _rep(m: re.Match) -> str:
        expr = m.group(1).strip()
        for k, v in variables.items():
            if k and (k in expr or expr in k):
                return str(v)
        return ""
    return _VAR_RE.sub(_rep, template)
