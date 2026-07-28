"""v5_m0_m3 v1_bridge — MODULE 0 이 쓰는 URL 크롤 + 소재 분석 LLM 호출.

원본(app/v5/services/v1_bridge.py)에서 M0 경로가 실제로 쓰는 부분만 이식:
  - URL 크롤 체인(curl_cffi → curl → httpx). MCP 브라우저 크롤러(MCP_CRAWLER_URL)와
    Windows 로컬 경로에 하드코딩된 got-scraping 스크립트는 이 프로젝트에 없는 인프라라 제외 —
    남은 curl_cffi/curl/httpx 체인만으로도 원본의 최종 폴백과 동일하게 동작한다.
  - _gpt_analyze → analyze_material: llm_adapter.chat_json(claude -p) 호출로 교체.
  - get_analysis_prompt: DB(prompt_manager)의 커스텀 프롬프트 오버라이드 기능은 제외하고
    원본에 이미 있던 하드코딩 폴백 프롬프트(_FALLBACK_ANALYSIS_PROMPT) + category_lookup 의
    카테고리 목록을 그대로 사용한다.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

from generation.v5_m0_m3 import category_lookup, llm_adapter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 소재 분석 LLM 호출 (원본 _gpt_analyze)
# ═══════════════════════════════════════════════

async def analyze_material(system: str, user_content) -> dict:
    """소재 분석 JSON 호출. user_content 는 str 또는 [{"type":"text","text":...}, ...] 형태.

    claude -p 는 이미지 첨부를 받지 않으므로 텍스트 블록만 이어붙인다 — M0 인제스트 경로는
    항상 텍스트만 전달한다(비전 첨부이미지 분석은 이 프로젝트 범위 밖, page_section_ocr 참고).
    """
    if isinstance(user_content, str):
        user_text = user_content
    else:
        user_text = "\n".join(
            str(block.get("text", "")) for block in user_content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return await asyncio.to_thread(llm_adapter.chat_json, system, user_text, stage="M0:material_analysis")


# 하드코딩 fallback — 원본 DB `material_analysis_system` 프롬프트의 기본값(원본 그대로).
_FALLBACK_ANALYSIS_PROMPT = """당신은 제품/서비스 분석 전문가입니다.
주어진 소재(텍스트, 이미지)를 분석하여 광고 영상 제작에 필요한 정보를 추출합니다.

