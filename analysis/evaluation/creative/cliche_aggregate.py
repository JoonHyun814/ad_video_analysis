"""세그먼트 내 크리에이티브 요소 빈도를 집계해 클리셰/파괴 요소를 판정한다.

판정 기준 (creative_element_schema.md):
  빈도 ≥ 60% → strong_cliche / 30~60% → convention / 영상 1편 고립 → cliche_breaker / 그 외 minor
캐스팅 속성은 profile 메타데이터에서 별도 집계한다.
"""
from collections import defaultdict

STRONG_THRESHOLD = 0.6
CONVENTION_THRESHOLD = 0.3

_JUDGE_ORDER = ("strong_cliche", "convention", "minor", "cliche_breaker")


def _judge(n_videos: int, count: int) -> str:
    ratio = count / n_videos if n_videos else 0.0
    if count == 1 and n_videos >= 3:
        return "cliche_breaker"
    if ratio >= STRONG_THRESHOLD:
        return "strong_cliche"
    if ratio >= CONVENTION_THRESHOLD:
        return "convention"
    return "minor"


def aggregate_elements(elements: list[dict], profiles: list[dict]) -> dict:
    """요소 레코드를 (element_type, element_subtype) 별로 집계해 리포트 dict 를 만든다."""
    video_ids = sorted({p["video_id"] for p in profiles})
    n_videos = len(video_ids)

    groups: dict[tuple[str, str], dict] = defaultdict(lambda: {"videos": set(), "examples": []})
    for e in elements:
        g = groups[(e["element_type"], e["element_subtype"])]
        g["videos"].add(e["video_id"])
        if len(g["examples"]) < 3:
            g["examples"].append({"video_id": e["video_id"], "cut_refs": e["cut_refs"],
                                  "document": e["document"][:120]})

    rows = [
        {
            "element_type": etype,
            "element_subtype": subtype,
            "video_count": len(g["videos"]),
            "ratio": round(len(g["videos"]) / n_videos, 3) if n_videos else 0.0,
            "judgement": _judge(n_videos, len(g["videos"])),
            "video_ids": sorted(g["videos"]),
            "examples": g["examples"],
        }
        for (etype, subtype), g in groups.items()
    ]
    rows.sort(key=lambda r: (_JUDGE_ORDER.index(r["judgement"]), -r["ratio"]))

    return {
        "n_videos": n_videos,
        "video_ids": video_ids,
        "rows": rows,
        "casting": _aggregate_casting(profiles),
    }


def _aggregate_casting(profiles: list[dict]) -> dict:
    """profile 메타데이터의 캐스팅 속성 분포를 집계한다."""
    n = len(profiles)
    dist: dict[str, dict] = {}
    for key in ("main_model", "age_band", "skin_look", "hair", "wardrobe",
                "expression_restraint", "narrative_pattern",
                "persuasion_engine", "narrative_form", "tone_register",
                "usp_category", "positioning_category", "price_tier"):
        counter: dict[str, int] = defaultdict(int)
        for p in profiles:
            val = p["metadata"].get(key)
            if val is not None:
                counter[str(val)] += 1
        if counter:
            dist[key] = {
                val: {"count": cnt, "ratio": round(cnt / n, 3) if n else 0.0}
                for val, cnt in sorted(counter.items(), key=lambda kv: -kv[1])
            }
    return dist


def format_report(report: dict, segment_desc: str) -> str:
    """리포트 dict 를 콘솔 출력용 텍스트 표로 만든다."""
    lines = [
        f"=== 클리셰 리포트: {segment_desc} (n={report['n_videos']}) ===",
        f"video_ids: {report['video_ids']}",
        "",
        f"{'판정':<15} {'element_type':<18} {'subtype':<24} {'빈도':>7}  video_ids",
    ]
    for r in report["rows"]:
        freq = f"{r['video_count']}/{report['n_videos']}"
        lines.append(
            f"{r['judgement']:<15} {r['element_type']:<18} {r['element_subtype']:<24} "
            f"{freq:>7}  {r['video_ids']}"
        )
    lines.append("")
    lines.append("--- 프로필 분포 (캐스팅·서사·차별성) ---")
    for key, values in report["casting"].items():
        top = ", ".join(f"{v}({d['count']})" for v, d in values.items())
        lines.append(f"  {key:<22}: {top}")
    return "\n".join(lines)
