"""pikk 기법 태깅 파이프라인 CLI: 전처리(pipeline 과 동일) → 컷별 태깅 → tags.json / proposals.json."""
import argparse
import os
from collections import Counter
from pathlib import Path

# TF가 처음 임포트되기 전에 설정해야 GPU 전체 선점을 막을 수 있음 (pipeline.cli 와 동일)
os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from pikk_tagging.llm import BACKENDS, LlmConfig, default_model
from pikk_tagging.preprocess import Preprocessed, load_preprocessed, run_preprocess
from pikk_tagging.tagger import TagConfig, tag_video
from pikk_tagging.vocab import Vocab, load_vocab
from pikk_tagging.results_io import save_json

_OUTPUT_ROOT = Path("outputs/pikk_tagging")
_CUT_BACKENDS = ("transnetv2", "scenedetect")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="pikk 기법 태깅 파이프라인 (전처리 → 컷별 태깅)")
    p.add_argument("--video_id", type=int, default=None, help="video_uploads.id (단일)")
    p.add_argument("--video_ids", type=str, default=None, help="범위 (예: 1-10 / 1,3,5 / 1-5,7)")
    p.add_argument("--video_path", type=Path, default=None, help="영상 파일 직접 지정 (DB 조회 생략)")
    p.add_argument("--cut_backend", choices=_CUT_BACKENDS, default="transnetv2")
    p.add_argument("--threshold", type=float, default=None, help="컷 감지 민감도 (기본: 백엔드별)")
    p.add_argument("--max_cuts", type=int, default=10, help="최대 컷 수 (기본: 10)")
    p.add_argument("--out_dir", type=Path, default=None, help=f"결과 루트 (기본: {_OUTPUT_ROOT})")
    p.add_argument("--skip_preprocess", action="store_true", help="out_dir 의 기존 전처리 결과 재사용")
    p.add_argument("--preprocess_dir", type=Path, default=None,
                   help="기존 전처리 결과 루트(<root>/<video_id>/). 지정하면 전처리를 생략하고 여기서 읽으며, 태깅 결과만 out_dir 에 저장")
    p.add_argument("--cache_dir", type=str, default="/root/.cache", help="HuggingFace·모델 캐시 루트")
    p.add_argument("--llm_backend", choices=BACKENDS, default="gemini", help="비전 LLM (기본: gemini)")
    p.add_argument("--model", type=str, default=None, help="모델명 (기본: backend 별 utils 기본값)")
    p.add_argument("--passes", type=int, default=2, help="축별 반복 횟수, 과반 득표만 채택 (기본: 2)")
    p.add_argument("--max_frames", type=int, default=8, help="컷당 LLM 에 넣는 최대 프레임 수 (기본: 8)")
    p.add_argument("--no_verify", action="store_true", help="태그별 2차 검증 호출을 생략")
    p.add_argument("--seed", type=str, default="0", help="어휘 순서 셔플 시드 (기본: 0)")
    p.add_argument("--max_tags_per_cut", type=int, default=5, help="컷당 최대 태그 수 (기본: 5)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.passes < 1 or args.max_frames < 1:
        raise SystemExit("오류: --passes, --max_frames 는 1 이상이어야 합니다.")
    os.environ["HF_HOME"] = args.cache_dir
    cfg = _make_config(args)
    vocab = load_vocab()
    if args.video_path is not None:
        if args.video_id is not None or args.video_ids is not None:
            raise SystemExit("오류: --video_path 와 --video_id / --video_ids 는 동시에 사용할 수 없습니다.")
        _run_video(args, cfg, vocab, None, args.video_path)
        return
    video_ids = _parse_video_ids(args)
    for i, video_id in enumerate(video_ids, 1):
        print(f"\n{'─' * 50}\n  [{i}/{len(video_ids)}] video_id={video_id}\n{'─' * 50}")
        _run_video(args, cfg, vocab, video_id, None)


def _parse_video_ids(args: argparse.Namespace) -> list[int]:
    """--video_id / --video_ids 를 정수 목록으로 변환한다 ('1-5,7,9-12' 형식 지원)."""
    if args.video_id is not None and args.video_ids is not None:
        raise SystemExit("오류: --video_id 와 --video_ids 는 동시에 사용할 수 없습니다.")
    if args.video_id is not None:
        return [args.video_id]
    if not args.video_ids:
        raise SystemExit("오류: --video_id 또는 --video_ids 를 지정하세요.")
    ids: list[int] = []
    for part in args.video_ids.split(","):
        lo, _, hi = part.strip().partition("-")
        ids.extend(range(int(lo), int(hi) + 1) if hi else [int(lo)])
    return ids


def _make_config(args: argparse.Namespace) -> TagConfig:
    model = args.model or default_model(args.llm_backend)
    return TagConfig(
        llm=LlmConfig(args.llm_backend, model),
        passes=args.passes,
        max_frames=args.max_frames,
        verify=not args.no_verify,
        seed=args.seed,
        max_tags_per_cut=args.max_tags_per_cut,
    )


def _run_video(args, cfg: TagConfig, vocab: Vocab, video_id: int | None, video_path: Path | None) -> None:
    key = video_path.stem if video_path is not None else str(video_id)
    out = (args.out_dir if args.out_dir is not None else _OUTPUT_ROOT) / key
    src = out
    if args.preprocess_dir is not None:
        src = args.preprocess_dir / key
        print(f"[1-7/7] 전처리 단계 생략 (--preprocess_dir: {src})")
        pre = load_preprocessed(src)
    elif args.skip_preprocess:
        print("[1-7/7] 전처리 단계 생략 (--skip_preprocess)")
        pre = load_preprocessed(out)
    else:
        pre = run_preprocess(video_id, video_path, out, args.cut_backend, args.threshold, args.max_cuts)
    print(f"[태깅] 컷 수={len(pre.cuts)}, backend={cfg.llm.backend}, model={cfg.llm.model}, passes={cfg.passes}, verify={cfg.verify}")
    _tag_and_save(pre, src, out, vocab, cfg, key)


def _tag_and_save(pre: Preprocessed, src: Path, out: Path, vocab: Vocab, cfg: TagConfig, key: str) -> None:
    cuts = tag_video(pre.cuts, src / "frames", pre.ocr, vocab, cfg, key)
    save_json(out / "tags.json", _build_document(key, vocab, cfg, cuts))
    save_json(out / "proposals.json", _flatten_proposals(key, cuts))
    print(f"      완료  →  {out / 'tags.json'}")
    print(f"      {_summary(cuts)}")


def _build_document(key: str, vocab: Vocab, cfg: TagConfig, cuts: list[dict]) -> dict:
    return {
        "video": key,
        "vocab_version": vocab.version,
        "backend": cfg.llm.backend,
        "model": cfg.llm.model,
        "passes": cfg.passes,
        "max_frames": cfg.max_frames,
        "verify": cfg.verify,
        "seed": cfg.seed,
        "cuts": cuts,
    }


def _flatten_proposals(key: str, cuts: list[dict]) -> list[dict]:
    return [{"video": key, "cut_index": c["cut_index"], **p} for c in cuts for p in c["proposals"]]


def _summary(cuts: list[dict]) -> str:
    tags = Counter(t["id"] for c in cuts for t in c["tags"])
    rej = Counter(r["stage"] for c in cuts for r in c["rejected"])
    errs = sum(len(c["errors"]) for c in cuts)
    return f"태그 {sum(tags.values())}개 {dict(tags)} / 탈락 {dict(rej)} / 오류 {errs}건"


if __name__ == "__main__":
    main()
