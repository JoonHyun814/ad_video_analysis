"""태깅 결과 리뷰용 단일 HTML 을 만든다.

keyframe·LLM 에 넣은 프레임 옆에서 태그·근거를 보고 정답/오답을 표시한 뒤 골든셋 JSON(evaluate.py 입력 형식)으로 내보낸다.
이미지는 HTML 에 넣지 않고 상대경로로 참조하므로, 만든 HTML 은 전처리 폴더와의 상대 위치를 유지한 채 열어야 한다.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

from pikk_tagging.results_io import load_tag_documents
from pikk_tagging.vocab import load_vocab

_TEMPLATE = Path(__file__).with_name("review_template.html")
_FRAME_TOL = 0.011


def _url(path: Path, base: Path) -> str:
    return quote(Path(os.path.relpath(path, base)).as_posix())


def _frame_time(idx: int, cut: dict) -> float:
    """pipeline.cut_analysis._get_cut_frames 와 같은 공식으로 프레임의 시각을 구한다."""
    span_frames = max(cut["end_frame"] - cut["start_frame"], 1)
    span_sec = cut["end_sec"] - cut["start_sec"]
    return round(cut["start_sec"] + (idx - cut["start_frame"]) / span_frames * span_sec, 2)


def _cut_frames(cut: dict, used_times: list[float], frames_dir: Path, base: Path) -> list[dict]:
    """컷 범위의 모든 프레임을 시간순으로 반환한다. n 은 LLM 에 넣은 프레임의 1-based 번호(안 넣었으면 None)."""
    found = []
    for path in frames_dir.glob("frame_*.jpg"):
        idx = int(path.stem.removeprefix("frame_"))
        if cut["start_frame"] <= idx <= cut["end_frame"]:
            found.append((_frame_time(idx, cut), path))
    out = []
    for t, path in sorted(found):
        n = next((i for i, u in enumerate(used_times, 1) if abs(u - t) < _FRAME_TOL), None)
        out.append({"src": _url(path, base), "t": t, "n": n})
    return out


def _tag_entry(tag: dict) -> dict:
    return {
        "id": tag["id"], "axis": tag["axis"], "confidence": tag["confidence"], "votes": tag["votes"],
        "verified": tag.get("verified") is True, "frames": tag["evidence"]["frames"],
        "note": tag["evidence"]["note"], "verify_reason": (tag.get("verify") or {}).get("reason", ""),
    }


def _cut_entry(doc_cut: dict, meta: dict, src: Path, base: Path, starred: bool) -> dict:
    keyframe = next(iter(sorted((src / "keyframes").glob(f"cut_{doc_cut['cut_index']:03d}_*.jpg"))), None)
    return {
        "index": doc_cut["cut_index"], "start": doc_cut["start_sec"], "end": doc_cut["end_sec"],
        "keyframe": _url(keyframe, base) if keyframe else None,
        "frames": _cut_frames(meta, doc_cut["frame_times"], src / "frames", base),
        "tags": [_tag_entry(t) for t in doc_cut["tags"]],
        "rejected": [{"id": r["id"], "stage": r["stage"], "reason": r["reason"]} for r in doc_cut["rejected"]],
        "observations": doc_cut["observations"], "errors": doc_cut["errors"], "priority": starred,
    }


def build_data(pred_dir: Path, preprocess_dir: Path, base: Path, priority: set[tuple[str, int]]) -> dict:
    """tags.json 들과 전처리 폴더를 합쳐 HTML 에 임베드할 데이터를 만든다."""
    videos = []
    for key, doc in load_tag_documents(pred_dir).items():
        src = preprocess_dir / key
        metas = {m["index"]: m for m in json.loads((src / "cuts.json").read_text(encoding="utf-8"))}
        cuts = [_cut_entry(c, metas[c["cut_index"]], src, base, (key, c["cut_index"]) in priority) for c in doc["cuts"]]
        videos.append({"id": key, "cuts": cuts})
    videos.sort(key=lambda v: (not v["id"].isdigit(), int(v["id"]) if v["id"].isdigit() else 0, v["id"]))
    return {"vocab": _vocab_data(), "videos": videos}


def _vocab_data() -> dict:
    vocab = load_vocab()
    techniques = [
        {"id": t.id, "axis": t.axis, "definition": t.definition, "include": list(t.include), "exclude": list(t.exclude)}
        for t in vocab.techniques.values()
    ]
    return {"axes": vocab.axes, "techniques": techniques}


def _parse_priority(spec: str) -> set[tuple[str, int]]:
    pairs = set()
    for item in filter(None, (s.strip() for s in spec.split(","))):
        video, _, cut = item.partition("-")
        pairs.add((video, int(cut)))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description="태깅 결과 리뷰 GUI(단일 HTML) 생성")
    ap.add_argument("--pred_dir", type=Path, required=True, help="태깅 결과 루트 (<root>/<video>/tags.json)")
    ap.add_argument("--preprocess_dir", type=Path, required=True, help="전처리 결과 루트 (<root>/<video>/keyframes, frames, cuts.json)")
    ap.add_argument("--out", type=Path, default=None, help="출력 HTML (기본: <pred_dir>/review.html)")
    ap.add_argument("--priority", type=str, default="", help="★ 추천 컷 목록 (예: 7-3,8-2,10-3)")
    args = ap.parse_args()

    out = (args.out or args.pred_dir / "review.html").resolve()
    data = build_data(args.pred_dir, args.preprocess_dir, out.parent, _parse_priority(args.priority))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(_TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/", payload), encoding="utf-8")
    print(f"리뷰 페이지 생성: {out}  (영상 {len(data['videos'])}개, 컷 {sum(len(v['cuts']) for v in data['videos'])}개)")


if __name__ == "__main__":
    main()
