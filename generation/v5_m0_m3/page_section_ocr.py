"""v5_m0_m3 page_section_ocr — 이미지형 상세페이지 구성요소(14섹션)를 비전으로 읽어
USP 후보 + 출처(섹션·이미지)를 추출한다.

원본은 basicvalue DB 토글로 SECTION_OCR_ENABLED/MAX_IMAGES/BATCH/MAX_PER_SECTION 을 읽었지만,
원본 주석대로 DB 스냅샷이 이미 아래 기본값과 동일해 상수로 고정되어 있었다 — 그 상수를 그대로 이식.
비전 호출은 llm_adapter.vision_json(OpenAI Vision, call_claude 는 이미지 미지원)으로 교체.

흐름: collect_detail_images → ocr_classify_sections → consolidate → uspsections
"""
from __future__ import annotations

import asyncio
import io
import logging
import re

from generation.v5_m0_m3 import llm_adapter, usp_score_rules
from generation.v5_m0_m3.schemas import UspSourceItem

logger = logging.getLogger(__name__)

SECTIONS: dict[int, str] = {
    0: "기타", 1: "후킹/키비주얼", 2: "문제제기/공감", 3: "솔루션", 4: "특장점/효능",
    5: "핵심성분/기술", 6: "임상/인체적용", 7: "사용 전후", 8: "사용법", 9: "후기/리뷰",
    10: "인증/수상", 11: "제품정보", 12: "FAQ", 13: "배송/교환", 14: "CTA",
}

_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")

_EXCLUDE = (
    "/banner/", "icon", "logo", "btn", "button", "arrow", "cart", "close",
    "search", "menu", "spinner", "loading", "pixel", "tracker", "spacer",
    "blank", "1x1", "sprite", "emoji", "rating", "flag", "payment", "visa",
    "master", "paypal", "social", "facebook", "instagram", "twitter",
    "youtube", "kakao_", "naver_logo", "/google", "apple", "android",
    "shipping", "inquiry", "/images/product/",
    "/templet/", "/template/", "/skin/", "/layout/", "/gnb", "/footer",
    "banner", "chatbot", "_noti", "morning_noti", "/event/", "welcome", "coupon",
)

SECTION_SYS = """쇼핑몰 상세페이지 이미지에서 광고에 쓸 USP(핵심 셀링포인트)를 뽑는 분석가입니다. 각 이미지마다:
- 섹션 분류(상세페이지 구성요소 번호): 1 후킹/메인키비주얼, 2 문제제기/공감, 3 솔루션제시, 4 핵심특장점/효능, 5 핵심성분/기술설명, 6 인체적용시험/임상결과, 7 사용 전후(Before-After), 8 사용법, 9 후기/리뷰/인플루언서, 10 인증/수상/미디어, 11 제품 상세정보(용량·전성분·제형), 12 FAQ, 13 배송/교환/반품, 14 CTA/구매유도. 어디에도 안 맞으면 0 기타.
- 그 이미지의 USP(셀링포인트)를 **1~3개만** 뽑아라. 이미지의 모든 문구를 그대로 나열하지 마라(원문 덤프 금지).
- 11~14(제품정보·FAQ·배송·CTA)와 0 기타는 보통 셀링포인트가 아니다 → 광고에 쓸 USP가 없으면 items 를 빈 배열로 둬라(억지로 만들지 마라).
- 서로 다른 셀링포인트는 분리(예: "01 트러블 진정 / 02 피지·유분·모공 개선 / 03 흔적 개선" = 3개).
- 같은 셀링포인트의 반복 수치·성분 나열은 반드시 **하나의 USP로 통합**하라.
- headline 은 광고 카피로 바로 쓸 짧은 USP 한 문장.
- 이미지에 실제 있는 내용에만 근거(없는 효능·수치 지어내기 금지). 임상/법적 작은 글씨는 footnote 로 분리.
아래 이미지들은 0-based 인덱스로 순서대로 첨부되어 있다. JSON 으로만 응답(sectionname 은 위 분류명 그대로):
{"images":[{"index":0,"section":4,"sectionname":"핵심특장점/효능","items":[{"headline":"USP 셀링포인트 한 문장","footnote":"임상/각주 근거 또는 빈값"}]}]}"""

_MAX_IMAGES = 30
_BATCH = 3
_MAX_PER_SECTION = 8


def collect_detail_images(html: str, base_url: str) -> list[str]:
    """상세 영역 콘텐츠 이미지 URL 을 DOM 등장 순서로 수집. 배너·UI·썸네일 제외, gif 포함."""
    if not html:
        return []
    from urllib.parse import urlparse

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    pu = urlparse(base_url or "")
    origin = f"{pu.scheme or 'https'}://{pu.netloc}" if pu.netloc else ""

    out: list[str] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        src = ""
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            v = img.get(attr) or ""
            if v:
                src = v
                break
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = origin + src
        if not src.startswith("http"):
            continue
        low = src.lower()
        if not low.split("?")[0].endswith(_IMG_EXT):
            continue
        if any(kw in low for kw in _EXCLUDE):
            continue
        if src in seen:
            continue
        seen.add(src)
        out.append(src)

    if len(out) > _MAX_IMAGES:
        logger.info(f"[page_section_ocr] detail images {len(out)} > cap {_MAX_IMAGES}, truncating")
        out = out[:_MAX_IMAGES]
    return out


