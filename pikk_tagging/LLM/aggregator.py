"""도메인별 대표 태그(dominant tag) 계산."""
from __future__ import annotations

from collections import Counter


def compute_dominant_tags(
    frames: list[dict], target_domains: list[str]
) -> dict[str, str]:
    """프레임 목록에서 도메인별 최빈 태그 반환."""
    counters: dict[str, Counter] = {d: Counter() for d in target_domains}

    for frame in frames:
        for domain, tag in frame.get("tags", {}).items():
            if domain in counters:
                counters[domain][tag] += 1

    return {
        domain: counter.most_common(1)[0][0] if counter else ""
        for domain, counter in counters.items()
    }


def compute_tag_distribution(
    frames: list[dict], domain: str
) -> dict[str, int]:
    """단일 도메인의 프레임별 태그 빈도 분포 반환."""
    counter: Counter = Counter()
    for frame in frames:
        tag = frame.get("tags", {}).get(domain)
        if tag:
            counter[tag] += 1
    return dict(counter)
