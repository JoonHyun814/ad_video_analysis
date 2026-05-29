"""DuckDuckGo 검색으로 브랜드/제품 정보를 수집한다."""
from duckduckgo_search import DDGS

_MAX_RESULTS = 5

_TOPIC_QUERIES: list[tuple[str, list[str]]] = [
    ("성분", [
        "{brand} {product} 원재료 성분",
        "{brand} {product} 재료 함량",
    ]),
    ("기능·효능", [
        "{brand} {product} 효능 효과 특징",
        "{brand} {product} 장점 차별점",
    ]),
    ("슬로건·캠페인", [
        "{brand} 슬로건 tagline 광고문구",
        "{brand} {product} 캠페인 카피",
    ]),
    ("타겟·포지셔닝", [
        "{brand} {product} 타겟 소비자 마케팅 전략",
        "{brand} 브랜드 포지셔닝 이미지",
    ]),
]


def search_brand_product(brand: str, product: str) -> str:
    """브랜드·제품 관련 웹 검색 결과를 주제별로 수집해 반환한다."""
    seen: set[str] = set()
    sections: list[str] = []

    with DDGS() as ddgs:
        for topic, queries in _TOPIC_QUERIES:
            snippets: list[str] = []
            for q in queries:
                for r in ddgs.text(q.format(brand=brand, product=product), max_results=_MAX_RESULTS):
                    body = r.get("body", "").strip()
                    if body and body not in seen:
                        seen.add(body)
                        snippets.append(f"  [{r.get('title', '')}]\n  {body}")
            if snippets:
                sections.append(f"## {topic}\n" + "\n\n".join(snippets))

    return "\n\n".join(sections)
