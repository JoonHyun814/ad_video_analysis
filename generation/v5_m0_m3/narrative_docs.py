"""narrative_docs.py 발췌 — usp_extractor 가 쓰는 narrative_picker 자료 로더만 이식.

원본은 scene_planner/keyvisual_selector 자료도 로드했지만 M0~M3 경로엔 usp_extractor 만
있어 core + narrativestructures 두 문서만 이식했다(reference_doc/narrative/ 아래 복사).
원본의 basicvalue 토글은 이미 상수 True 로 고정돼 있었다(주석 참고) — 그대로 상수화.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DOC_DIR = Path(__file__).resolve().parent / "reference_doc" / "narrative"

_DOC_FILES: dict[str, str] = {
    "core": "00_core.md",
    "narrativestructures": "01_narrative_structures.md",
}

_HEADING: dict[str, str] = {
    "narrativestructures": "# 서사구조 6종 가이드",
}

_CACHE: dict[str, str | None] = {}


def load(key: str) -> str | None:
    """단일 자료 로드. 파일 없음 → None."""
    if key in _CACHE:
        return _CACHE[key]
    fname = _DOC_FILES.get(key)
    if not fname:
        return None
    p = _DOC_DIR / fname
    if not p.exists():
        logger.warning(f"narrative doc missing: {p}")
        _CACHE[key] = None
        return None
    try:
        body = p.read_text(encoding="utf-8")
        _CACHE[key] = body
        return body
    except Exception as e:
        logger.warning(f"narrative doc read failed ({fname}): {e}")
        _CACHE[key] = None
        return None


def load_for_module(module: str) -> str:
    """core + narrativestructures 합쳐서 반환. module 인자는 원본 호환용(usp_extractor 는 "narrative_picker" 고정)."""
    parts: list[str] = []
    core = load("core")
    if core:
        parts.append("# 광고 영상 제작 핵심 (총론)\n\n" + core.strip())
    doc = load("narrativestructures")
    if doc:
        parts.append(f"{_HEADING['narrativestructures']}\n\n{doc.strip()}")
    return "\n\n---\n\n".join(parts)
