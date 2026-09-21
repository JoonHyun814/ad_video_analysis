"""컷 단위 태깅 오케스트레이션: 축별 생성(순서 셔플 × N회) → 다수결 → 태그별 검증 → 컷 상한."""
from dataclasses import dataclass
from pathlib import Path

from pikk_tagging.frame_select import FrameList, load_frame_map, select_cut_frames
from pikk_tagging.llm import LlmConfig, call_vision
from pikk_tagging.prompts import build_tag_prompt
from pikk_tagging.schema import ParsedPass, parse_tag_response
from pikk_tagging.verify import verify_tag
from pikk_tagging.voting import vote
from pikk_tagging.vocab import Vocab, shuffled

_CONF_RANK = {"high": 2, "medium": 1}


@dataclass(frozen=True)
class TagConfig:
    llm: LlmConfig
    passes: int = 2
    max_frames: int = 8
    verify: bool = True
    seed: str = "0"
    max_tags_per_cut: int = 5


def tag_video(cuts: list, frames_dir: Path, ocr_data: dict, vocab: Vocab, cfg: TagConfig, video_key: str) -> list[dict]:
    """모든 컷을 컷 단위로만 태깅한다 (영상 전체 태그는 만들지 않는다)."""
    frame_map = load_frame_map(frames_dir)
    results = []
    for cut in cuts:
        frames = select_cut_frames(frame_map, cut, cfg.max_frames)
        print(f"      [{cut.index}/{len(cuts)}] {cut.start_sec:.2f}~{cut.end_sec:.2f}s  {len(frames)} frames")
        results.append(tag_cut(cut, frames, ocr_data, vocab, cfg, video_key))
    return results


def tag_cut(cut, frames: FrameList, ocr_data: dict, vocab: Vocab, cfg: TagConfig, video_key: str) -> dict:
    """컷 하나를 태깅해 tags / rejected / proposals / errors 를 담은 dict 를 반환한다."""
    result = {
        "cut_index": cut.index, "start_sec": cut.start_sec, "end_sec": cut.end_sec,
        "frame_times": [t for t, _ in frames], "observations": {},
        "tags": [], "rejected": [], "proposals": [], "errors": [],
    }
    if not frames:
        result["errors"].append({"axis": "*", "reason": "no_frames"})
        return result
    span = (cut.start_sec, cut.end_sec)
    kept: list[dict] = []
    for axis in vocab.axes:
        kept += _run_axis(axis, cut.index, frames, span, ocr_data, vocab, cfg, video_key, result)
    if cfg.verify:
        kept = _verify_all(kept, frames, span, vocab, cfg, result)
    else:
        kept = [{**t, "verified": None} for t in kept]
    result["tags"] = _cap_cut(kept, cfg.max_tags_per_cut, result["rejected"])
    return result


def _run_axis(axis, cut_index, frames, span, ocr_data, vocab, cfg, video_key, result) -> list[dict]:
    spec = vocab.axes[axis]
    techs = vocab.axis_techniques(axis)
    passes: list[ParsedPass | None] = []
    for i in range(cfg.passes):
        order = shuffled(techs, f"{cfg.seed}:{video_key}:{cut_index}:{axis}:{i}")
        prompt = build_tag_prompt(spec["label"], order, frames, span, spec["max_tags"],
                                  ocr_data if spec.get("use_ocr") else None)
        parsed, err = _one_pass(prompt, frames, {t.id for t in techs}, spec["max_tags"], vocab, cfg)
        if err:
            result["errors"].append({"axis": axis, "pass": i, "reason": err})
        passes.append(parsed)
    kept, vote_rejected, n_ok = vote(passes, axis)
    if n_ok == 0:
        result["errors"].append({"axis": axis, "reason": "all_passes_failed"})
    _collect_side_outputs(axis, passes, vote_rejected, result)
    return kept


def _one_pass(prompt, frames, axis_ids, max_tags, vocab, cfg) -> tuple[ParsedPass | None, str | None]:
    try:
        raw = call_vision(prompt, [p for _, p in frames], cfg.llm.backend, cfg.llm.model)
    except Exception as e:  # 한 번의 호출 실패가 배치 전체를 죽이지 않도록 기록만 한다
        return None, f"call_error: {e}"
    parsed = parse_tag_response(raw, axis_ids, len(frames), max_tags, vocab)
    return parsed, (None if parsed is not None else "parse_failed")


def _collect_side_outputs(axis: str, passes: list, vote_rejected: list[dict], result: dict) -> None:
    ok = [p for p in passes if p is not None]
    obs = next((p.observation for p in ok if p.observation), "")
    if obs:
        result["observations"][axis] = obs
    rejected = [r for p in ok for r in p.rejected] + vote_rejected
    seen = {(r["id"], r["stage"], r["reason"], r.get("axis")) for r in result["rejected"]}
    for r in rejected:
        key = (r["id"], r["stage"], r["reason"], axis)
        if key not in seen:
            seen.add(key)
            result["rejected"].append({**r, "axis": axis})
    known = {p["term"].lower() for p in result["proposals"]}
    for p in (q for pp in ok for q in pp.proposals):
        if p["term"].lower() not in known:
            known.add(p["term"].lower())
            result["proposals"].append({**p, "axis": axis})


def _verify_all(kept: list[dict], frames: FrameList, span, vocab: Vocab, cfg: TagConfig, result: dict) -> list[dict]:
    final = []
    for tag in kept:
        info = verify_tag(vocab.techniques[tag["id"]], frames, span, cfg.llm)
        if info["present"] is True:
            final.append({**tag, "verified": True, "verify": {"frames": info["frames"], "reason": info["reason"]}})
            continue
        stage = "verify_error" if info["present"] is None else "verify"
        result["rejected"].append({"id": tag["id"], "axis": tag["axis"], "stage": stage, "reason": info["reason"]})
    return final


def _cap_cut(tags: list[dict], max_n: int, rejected: list[dict]) -> list[dict]:
    ranked = sorted(tags, key=lambda t: (-_CONF_RANK[t["confidence"]], -int(t["votes"].split("/")[0])))
    for extra in ranked[max_n:]:
        rejected.append({"id": extra["id"], "axis": extra["axis"], "stage": "cut_cap", "reason": "over_cut_cap"})
    return ranked[:max_n]
