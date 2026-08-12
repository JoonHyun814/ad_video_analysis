"""retrieval_pipeline M1 — 제품명/URL/가이드 문서/참조 이미지로 제품·브랜드 인사이트를
조사한다(LLM 1회 — 그 앞에 크롤링·웹 검색·이미지 분석을 코드가 결정적으로 수행해 근거를
모아 놓는다). 이 파이프라인의 새 첫 단계다(module0/m1 개편 — "M0~M2는 v5_m0_m3와 동일"
원칙은 그대로 두되, 이 M1은 v5_m0_m3 MODULE 1과 무관한 새 설계다).

  - URL 크롤링: generation.v5_m0_m3.v1_bridge.parse_url() 을 그대로 재사용한다(사용자 승인
    — 봇 차단 대응이 이미 검증된 크롤러). card/material_extractor 등 그 위의 무거운 레이어는
    가져오지 않는다.
  - 제품 스펙·댓글/리뷰 검색: generation/web_searcher.py 는 brand+product 두 인자가 필수라
    (이 단계는 브랜드명이 아직 확정 전) 이 파일에 duckduckgo_search.DDGS 로 독립 구현한다
    (retrieval_pipeline 은 v5_m0_m3 인프라를 그대로 안 쓰는 원칙 — README 참고).
  - 참조 이미지: 이 저장소에서 Claude(claude -p/Anthropic API) 에 이미지를 직접 붙이는 경로가
    검증된 적이 없어, 이미 검증된 utils.openai_caller.call_openai_with_images() (OpenAI
    Vision) 로 이미지→외관 서술 텍스트를 먼저 뽑고 그 텍스트를 다른 소스와 함께 프롬프트에
    얹는다. v5_m0_m3 가 이미 OPENAI_API_KEY 를 요구하므로 새 의존성은 아니다.
  - LLM 호출: 도구가 필요 없지만(코드가 이미 검색을 끝내놓음) tool_chat.run() 을 그대로
    재사용한다 — README 의 선례("M5 는 검색을 쓰지 않지만 같은 호출 인프라를 재사용") 와 같은
    이유.
  - 크롤링 중 발견한 제품 이미지·로고 저장: v1_bridge.parse_url() 이 돌려주는 html(로고 탐색과
    같은 이유로 이미 반환값에 포함돼 있음)에서 og:image + 제품으로 보이는 <img> 후보,
    brandlogourl 을 뽑아 이 실행의 출력 폴더(log_dir, cli_m1.py 가 넘기는 run_dir) 아래
    crawled_images/ 에 내려받는다. 저장 실패는 전부 그레이스풀 — 이미지 하나 못 받았다고
    M1 전체가 죽지 않는다.

근거 우선순위(가이드 문서 → 크롤링/검색 → 추론)는 코드가 아니라 prompts/m1_common.md 의
프롬프트 지시로 처리한다(이 파이프라인의 "코드와 프롬프트 분리" 관례).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from generation.retrieval_pipeline import prompt_loader, tool_chat
from generation.retrieval_pipeline.schemas import ProductInsight
from generation.v5_m0_m3.v1_bridge import parse_url

logger = logging.getLogger(__name__)

_MAX_RESULTS = 5
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_IMAGES = 5

_MAX_PRODUCT_IMAGES = 5
_BAD_IMAGE_MARKERS = ("logo", "icon", "sprite", "btn", "button", "blank", "pixel", "sns", "share", "loading")
_EXT_BY_CONTENT_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
_DOWNLOAD_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_SPEC_QUERIES = [
    "{q} 제품 정보 스펙 특징",
    "{q} 사용법 사용 방법",
    "{q} 소재 재질 성분 함량",
]
_COMMENT_QUERIES = [
    "{q} 후기 리뷰",
    "{q} 평판 브랜드 이미지",
]

_IMAGE_PROMPT = (
    "다음은 한 제품의 참조 이미지들이다. 실제로 눈에 보이는 형태·색상·소재감·크기·마감·"
    "부착물·디테일만 객관적으로 서술하라. 보이지 않는 것을 추측해 지어내지 마라.\n\n"
    '오직 JSON 객체 하나로만 응답하라: {"appearance_notes": "관찰한 외관 서술"}'
)


def _ddg_search(query_templates: list[str], product_name: str) -> str:
    """query_templates 의 {q} 를 product_name 으로 채워 DuckDuckGo 검색, 쿼리별 섹션 텍스트로 합친다."""
    seen: set[str] = set()
    sections: list[str] = []
    with DDGS() as ddgs:
        for template in query_templates:
            query = template.format(q=product_name)
            snippets: list[str] = []
            try:
                for r in ddgs.text(query, max_results=_MAX_RESULTS):
                    body = (r.get("body") or "").strip()
                    if body and body not in seen:
                        seen.add(body)
                        snippets.append(f"  [{r.get('title', '')}]\n  {body}")
            except Exception as e:
                logger.warning(f"[m1 product_insight] DDG 검색 실패 '{query}': {type(e).__name__}: {e}")
            if snippets:
                sections.append(f"## {query}\n" + "\n\n".join(snippets))
    return "\n\n".join(sections)


async def _crawl(url: str) -> dict:
    """v1_bridge.parse_url() 래핑 — 실패해도 그레이스풀(빈 dict, 파이프라인 중단 안 함)."""
    if not (url or "").strip():
        return {}
    try:
        result = await parse_url(url)
    except Exception as e:
        logger.warning(f"[m1 product_insight] 크롤 실패: {type(e).__name__}: {e}")
        return {}
    if result.get("error"):
        logger.warning(f"[m1 product_insight] 크롤 오류: {result['error']}")
        return {}
    return result


def _extract_product_image_urls(html: str, base_url: str) -> list[str]:
    """크롤 html에서 og:image + 제품으로 보이는 <img> 후보 URL을 뽑는다(로고는 v1_bridge.
    parse_url()의 brandlogourl 이 이미 따로 뽑아준다 — 여기서는 그 마커에 걸리는 이미지는
    제외한다)."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    urls: list[str] = []

    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        u = urljoin(base_url, str(og["content"]).strip())
        if u.startswith("http"):
            seen.add(u)
            urls.append(u)

    for img in soup.find_all("img"):
        if len(urls) >= _MAX_PRODUCT_IMAGES:
            break
        raw = str(img.get("data-src") or img.get("data-lazy-src") or img.get("src") or "").strip()
        if not raw:
            continue
        identity = " ".join(str(img.get(k, "")) for k in ("alt", "class", "id", "src")).lower()
        if any(marker in identity for marker in _BAD_IMAGE_MARKERS):
            continue
        u = urljoin(base_url, raw)
        if not u.startswith("http") or u in seen:
            continue
        seen.add(u)
        urls.append(u)
    return urls[:_MAX_PRODUCT_IMAGES]


