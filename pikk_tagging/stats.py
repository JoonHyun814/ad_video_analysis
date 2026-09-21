"""배치 결과 진단: 기법별 컷 단위 태깅 비율을 사이트 사전 비율(site_prior)과 비교하고, 단계별 탈락 수를 집계한다.

과다 태깅(모델의 빈도 편향)을 찾는 용도다. site_prior 는 '장면' 단위, 여기 비율은 '컷' 단위라 대략적인 비교 기준이다.
"""
import argparse
from collections import Counter
from pathlib import Path

from pikk_tagging.results_io import load_tag_documents
from pikk_tagging.vocab import Vocab, load_vocab


def tag_rates(docs: dict[str, dict], vocab: Vocab) -> tuple[dict[str, float], int, Counter]:
    """(기법별 태깅 컷 비율, 전체 컷 수, 탈락 stage 카운터) 를 반환한다."""
    cuts = [c for doc in docs.values() for c in doc["cuts"]]
    hits = Counter(t["id"] for c in cuts for t in c["tags"])
    stages = Counter(r["stage"] for c in cuts for r in c["rejected"])
    total = len(cuts)
    return {tid: hits[tid] / total for tid in vocab.techniques} if total else {}, total, stages


def main() -> None:
    ap = argparse.ArgumentParser(description="기법별 태깅 비율 vs 사이트 비율 진단")
    ap.add_argument("--pred_dir", type=Path, required=True, help="태깅 결과 루트 (<root>/<video>/tags.json)")
    ap.add_argument("--factor", type=float, default=2.0, help="사이트 비율의 몇 배 초과를 과다로 표시 (기본: 2.0)")
    args = ap.parse_args()

    vocab = load_vocab()
    rates, total, stages = tag_rates(load_tag_documents(args.pred_dir), vocab)
    print(f"컷 수: {total}")
    print(f"{'기법':<14}{'태깅률':>8}{'사이트':>8}{'배수':>7}")
    for tid, rate in rates.items():
        prior = vocab.techniques[tid].site_prior
        ratio = rate / prior if prior else float("inf")
        flag = "  ← 과다?" if ratio > args.factor else ""
        print(f"{tid:<14}{rate:>8.3f}{prior:>8.3f}{ratio:>7.2f}{flag}")
    print(f"탈락 stage: {dict(stages)}")


if __name__ == "__main__":
    main()