def _gif_to_static(data: bytes) -> tuple[bytes, str]:
    """애니메이션 GIF → 마지막 프레임 PNG."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        n = getattr(im, "n_frames", 1)
        if n <= 1:
            return data, "gif"
        im.seek(n - 1)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        return buf.getvalue(), "png"
    except Exception as e:
        logger.warning(f"[page_section_ocr] gif flatten fail: {type(e).__name__}")
        return data, "gif"


async def ocr_classify_sections(image_urls: list[str], *, batch: int | None = None) -> list[dict]:
    """이미지 URL 들을 다운로드 → 비전 분류. 실패분(다운로드/배치)은 graceful skip."""
    if not image_urls:
        return []
    import httpx

    bsize = batch or _BATCH
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as cli:
        for b in range(0, len(image_urls), bsize):
            chunk = image_urls[b:b + bsize]
            images: list[tuple[bytes, str]] = []
            local: list[str] = []
            for u in chunk:
                try:
                    r = await cli.get(u, headers={"User-Agent": "Mozilla/5.0"})
                    if r.status_code == 200 and len(r.content) > 500:
                        raw = r.content
                        ext = "jpg"
                        if "gif" in (r.headers.get("content-type") or "") or u.lower().split("?")[0].endswith(".gif"):
                            raw, ext = _gif_to_static(raw)
                        images.append((raw, ext))
                        local.append(u)
                except Exception as e:
                    logger.warning(f"[page_section_ocr] image dl fail {u[:60]}: {type(e).__name__}")
            if not local:
                continue
            try:
                res = await asyncio.to_thread(llm_adapter.vision_json, SECTION_SYS, images)
                for im in (res.get("images") or []):
                    idx = im.get("index")
                    url = local[idx] if isinstance(idx, int) and 0 <= idx < len(local) else None
                    sec = im.get("section")
                    sec = sec if isinstance(sec, int) and sec in SECTIONS else 0
                    results.append({
                        "imageurl": url or "", "section": sec,
                        "sectionname": im.get("sectionname") or SECTIONS.get(sec, ""),
                        "items": im.get("items") or [],
                    })
            except Exception as e:
                logger.warning(f"[page_section_ocr] vision batch {b // bsize} fail: {type(e).__name__}: {e}")
    return results


def _norm(s: str) -> str:
    return re.sub(r"[\s\W]+", "", (s or "")).lower()


def _score_other(headline: str) -> float:
    """섹션 미매칭(기타) USP 랭킹 점수 — usp_score_rules 2축(clarity+credibility) 재사용."""
    try:
        blob = (headline or "") + " " + (headline or "").lower()
        if any(k in blob for k in usp_score_rules._OBJECTIVE_PROOF):
            cred = 1.0
        elif any(k in headline for k in usp_score_rules._TESTIMONY) or any(k in headline for k in usp_score_rules._AUTHORITY):
            cred = 0.6
        else:
            cred = 0.2
        return round((usp_score_rules._clarity(headline) + cred) / 2, 3)
    except Exception:
        return 0.0


def consolidate(results: list[dict]) -> list[UspSourceItem]:
    """이미지별 분류 결과 → UspSourceItem 리스트. headline 정규화 dedup, 섹션 순 + 기타 점수 랭킹."""
    items: list[UspSourceItem] = []
    seen: set[str] = set()
    for r in results or []:
        sec = r.get("section") or 0
        url = r.get("imageurl") or ""
        for it in (r.get("items") or []):
            hl = (it.get("headline") or "").strip()
            if not hl:
                continue
            key = _norm(hl)
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(UspSourceItem(
                section=sec if sec in SECTIONS else 0,
                sectionname=SECTIONS.get(sec, "기타"),
                number=str(it.get("number") or "").strip(),
                headline=hl,
                footnote=(it.get("footnote") or "").strip(),
                sourceimageurl=url,
                score=_score_other(hl) if (sec or 0) == 0 else 0.0,
            ))
    enumerated = list(enumerate(items))
    ranked = [x for x in enumerated if x[1].section != 0]
    others = [x for x in enumerated if x[1].section == 0]
    ranked.sort(key=lambda x: (x[1].section, x[0]))
    others.sort(key=lambda x: -x[1].score)
    ordered = [it for _, it in ranked] + [it for _, it in others]

    capped: list[UspSourceItem] = []
    cnt: dict[int, int] = {}
    for it in ordered:
        n = cnt.get(it.section, 0)
        if n >= _MAX_PER_SECTION:
            continue
        cnt[it.section] = n + 1
        capped.append(it)
    return capped


async def extract(html: str, base_url: str) -> dict:
    """상세페이지 html → uspsections + usplist. 전구간 graceful (실패 시 빈 결과)."""
    try:
        urls = collect_detail_images(html, base_url)
        if not urls:
            logger.info("[page_section_ocr] 상세 이미지 0장 (정적 미수집/JS렌더 가능)")
            return {"uspsections": [], "usplist": []}
        results = await ocr_classify_sections(urls)
        sections = consolidate(results)
        logger.info(f"[page_section_ocr] imgs={len(urls)} -> uspsections={len(sections)}")
        return {
            "uspsections": [s.model_dump() for s in sections],
            "usplist": [s.headline for s in sections if s.headline],
        }
    except Exception as e:
        logger.warning(f"[page_section_ocr] extract fail: {type(e).__name__}: {e}")
        return {"uspsections": [], "usplist": []}
