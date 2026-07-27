"""v5_m0_m3 MODULE 0 — 소재 인제스트 + MODULE 0 표준 스키마 변환.

원본(app/v5/services/module0_ingest.py)에서 두 단계를 제외했다:
  - store.get_run(runid) 로 사용자 입력 제목을 DB 에서 읽어오던 부분 → ingest() 의
    producttitle 인자로 직접 받는다(이 프로젝트는 v5runs 테이블이 없다).
  - ensure_product_references(image_gen) — 제품 이미지가 없을 때 AI 로 참조 이미지를 생성해
    S3 에 올리던 폴백. M9~M12(영상 생성) 전용이라 M0~M3(전략/컨셉 텍스트) 범위 밖이라 제외.
그 외 신뢰등급 태깅·크롤 차단 감지·web_search 폴백 로직은 원본 그대로다.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_EVIDENCE_SIGNALS = (
    "임상", "시험", "인증", "특허", "검증", "데이터", "함량", "테스트",
    "fda", "식약처", "논문", "연구", "%", "퍼센트", "1위", "수상", "ppm",
)


def _trust_of(text: str, source: str) -> str:
    """USP 신뢰등급 판정. 검증 신호 또는 경쟁 web_search 출처면 evidence, 아니면 claim."""
    if source == "competitorweb":
        return "evidence"
    blob = (text or "").lower()
    return "evidence" if any(s in blob for s in _EVIDENCE_SIGNALS) else "claim"


_FAILUREPHRASES = (
    "확인 불가", "확인불가", "미확인", "확인되지 않", "확인 필요",
    "접근 차단", "접속 차단", "접근 불가", "접근 정보 부족", "페이지 접근",
    "보안 확인", "보안 페이지", "robots", "captcha", "access denied",
    "정보 없음", "정보 부족", "수집 불가", "수집할 수 없", "추출할 수 없",
    "노출되지 않", "미노출", "알 수 없", "추가 정보 필요", "이미지 첨부 없음", "데이터 없음",
)


def hasrealtext(text: object) -> bool:
    """실제 데이터 텍스트인지 — 비어있거나 실패 설명 문구를 포함하면 False."""
    if not isinstance(text, str) or not text.strip():
        return False
    blob = text.strip().lower()
    return not any(p in blob for p in _FAILUREPHRASES)


def _insufficient(out: dict) -> bool:
    """크롤 차단/실패 신호 — productname 이 없으면 True (폴백 발동)."""
    return not hasrealtext(out.get("productname"))


def _merge_rescue(out: dict, rescue: dict) -> dict:
    """web_search 복구 결과를 module0 에 병합 (크롤 usp/facts 는 차단 화면 창작 가능성이 있어 전량 폐기)."""
    out["productname"] = rescue.get("productname", "")
    out["brand"] = out.get("brand") or rescue.get("brand", "")
    out["category"] = out.get("category") or rescue.get("category", "")
    out["uspcandidates"] = [
        {"text": t, "source": "websearch", "trust": _trust_of(t, "websearch")}
        for t in rescue.get("usplist", [])
    ]
    srcs = ", ".join(rescue.get("sources", [])[:3])
    out["facts"] = (
        [f"[데이터 출처] URL 크롤이 봇 차단으로 실패하여 웹 검색으로 수집한 정보임 "
         f"(신뢰도 {rescue.get('researchconfidence', 'low')}" + (f", 근거: {srcs}" if srcs else "") + ")"]
        + rescue.get("facts", [])
    )
    if rescue.get("targethints"):
        out["targethints"] = rescue["targethints"]
    out["ingestsource"] = "websearch"
    out["ingestnote"] = "URL 크롤 차단 → 웹 검색으로 제품 정보 수집"
    return out


async def ingest(*, sourceurl: str, producttitle: str = "", label: str = "") -> dict[str, Any]:
    """sourceurl → MODULE 0 표준 JSON. 구간별 graceful — 실패해도 M1 이 받는 필드는 항상 존재(빈 값)."""
    from generation.v5_m0_m3 import (
        brand_research_service,
        material_extractor,
        page_section_ocr,
        usp_extractor,
        v1_bridge,
    )

    # ── 1. URL 크롤 ──
    try:
        crawl = await v1_bridge.parse_url(sourceurl)
    except Exception as e:
        logger.warning(f"[v5_m0_m3 {label}] crawl fail: {type(e).__name__}: {e}")
        crawl = {}
    text = crawl.get("text") or ""
    html = crawl.get("html") or ""

    productanchor = (crawl.get("title") or "").strip()
    if text:
        anchor_prefix = f"[분석 대상 제품]: {productanchor}\n" if productanchor else ""
        fact_guard = (
            "★ facts/keypoints에는 이 페이지에 명시적으로 기재된 사실만 포함하세요 — "
            "추론·일반 상식·타 제품 정보는 제외하세요.\n"
        )
        gpt_texts = [f"{anchor_prefix}{fact_guard}[URL: {sourceurl}]\n{text[:3000]}"]
    else:
        gpt_texts = []

    # ── 2. ProductInfoCard 추출 (경쟁사 web_search 발굴 포함) ──
    card = await material_extractor.extract_via_v1(gpt_texts=gpt_texts, competitorresearch=True)

    # ── 3. 상세페이지 USP (page_section_ocr) — card.usp 앞에 prepend ──
    detail_usps: list[str] = []
    if html:
        try:
            sec = await page_section_ocr.extract(html, sourceurl)
            detail_usps = sec.get("usplist") or []
            if detail_usps:
                rest = [u for u in (card.usp or []) if u not in detail_usps]
                card.usp = (detail_usps + rest)[:20]
        except Exception as e:
            logger.warning(f"[v5_m0_m3 {label}] page_section_ocr skip: {type(e).__name__}: {e}")

    # ── 4. 대표 USP 한 문장 ──
    headline_usp = ""
    try:
        usp_result = await usp_extractor.extract(card)
        headline_usp = usp_result.text or ""
    except Exception as e:
        logger.warning(f"[v5_m0_m3 {label}] usp_extractor skip: {type(e).__name__}: {e}")
        headline_usp = card.adheadline or ""

    out = _to_module0(card, set(detail_usps), headline_usp, sourceurl)
    brandlogourl = str(crawl.get("brandlogourl") or card.brandlogourl or "").strip()
    if brandlogourl:
        out["brandlogourl"] = brandlogourl

    # ── 5. 크롤 차단 폴백 — 제품 데이터가 없으면 web_search 로 복구 ──
    if _insufficient(out):
        logger.warning(f"[v5_m0_m3 {label}] 크롤 데이터 부족(차단 의심) → web_search 폴백 시도")
        try:
            rescue = await brand_research_service.research_product_from_url_with_web(
                sourceurl, producttitle)
        except Exception as e:
            logger.warning(f"[v5_m0_m3 {label}] web_search 폴백 실패: {type(e).__name__}: {e}")
            rescue = {}
        if rescue:
            out = _merge_rescue(out, rescue)
            logger.info(f"[v5_m0_m3 {label}] web_search 복구: product={out['productname']!r} "
                        f"usp={len(out['uspcandidates'])} conf={rescue.get('researchconfidence')}")
        else:
            logger.warning(f"[v5_m0_m3 {label}] web_search 폴백도 제품 미특정 — usable 가드가 run 중단 예정")

    # ── 6. M1 검증용 인제스트 후보 2종 — 기존 소재분석 필드에서 합성(전부 [가설], M1 이 확정) ──
    out["targetcandidate"] = {
        "who": "; ".join(str(x) for x in (out.get("targethints") or [])) or "",
        "aio": {"activities": "", "interests": "", "opinions": "", "lifestyle": ""},
        "note": "제품 정보만으로 추론한 후보 — 전부 [가설] 기본값. 근거(VoC 등) 없으면 공란. M1에서 근거로 승격/기각·확정.",
    }
    _comp = ", ".join(
        c.get("name", "") for c in (out.get("competitorcandidates") or [])
        if isinstance(c, dict) and c.get("name")
    )
    out["marketdefinitioncand"] = (
        f"[카테고리] {out.get('category') or '미정'} + [직접·간접 경쟁대안] {_comp or '미조사'} "
        f"+ [비소비(현상유지) 포함 전체 구매자 풀] — 제품 정보 기반 추론 [가설], M1이 검증·확정"
    )

    logger.info(
        f"[v5_m0_m3 {label}] done: product={out['productname']!r} "
        f"usp={len(out['uspcandidates'])} target={len(out['targethints'])} "
        f"competitor={len(out['competitorcandidates'])}"
    )
    return out


def _to_module0(card, detail_set: set[str], headline_usp: str, sourceurl: str) -> dict[str, Any]:
    """ProductInfoCard + 상세USP set + 대표USP → MODULE 0 표준 JSON (출처·신뢰등급 태깅)."""
    uspcandidates: list[dict] = []
    seen: set[str] = set()
    if headline_usp.strip():
        t = headline_usp.strip()
        uspcandidates.append({"text": t, "source": "headline", "trust": _trust_of(t, "headline")})
        seen.add(t)
    for u in (card.usp or []):
        u = (u or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        src = "detailpage" if u in detail_set else "brandresearch"
        uspcandidates.append({"text": u, "source": src, "trust": _trust_of(u, src)})

    facts: list[str] = []
    claimedfacts: list[str] = []
    for k in (card.keypoints or []):
        if not isinstance(k, str) or not k.strip():
            continue
        (facts if _trust_of(k, "detailpage") == "evidence" else claimedfacts).append(k.strip())
    if card.productfeatures and card.productfeatures.strip():
        item = card.productfeatures.strip()
        (facts if _trust_of(item, "detailpage") == "evidence" else claimedfacts).append(item)
    if isinstance(card.materialspecs, dict):
        for k, v in card.materialspecs.items():
            if v:
                item = f"{k}: {v}"
                (facts if _trust_of(item, "detailpage") == "evidence" else claimedfacts).append(item)

    targethints: list[str] = []
    if card.targetaudience and card.targetaudience.strip():
        targethints.append(card.targetaudience.strip())
    for p in (card.personas or [])[:3]:
        if not isinstance(p, dict):
            continue
        parts = [p.get("label") or "", p.get("agerange") or "", p.get("coredesire") or ""]
        hint = " / ".join(x for x in parts if x)
        if hint:
            targethints.append(hint)
    if card.heropersonabrief:
        targethints.append(str(card.heropersonabrief))

    competitorcandidates: list[dict] = []
    for c in (card.competitors or []):
        if isinstance(c, dict) and c.get("name"):
            competitorcandidates.append({
                "name": c.get("name"), "positioning": c.get("positioning") or "",
                "ourdifference": c.get("ourdifference") or "", "trust": "evidence",
            })
    if not competitorcandidates and card.competitiveposition:
        competitorcandidates.append({
            "name": "(추정)", "positioning": card.competitiveposition,
            "ourdifference": "", "trust": "claim",
        })

    return {
        "productname": card.productname or "",
        "brand": card.brand or "",
        "category": card.categorypath or card.industry or card.category2name or "",
        "producttype": card.producttype.value if card.producttype else "",
        "uspcandidates": uspcandidates,
        "facts": facts,
        "claimedfacts": claimedfacts,
        "targethints": targethints,
        "competitorcandidates": competitorcandidates,
        "tone": card.tone or "",
        "visualmotifs": [m for m in (card.visualmotifs or []) if isinstance(m, str)],
        "brandlogourl": str(card.brandlogourl or "").strip(),
        "sourceurl": sourceurl,
    }
