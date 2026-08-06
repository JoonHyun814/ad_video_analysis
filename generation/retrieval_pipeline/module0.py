"""M0 — 브랜드 가이드라인을 1차 소스로 제품 정보를 확보하고, 가이드라인에 없는 정보만 크롤링
으로 보완한다(LLM 1회). v5_m0_m3/module0_ingest.py 와 달리 크롤이 아니라 **가이드라인이 1차
소스**다(사용자 요청 — "가이드라인 참조하여 usp, target, 제품명, 제품카테고리, 제품 이미지 등
확보 - 가이드라인에서 확인할 수 없는 정보들은 크롤링하여 보완").

`product_image_url` 은 LLM에게 맡기지 않는다 — crawler.fetch_page() 가 og:image 등에서 찾아온
값을 코드가 그대로 쓴다(URL을 텍스트에서 추측하게 하면 존재하지 않는 이미지 경로를 지어낼 수
있다 — 결정적으로 구할 수 있는 값은 코드가 담당한다는 이 파이프라인의 원칙).
"""
from __future__ import annotations

from typing import Any

from generation.retrieval_pipeline import crawler, prompt_loader
from generation.retrieval_pipeline.module_schemas import Module0LLM
from generation.v5_m0_m3 import llm_adapter

_STAGE = "M0"


def build_prompt(guideline_text: str, crawl: dict[str, Any]) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("m0_system.md")
    user_template = prompt_loader.load("m0_user.md")
    user = prompt_loader.fill(user_template, {
        "guideline_text": guideline_text,
        "crawl_title": crawl.get("title", ""),
        "crawl_text": crawl.get("text", ""),
    })
    return {"system": system, "user": user}


def run_module0(guideline_text: str, url: str = "") -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    """가이드라인(+선택적으로 크롤)을 근거로 M0 를 완성한다.

    반환: (module0 dict — LLM 필드 + product_image_url/source_url/guideline_text 코드 보강,
    실제 전송한 프롬프트, 크롤 원본 결과)
    """
    crawl = crawler.fetch_page(url) if url else {"text": "", "image_url": "", "title": "", "error": None}
    prompt = build_prompt(guideline_text, crawl)
    raw = llm_adapter.chat_json(prompt["system"], prompt["user"], stage=_STAGE)
    if isinstance(raw, dict) and raw.get("error"):
        raise RuntimeError(f"M0 LLM 호출 실패: {raw.get('error')} - {str(raw.get('raw', ''))[:300]}")
    llm_output = Module0LLM.model_validate(raw)

    module0 = {
        **llm_output.model_dump(),
        "product_image_url": crawl.get("image_url", ""),
        "source_url": url,
        "guideline_text": guideline_text,
        "crawl_error": crawl.get("error"),
    }
    return module0, prompt, crawl