반드시 JSON으로 응답 (필드명 주의 - 언더바 없이 소문자 연결):
{
  "productname": "제품/서비스 이름",
  "brand": "브랜드명",
  "category3id": "아래 목록에서 가장 적합한 ID 하나 선택",
  "adheadline": "광고 핵심 문구 (1줄)",
  "functionalstrengths": ["기능적 강점 3개"],
  "productfeatures": "제품 특징 상세 설명",
  "targetaudience": "추천 타겟층",
  "tone": "추천 톤앤매너코드",
  "keypoints": ["핵심 포인트 3-5개"],
  "style": "추천 비주얼 스타일코드",
  "productimageidx": [],
  "brandlogoidx": null,
  "confidence": 0.0
}
"""


def get_analysis_prompt() -> str:
    """소재 분석 system prompt + 카테고리 목록(category_lookup, 읽기 전용 RDS 조회)."""
    cat_text = category_lookup.build_category_prompt()
    return _FALLBACK_ANALYSIS_PROMPT + "\n## 카테고리 목록 (이 중에서만 선택)\n" + cat_text


# ═══════════════════════════════════════════════
# URL 크롤 (curl_cffi → curl → httpx — MCP/got-scraping 제외)
# ═══════════════════════════════════════════════

def _is_valid_html(html: str) -> bool:
    """크롤링 결과가 유효한 상품 페이지인지 확인."""
    if not html or len(html) < 3000:
        return False
    if len(html) > 50000:
        return True
    bad = ["Access Denied", "에러페이지", "시스템오류", "bot_check",
           "challenge-page", "Application error", "security verification"]
    return not any(b in html for b in bad)


def _to_mobile_url(url: str) -> str:
    """PC URL → 모바일 URL 변환 (네이버 스마트스토어 차단 회피용)."""
    if "smartstore.naver.com" in url:
        return url.replace("smartstore.naver.com", "m.smartstore.naver.com")
    if "://www." in url:
        return url.replace("://www.", "://m.")
    return url


async def _fetch_via_curl(url: str) -> str:
    """curl로 HTML fetch (iPhone UA, TLS 네이티브)."""
    import subprocess

    def _sync():
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", "--max-time", "15",
                 "-H", "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                 url],
                capture_output=True, text=True, timeout=20,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and _is_valid_html(result.stdout):
                return result.stdout
        except Exception as e:
            logger.warning(f"curl failed: {url[:60]} {e}")
        return ""
    html = await asyncio.to_thread(_sync)
    if html:
        logger.info(f"curl OK: {url[:60]} ({len(html)}자)")
    return html


async def _fetch_via_curl_cffi(url: str) -> str:
    """curl_cffi로 HTML fetch (Chrome TLS fingerprint 위조)."""
    def _sync():
        try:
            from curl_cffi import requests as cffi_requests
            r = cffi_requests.get(url, impersonate="chrome124", timeout=30,
                headers={"Accept": "text/html", "Accept-Language": "ko-KR,ko;q=0.9"})
            if r.status_code == 200 and _is_valid_html(r.text):
                return r.text
        except Exception as e:
            logger.warning(f"curl_cffi failed: {url[:60]} {e}")
        return ""
    html = await asyncio.to_thread(_sync)
    if html:
        logger.info(f"curl_cffi OK: {url[:60]} ({len(html)}자)")
    return html


async def _fetch_html(url: str) -> str:
    """사이트별 최적 순서로 크롤 시도: curl_cffi → curl(모바일, 네이버) → httpx."""
    is_naver = "smartstore.naver.com" in url or "shopping.naver.com" in url

    if is_naver:
        mobile = _to_mobile_url(url)
        html = await _fetch_via_curl(mobile)
        if html:
            return html

    html = await _fetch_via_curl_cffi(url)
    if html:
        return html

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if _is_valid_html(resp.text):
                return resp.text
    except Exception as e:
        logger.warning(f"httpx fallback failed: {url[:60]} {e}")

    logger.error(f"All crawl methods failed: {url[:60]}")
    return ""


async def parse_url(url: str) -> dict:
    """URL → 텍스트 + 브랜드 로고 + 원본 html(page_section_ocr 재사용용)."""
    try:
        html = await _fetch_html(url)
        if not html:
            return {"type": "url", "url": url, "error": "크롤링 실패",
                    "title": "", "text": "", "html": ""}

        soup = BeautifulSoup(html, "html.parser")

        title = ""
        if soup.title:
            title = soup.title.string or ""
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", title)

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)[:5000]

        from urllib.parse import urljoin
        logo_candidates: list[tuple[int, str]] = []
        for img_tag in soup.find_all("img"):
            raw_url = str(img_tag.get("data-src", "") or img_tag.get("data-lazy-src", "") or img_tag.get("src", "") or "")
            identity = " ".join(
                str(img_tag.get(key, "")) for key in ("alt", "class", "id", "src", "data-src", "data-lazy-src")
            ).lower()
            if raw_url and any(marker in identity for marker in ("logo", "brandmark", "wordmark")):
                logo_candidates.append((1, urljoin(url, raw_url.strip())))
        for link_tag in soup.find_all("link", href=True):
            rel = " ".join(str(item) for item in (link_tag.get("rel") or [])).lower()
            if "icon" in rel:
                priority = 2 if "apple" in rel else 3
                logo_candidates.append((priority, urljoin(url, str(link_tag.get("href") or ""))))
        logo_candidates.sort(key=lambda item: item[0])
        brandlogourl = logo_candidates[0][1] if logo_candidates else ""

        return {
            "type": "url", "url": url, "title": title, "text": text,
            "brandlogourl": brandlogourl,
            "html": html,  # page_section_ocr 재사용용 — 호출자가 persist 전 pop
        }
    except Exception as e:
        logger.error(f"URL parse failed ({url}): {e}")
        return {"type": "url", "url": url, "error": str(e), "title": "", "text": "", "html": ""}
