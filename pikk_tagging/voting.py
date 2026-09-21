"""여러 번(다른 어휘 순서) 돌린 태깅 결과를 다수결로 합친다 (자기 일관성)."""
from collections import defaultdict

from pikk_tagging.schema import Candidate, ParsedPass

_CONF_RANK = {"high": 2, "medium": 1}


def vote(passes: list[ParsedPass | None], axis: str) -> tuple[list[dict], list[dict], int]:
    """성공한 pass 의 과반(초과)에서 나온 태그만 남긴다. (채택 태그, 탈락 기록, 성공 pass 수) 를 반환한다."""
    ok = [p for p in passes if p is not None]
    by_id: dict[str, list[Candidate]] = defaultdict(list)
    for p in ok:
        for cand in p.candidates:
            by_id[cand.id].append(cand)

    kept, rejected = [], []
    for tag_id, cands in by_id.items():
        if len(cands) * 2 > len(ok):
            kept.append(_merge(tag_id, axis, cands, len(ok)))
        else:
            rejected.append({"id": tag_id, "stage": "vote", "reason": f"votes {len(cands)}/{len(ok)}"})
    return kept, rejected, len(ok)


def _merge(tag_id: str, axis: str, cands: list[Candidate], n_ok: int) -> dict:
    best = max(cands, key=lambda c: _CONF_RANK[c.confidence])
    all_high = all(c.confidence == "high" for c in cands)
    return {
        "id": tag_id,
        "axis": axis,
        "confidence": "high" if all_high else "medium",
        "votes": f"{len(cands)}/{n_ok}",
        "evidence": {
            "frames": sorted({f for c in cands for f in c.frames}),
            "note": best.evidence,
        },
    }