def _guess_ext(url: str, content_type: str) -> str:
    for k, v in _EXT_BY_CONTENT_TYPE.items():
        if k in (content_type or "").lower():
            return v
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    return suffix if suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif") else ".jpg"


async def _download_image(client: httpx.AsyncClient, url: str, dest_stem: Path) -> str:
    """url을 받아 dest_stem(확장자 없는 경로)에 저장하고 실제 저장 경로를 반환. 실패 시 빈 문자열(그레이스풀)."""
    try:
        resp = await client.get(url, headers=_DOWNLOAD_HEADERS)
        resp.raise_for_status()
        dest = dest_stem.with_suffix(_guess_ext(url, resp.headers.get("content-type", "")))
        dest.write_bytes(resp.content)
        return str(dest)
    except Exception as e:
        logger.warning(f"[m1 product_insight] 이미지 저장 실패 {url}: {type(e).__name__}: {e}")
        return ""


async def _save_crawled_images(crawl: dict, out_dir: str | Path | None) -> list[dict[str, str]]:
    """크롤 결과(html/brandlogourl)에서 찾은 로고·제품 이미지를 out_dir/crawled_images/ 에
    내려받는다. out_dir 이 없거나 크롤이 실패했으면 빈 리스트(그레이스풀 — 저장을 못 해도
    M1 자체는 계속 진행)."""
    if not out_dir or not crawl:
        return []
    html = crawl.get("html") or ""
    page_url = crawl.get("url") or ""
    logo_url = str(crawl.get("brandlogourl") or "").strip()
    product_urls = _extract_product_image_urls(html, page_url) if html else []
    if not logo_url and not product_urls:
        return []

    dest_dir = Path(out_dir) / "crawled_images"
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        if logo_url:
            path = await _download_image(client, logo_url, dest_dir / "logo")
            if path:
                saved.append({"type": "logo", "url": logo_url, "path": path})
        for i, u in enumerate(product_urls, 1):
            path = await _download_image(client, u, dest_dir / f"product_{i}")
            if path:
                saved.append({"type": "product", "url": u, "path": path})
    if saved:
        logger.info(f"[m1 product_insight] 크롤 이미지 저장 {len(saved)}개 → {dest_dir}")
    return saved


