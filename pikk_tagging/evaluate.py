"""골든셋(사람 라벨) 대비 태그별 precision / recall / F1 을 계산한다. 프롬프트·모델 변경 시 회귀 테스트용.

골든 형식: {"<video_key>": {"<cut_index>": ["탑뷰", "로우키"], ...}, ...}  (라벨이 없는 컷은 빈 배열)
"""
import argparse
import json
from pathlib import Path

from pikk_tagging.results_io import load_tag_documents
from pikk_tagging.vocab import load_vocab


def predicted_sets(docs: dict[str, dict]) -> dict[str, dict[str, set[str]]]:
    """{video: {cut_index(str): {태그 id}}} 로 변환한다."""
    return {
        video: {str(c["cut_index"]): {t["id"] for t in c["tags"]} for c in doc["cuts"]}
        for video, doc in docs.items()
    }


def compute_metrics(golden: dict, preds: dict, tech_ids: list[str]) -> dict[str, dict]:
    """골든에 있는 (영상, 컷)만 채점한다. 예측 결과가 없는 영상은 건너뛰고, 없는 컷은 빈 예측으로 본다."""
    counts = {t: {"tp": 0, "fp": 0, "fn": 0} for t in tech_ids}
    for video, cuts in golden.items():
        if video not in preds:
            print(f"      [경고] 예측 결과 없음, 건너뜀: {video}")
            continue
        for cut, labels in cuts.items():
            _count_cut(counts, set(labels), preds[video].get(str(cut), set()))
    return {t: _scores(c) for t, c in counts.items()} | {"__micro__": _scores(_sum(counts))}


def _count_cut(counts: dict, gold: set[str], pred: set[str]) -> None:
    for tech, c in counts.items():
        c["tp"] += tech in gold and tech in pred
        c["fp"] += tech not in gold and tech in pred
        c["fn"] += tech in gold and tech not in pred


def _sum(counts: dict) -> dict[str, int]:
    return {k: sum(c[k] for c in counts.values()) for k in ("tp", "fp", "fn")}


def _scores(c: dict[str, int]) -> dict:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {**c, "precision": p, "recall": r, "f1": f1}


def _fmt(v: float | None) -> str:
    return "  -  " if v is None else f"{v:.3f}"


def main() -> None:
    ap = argparse.ArgumentParser(description="골든셋 대비 태깅 정확도 평가")
    ap.add_argument("--golden", type=Path, required=True, help="골든 JSON 경로")
    ap.add_argument("--pred_dir", type=Path, required=True, help="태깅 결과 루트 (<root>/<video>/tags.json)")
    ap.add_argument("--out", type=Path, default=None, help="결과 JSON 저장 경로 (선택)")
    args = ap.parse_args()

    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    preds = predicted_sets(load_tag_documents(args.pred_dir))
    metrics = compute_metrics(golden, preds, list(load_vocab().techniques))

    print(f"{'기법':<14}{'TP':>4}{'FP':>4}{'FN':>4}  {'P':>5}  {'R':>5}  {'F1':>5}")
    for tech, m in metrics.items():
        name = "(micro)" if tech == "__micro__" else tech
        print(f"{name:<14}{m['tp']:>4}{m['fp']:>4}{m['fn']:>4}  {_fmt(m['precision'])}  {_fmt(m['recall'])}  {_fmt(m['f1'])}")
    if args.out is not None:
        args.out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
