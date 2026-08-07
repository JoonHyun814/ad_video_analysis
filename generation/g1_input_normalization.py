"""G1 — 광고주 입력(장르·타겟·USP 자유 텍스트)을 세그먼트 검색용 enum + facet 텍스트로 정규화한다.

광고주가 준 값은 그대로 존중하고(교체 금지), 비어있는 항목만 브리프에서 추론해 채운다.
출력의 genre/industry_category 는 벡터 DB 메타데이터와 같은 enum 사전을 쓴다.
"""
import json

from db.chromadb.importers.facets import GENRE_CHOICES
from utils.llm_dispatch import call_llm

_INDUSTRY = ("beauty|food_beverage|retail_ecommerce|finance|healthcare|fashion|tech_electronics"
             "|automotive|entertainment|travel|education|gaming|other")
_GENRE = "|".join(GENRE_CHOICES)
_POSITION = "leader|challenger|new_entrant"

_SCHEMA = (
    f'{{"genre": "{_GENRE}",'
    ' "genre_reason": "장르 판정 근거 한 문장",'
    f' "industry_category": "{_INDUSTRY}",'
    ' "product_category": "제품 카테고리 명칭 (한국어)",'
    ' "target_persona": "타겟 소비자 서술 (연령대·성별·라이프스타일·구매 동기, 2~3문장)",'
    ' "usp": "차별화 포인트 서술 (1~2문장)",'
    ' "positioning": "브랜드/제품 포지셔닝 (1문장)",'
    f' "brand_position": "{_POSITION}",'
    ' "brand_position_reason": "시장 지위 판정 근거 한 문장"}'
)


def _advertiser_block(advertiser: dict) -> str:
    given = {k: v for k, v in advertiser.items() if v}
    if not given:
        return ""
    return (
        "\n[광고주 지정값 — 의미를 바꾸지 말고 정규화만 해라. enum 필드는 가장 가까운 enum 값으로 매핑]\n"
        + json.dumps(given, ensure_ascii=False, indent=2) + "\n"
    )


def build_prompt(brief: dict, advertiser: dict) -> str:
    """브리프 + 광고주 지정값에서 G1 정규화 프롬프트를 만든다."""
    return (
        "너는 광고 전략 플래너다. 아래 브리프와 광고주 지정값을 세그먼트 검색용 표준 스키마로 정규화해라.\n\n"
        "규칙:\n"
        "1. 광고주 지정값이 있는 필드는 그 의미를 유지한 채 표준 표현으로만 다듬는다 (내용 교체 금지).\n"
        "2. 지정값이 없는 필드는 브리프에서 추론해 채운다.\n"
        "3. genre 는 광고의 소구 장르다 — humor(유머·패러디), emotional(감성·향수), "
        "informational(정보·비교·증언), aspirational(동경·과시), urgency(공포·긴급) 중 판단.\n"
        "4. brand_position 은 이 브랜드의 시장 지위다 — leader(선도), challenger(도전), new_entrant(신규 진입).\n"
        "5. target_persona / usp / positioning 은 벡터 검색 쿼리로 쓰이므로 구체적 명사·형용사로 서술한다.\n\n"
        f"[브리프]\n{json.dumps(brief, ensure_ascii=False, indent=2)}\n"
        f"{_advertiser_block(advertiser)}\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    advertiser: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """광고주 입력을 정규화한 G1 결과를 반환한다."""
    return call_llm(build_prompt(brief, advertiser),
                    backend=backend, gemini_model=gemini_model, codex_model=codex_model)