def _analyze_images(reference_dir: str | Path | None) -> str:
    """reference_dir 안의 이미지(최대 _MAX_IMAGES 장)를 OpenAI Vision 으로 분석해 외관 서술
    텍스트를 얻는다. 폴더 없음/이미지 없음/호출 실패는 전부 빈 문자열(그레이스풀)."""
    if not reference_dir:
        return ""
    d = Path(reference_dir)
    if not d.is_dir():
        logger.warning(f"[m1 product_insight] reference_dir 없음: {d}")
        return ""
    paths = sorted(p for p in d.iterdir() if p.suffix.lower() in _IMAGE_EXTS)[:_MAX_IMAGES]
    if not paths:
        logger.warning(f"[m1 product_insight] reference_dir 안에 이미지 없음: {d}")
        return ""
    try:
        from utils.openai_caller import call_openai_with_images
        result = call_openai_with_images(_IMAGE_PROMPT, paths, model="gpt-4o")
        return str(result.get("appearance_notes") or "")
    except Exception as e:
        logger.warning(f"[m1 product_insight] 이미지 분석 실패: {type(e).__name__}: {e}")
        return ""


def build_prompt(product_name: str, url: str, guideline_md: str, crawl: dict,
                 product_research: str, comment_research: str, image_notes: str) -> dict[str, str]:
    """실제로 LLM에 보낼 system/user 텍스트를 그대로 반환한다(출력 로그에 그대로 저장됨)."""
    system = prompt_loader.load("m1_common.md") + "\n\n---\n\n" + prompt_loader.load("m1_system.md")
    user_template = prompt_loader.load("m1_user.md")
    user = prompt_loader.fill(user_template, {
        "product_name": product_name,
        "url": url or "(없음)",
        "guideline_md": guideline_md.strip() or "(제공되지 않음)",
        "crawled_title": crawl.get("title", "") or "(없음)",
        "crawled_text": crawl.get("text", "") or "(크롤링 실패 또는 정보 없음)",
        "product_research": product_research or "(검색 결과 없음)",
        "comment_research": comment_research or "(검색 결과 없음)",
        "image_notes": image_notes or "(참조 이미지 없음)",
    })
    return {"system": system, "user": user}


async def run(product_name: str, url: str, *, guideline_md: str = "",
              reference_dir: str | Path | None = None, backend: str = "cli",
              log_prefix: str = "default", log_dir: str | None = None
              ) -> tuple[ProductInsight, dict[str, str], list[dict[str, str]]]:
    """크롤(+발견한 로고·제품 이미지를 log_dir/crawled_images/ 에 저장) → 제품 스펙 검색 →
    댓글/평판 검색 → 참조 이미지 분석(순차) → LLM 종합 순으로 실행하고 (파싱된 결과, 실제
    전송한 프롬프트, 저장된 크롤 이미지 목록) 를 반환한다."""
    crawl = await _crawl(url)
    saved_images = await _save_crawled_images(crawl, log_dir)
    product_research = _ddg_search(_SPEC_QUERIES, product_name)
    comment_research = _ddg_search(_COMMENT_QUERIES, product_name)
    image_notes = _analyze_images(reference_dir)

    prompt = build_prompt(product_name, url, guideline_md, crawl, product_research,
                          comment_research, image_notes)
    raw = tool_chat.run(prompt["system"], prompt["user"], backend=backend,
                        log_prefix=log_prefix, log_dir=log_dir, stage="M1")
    if isinstance(raw, dict) and raw.get("error"):
        raise RuntimeError(f"M1(product_insight) LLM 호출 실패: {raw.get('error')} — {str(raw.get('raw', ''))[:300]}")
    return ProductInsight.model_validate(raw), prompt, saved_images
