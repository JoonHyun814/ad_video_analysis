"""LLM 응답을 검증·정규화한다. 어휘 밖 id, 근거 없는 태그는 여기서 걸러 rejected 로 기록한다."""
from dataclasses import dataclass, field

from pikk_tagging.vocab import Vocab
from utils.io_checks import is_parse_failed

_CONF_RANK = {"high": 2, "medium": 1}


@dataclass
class Candidate:
    id: str
    frames: list[int]
    evidence: str
    confidence: str


@dataclass
class ParsedPass:
    observation: str = ""
    candidates: list[Candidate] = field(default_factory=list)
    proposals: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


def clean_frames(raw: object, n_frames: int) -> list[int]:
    """근거 프레임 번호 중 1..n_frames 범위의 정수만 중복 없이 남긴다."""
    if not isinstance(raw, list):
        return []
    valid = {v for v in raw if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= n_frames}
    return sorted(valid)


def parse_tag_response(raw: dict, axis_ids: set[str], n_frames: int, max_tags: int, vocab: Vocab) -> ParsedPass | None:
    """태깅 응답을 ParsedPass 로 변환한다. JSON 파싱 실패면 None (호출자가 실패한 pass 로 취급)."""
    if not isinstance(raw, dict) or is_parse_failed(raw):
        return None
    parsed = ParsedPass(observation=str(raw.get("observation", "")).strip())
    seen: set[str] = set()
    for entry in _as_dicts(raw.get("tags")):
        _accept_or_reject(entry, axis_ids, n_frames, seen, parsed)
    _apply_axis_cap(parsed, max_tags)
    parsed.proposals = _clean_proposals(raw.get("proposals"), n_frames, vocab, parsed.rejected)
    return parsed


def _as_dicts(value: object) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _accept_or_reject(entry: dict, axis_ids: set[str], n_frames: int, seen: set[str], parsed: ParsedPass) -> None:
    tag_id = str(entry.get("id", "")).strip()
    reason = _reject_reason(entry, tag_id, axis_ids, seen)
    frames = clean_frames(entry.get("frames"), n_frames)
    if reason is None and not frames:
        reason = "no_valid_evidence_frames"
    if reason is not None:
        parsed.rejected.append({"id": tag_id, "stage": "schema", "reason": reason})
        return
    seen.add(tag_id)
    parsed.candidates.append(Candidate(tag_id, frames, str(entry["evidence"]).strip(), entry["confidence"]))


def _reject_reason(entry: dict, tag_id: str, axis_ids: set[str], seen: set[str]) -> str | None:
    if tag_id not in axis_ids:
        return "not_in_vocab"
    if tag_id in seen:
        return "duplicate"
    if entry.get("confidence") not in _CONF_RANK:
        return "invalid_confidence"
    if not str(entry.get("evidence", "")).strip():
        return "no_evidence_note"
    return None


def _apply_axis_cap(parsed: ParsedPass, max_tags: int) -> None:
    ranked = sorted(parsed.candidates, key=lambda c: -_CONF_RANK[c.confidence])
    for extra in ranked[max_tags:]:
        parsed.rejected.append({"id": extra.id, "stage": "schema", "reason": "over_axis_cap"})
    parsed.candidates = ranked[:max_tags]


def _clean_proposals(raw: object, n_frames: int, vocab: Vocab, rejected: list[dict]) -> list[dict]:
    """제안 중 기존 기법의 별칭이면 버리고(rejected 기록), 나머지는 검수 큐용으로 남긴다."""
    out = []
    for entry in _as_dicts(raw):
        term = str(entry.get("term", "")).strip()
        if not term:
            continue
        alias_of = vocab.normalize_term(term)
        if alias_of is not None:
            rejected.append({"id": term, "stage": "schema", "reason": f"proposal_is_alias_of:{alias_of}"})
            continue
        out.append({
            "term": term,
            "frames": clean_frames(entry.get("frames"), n_frames),
            "evidence": str(entry.get("evidence", "")).strip(),
        })
    return out
