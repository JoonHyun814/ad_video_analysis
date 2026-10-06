from pathlib import Path

import easyocr

_reader: easyocr.Reader | None = None
_CONFIDENCE_THRESHOLD = 0.3


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["ko", "en"], verbose=False)
    return _reader


def run_ocr(image_path: Path) -> list[str]:
    """이미지에서 신뢰도 0.3 이상의 텍스트만 추출해 리스트로 반환한다."""
    results = _get_reader().readtext(str(image_path))
    return [text for _, text, conf in results if conf >= _CONFIDENCE_THRESHOLD]


def run_ocr_batch(image_paths: list[Path]) -> dict[str, list[str]]:
    """여러 이미지에 OCR을 수행하고 {파일명: 텍스트 리스트}를 반환한다."""
    return {p.name: run_ocr(p) for p in image_paths}


def release() -> None:
    """EasyOCR 모델을 메모리에서 해제한다."""
    global _reader
    _reader = None
