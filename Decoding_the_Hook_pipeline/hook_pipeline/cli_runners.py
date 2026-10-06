"""cli.py 서브커맨드 실행부. 무거운 의존성(whisper, BERTopic)은 해당 커맨드에서만 불러온다."""
import argparse
import traceback

from hook_pipeline.video_source import VideoSource, expand_id_range, from_path, from_video_id


def run_extract_command(args: argparse.Namespace) -> None:
    """영상 목록을 순회하며 extract 단계를 실행한다. 한 영상이 실패해도 나머지는 계속 처리한다."""
    from hook_pipeline.extract import ExtractOptions, run_extract
    from hook_pipeline.hook_audio import release_asr

    opt = ExtractOptions(
        out_root=args.out_dir, sampling=args.sampling, num_frames=args.num_frames, alpha=args.alpha,
        min_interval=args.min_interval, seed=args.seed, hook_sec=args.hook_sec,
        llm_backend=args.llm_backend, llm_model=args.llm_model, asr_model=args.asr_model,
        asr_language=None if args.asr_language == "auto" else args.asr_language,
    )
    targets = _resolve_targets(args)
    failed: list[str] = []
    for i, target in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {target}")
        try:
            src = target if isinstance(target, VideoSource) else from_video_id(target)
            run_extract(src, opt)
        except Exception as exc:
            failed.append(str(target))
            print(f"  [ERROR] {type(exc).__name__}: {exc}")
            traceback.print_exc()
    release_asr()
    print(f"\n완료: {len(targets) - len(failed)}/{len(targets)}" + (f"  실패: {', '.join(failed)}" if failed else ""))


def _resolve_targets(args: argparse.Namespace) -> list:
    if args.video_path is not None:
        if args.video_id is not None or args.video_ids is not None:
            raise SystemExit("오류: --video_path 와 --video_id / --video_ids 는 동시에 사용할 수 없습니다.")
        return [from_path(args.video_path)]
    return _parse_video_ids(args)


def _parse_video_ids(args: argparse.Namespace) -> list[int]:
    if args.video_id is not None and args.video_ids is not None:
        raise SystemExit("오류: --video_id 와 --video_ids 는 동시에 사용할 수 없습니다.")
    if args.video_ids:
        return expand_id_range(args.video_ids)
    if args.video_id is not None:
        return [args.video_id]
    raise SystemExit("오류: --video_id, --video_ids 또는 --video_path 를 지정하세요.")


def run_topics_command(args: argparse.Namespace) -> None:
    """extract 결과 전체(또는 --video_id(s) 지정분)로 BERTopic 을 학습하고 대표값을 저장한다."""
    from hook_pipeline import topics_report as rep
    from hook_pipeline.topics import fit_best_topic_model

    keys = None
    if args.video_id is not None or args.video_ids:
        keys = {str(v) for v in _parse_video_ids(args)}
    records = rep.load_corpus(args.out_dir, keys)
    docs = [rep.to_document(r) for r in records]
    print(f"[1/3] 문서 수집: {len(docs)}개 ({args.out_dir})")

    candidates = [int(k) for k in args.nr_topics.split(",") if k.strip()]
    print(f"[2/3] BERTopic 학습 + perplexity 비교 (후보: {candidates})")
    fit, scores = fit_best_topic_model(docs, candidates, args.min_cluster_size, args.embedding_model, args.seed)
    print(f"      선택: nr_topics={fit.candidate} (perplexity={fit.perplexity:.2f})")

    topic_info = rep.build_topic_info(fit, records, docs)
    table = rep.build_feature_table(fit, records, topic_info)
    out = args.out_dir / "_topics"
    rep.save_outputs(out, fit, scores, topic_info, table, args.embedding_model)
    print(f"[3/3] 저장 완료 → {out}")
    for t in topic_info:
        words = ", ".join(w["word"] for w in t["top_words"][:5])
        print(f"      Topic {t['topic']:>3} ({t['count']:>3}개) {t['label']}  |  {words}")
