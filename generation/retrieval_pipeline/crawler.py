"""M0 부속 — URL 페이지에서 텍스트/대표 이미지를 가져온다(결정적, LLM 아님).

v5_m0_m3/v1_bridge.py 와 같은 기술(httpx+BeautifulSoup)이지만 이 파이프라인 전용으로 독립
구현했다(사용자 요청 — "m0-m2 를 v5_m0_m3 거를 import 하는게 아니라 독립적으로"). curl_cffi
폴백 체인 같은 봇 차단 우회는 두지 않는다 — 이 파이프라인에서 크롤은 가이드라인을 보완하는
2차 소스일 뿐이라, 차단되면 그냥 빈 값으로 두고 LLM이 가이드라인만으로 채우게 한다.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_MAX_TEXT_CHARS = 8000


def _extract_image(soup: BeautifulSoup, base_url: str) -> str:
    """대표 이미지 후보를 우선순위대로 찾는다 — og:image > twitter:image > 첫 <img>."""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return urljoin(base_url, og["content"])
    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        return urljoin(base_url, tw["content"])
    img = soup.find("img")
    if img and img.get("src"):
        return urljoin(base_url, img["src"])
    return ""


def fetch_page(url: str, timeout: int = 15) -> dict[str, Any]:
    """URL 하나를 가져와 {text, image_url, title, error} 를 반환한다. 실패해도 예외를 던지지
    않고 빈 값 + error 문자열로 graceful 처리한다(크롤은 이 파이프라인에서 필수가 아니므로)."""
    if not url:
        return {"text": "", "image_url": "", "title": "", "error": None}
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        return {"text": "", "image_url": "", "title": "", "error": f"{type(e).__name__}: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())[:_MAX_TEXT_CHARS]
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    image_url = _extract_image(soup, url)
    return {"text": text, "image_url": image_url, "title": title, "error": None}
