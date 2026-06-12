"""분석 결과 JSON을 출력 형식으로 변환한다.

--mode parsed (기본): parsed_analysis.json → claude_preprocessed_v1 스키마 변환
--mode brief        : brief_analysis.json → out_dir/<video_id>.json 으로 그대로 저장
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

_PIPELINE_FILES = {
    "parsed": "parsed_analysis.json",
    "cut_analysis": "cut_analysis.json",
    "scene_analysis": "scene_analysis.json",
    "stt": "stt.json",
    "audio": "audio_analysis.json",
    "cuts_raw": "cuts.json",
}

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="분석 결과 JSON 일괄 변환")
    p.add_argument("--video_dir", type=Path, required=True, help="<video_id> 하위 폴더들이 들어있는 루트 디렉토리")
    p.add_argument("--out_dir", type=Path, required=True, help="결과 JSON 저장 디렉토리 (<video_id>.json 으로 저장)")
    p.add_argument("--mode", choices=["parsed", "brief"], default="parsed", help="변환 모드 (기본: parsed)")
    return p


def load_sources(video_dir: Path) -> dict:
    """video_dir 안의 파이프라인 산출 JSON 파일들을 한 번에 로드한다."""
    out: dict = {}
    for key, name in _PIPELINE_FILES.items():
        path = video_dir / name
        out[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if out.get("parsed") is None:
        raise FileNotFoundError(f"parsed_analysis.json 없음: {video_dir}")
    return out


def convert(sources: dict, video_filename: str, video_id: int) -> dict:
    """파이프라인 결과 묶음을 claude_preprocessed_v1 최상위 구조로 조립한다."""
    parsed = sources["parsed"]
    result = {
        "labeling_data": _build_labeling_data(parsed),
        "sequences": _build_sequences(parsed),
        "cuts": _build_cuts(parsed, sources),
        "key_scenes": _build_key_scenes(parsed),
    }
    return {
        "video": video_filename,
        "parse_success": not bool(parsed.get("error")),
        "analysis_metadata": _build_metadata(parsed),
        "raw_output": "",
        "result": result,
        "video_id": video_id,
    }


def _build_metadata(parsed: dict) -> dict:
    pi = parsed.get("pipeline_inputs") or {}
    return {
        "model": pi.get("model"),
        "prompt_version": parsed.get("schema_version", "pipeline_v1"),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "inference_time_sec": None,
        "agent_mode": False,
        "engine": "ad_video_analysis pipeline",
        "num_turns": None,
    }


def _build_labeling_data(parsed: dict) -> dict:
    nc = parsed.get("narrative_classification") or {}
    os_ = parsed.get("overall_strategy") or {}
    cuts = parsed.get("cuts") or []
    base = {
        "narrative_type": nc.get("narrative_type"),
        "narrative_confidence": nc.get("confidence"),
        "narrative_reasoning": nc.get("reasoning"),
        "narrative_structure": os_.get("narrative_structure"),
        "creative_style": os_.get("creative_style"),
        "tagline": os_.get("tagline"),
        "brand_first_sec": _first_sec(cuts, "brand_visible"),
        "product_first_sec": _first_sec(cuts, "product_visible"),
        "role_sequence": parsed.get("role_sequence"),
        "narrative_summary": parsed.get("narrative_summary"),
        "step1_has_problem": parsed.get("step1_has_problem", False),
        "step2_has_review": parsed.get("step2_has_review", False),
    }
    base.update(_hook_fields(os_.get("hook_strategy") or {}))
    base.update(_av_fields(os_.get("audio_visual_strategy") or {}))
    base.update(_close_fields(os_.get("close_strategy") or {}))
    base.update(_message_fields(os_.get("message_hierarchy") or {}))
    return base


def _hook_fields(hook: dict) -> dict:
    return {
        "hook_technique": hook.get("technique"),
        "skip_resistance_strategy": hook.get("skip_resistance_strategy"),
        "opening_device": hook.get("opening_device"),
        "first_frame_element": hook.get("first_frame_element"),
        "speech_in_first_3sec": hook.get("speech_in_first_scene"),
        "text_in_first_3sec": hook.get("text_in_first_scene"),
        "brand_in_first_3sec": hook.get("brand_in_first_scene"),
    }


def _av_fields(av: dict) -> dict:
    text_carries = av.get("text_carries_primary_message")
    return {
        "voiceover_type": av.get("voiceover_type"),
        "voiceover_tone": av.get("voiceover_tone"),
        "mute_optimized": bool(text_carries),
        "music_role": av.get("music_role"),
        "music_tempo": av.get("music_tempo"),
        "text_carries_primary_message": text_carries,
    }


def _close_fields(close: dict) -> dict:
    promo = close.get("promo_info")
    return {
        "close_type": close.get("close_type"),
        "end_card_elements": close.get("end_card_elements") or [],
        "cta_type": close.get("cta_type"),
        "promo_type": "none" if not promo else "custom",
        "promo_detail": promo,
    }


def _message_fields(msg: dict) -> dict:
    return {
        "primary_message": msg.get("primary_message"),
        "supporting_messages": msg.get("supporting_messages") or [],
        "message_repetition_count": msg.get("message_repetition_count", 0),
    }


def _first_sec(cuts: list, flag: str) -> float | None:
    for c in cuts:
        if c.get(flag):
            return c.get("start_sec", 0.0)
    return None


def _build_sequences(parsed: dict) -> list:
    seqs = parsed.get("sequences") or []
    cuts = parsed.get("cuts") or []
    keys = parsed.get("key_scenes") or []
    return [_one_sequence(s, i, cuts, keys) for i, s in enumerate(seqs)]


def _one_sequence(s: dict, idx: int, cuts: list, keys: list) -> dict:
    sid = s.get("sequence_id")
    in_seq = [c for c in cuts if c.get("sequence_id") == sid]
    roles = [c.get("role") for c in in_seq if c.get("role")]
    assets = sorted({a for c in in_seq for a in (c.get("brand_assets") or [])})
    key = _match_key_scene(keys, s.get("start_sec"), s.get("end_sec"))
    return {
        "sequence_id": sid,
        "start_sec": s.get("start_sec"),
        "end_sec": s.get("end_sec"),
        "role": roles[0] if roles else None,
        "role_evidence": None,
        "has_problem_element": "PROBLEM" in roles,
        "has_experience_element": "EXPERIENCE" in roles,
        "sequence_label": s.get("sequence_label"),
        "intent": s.get("intent"),
        "num_cuts": s.get("num_cuts", len(in_seq)),
        "delivery": s.get("delivery"),
        "brand_visible": bool(s.get("brand_visible")),
        "product_visible": bool(s.get("product_visible")),
        "product_focus_level": "primary" if s.get("product_visible") else None,
        "brand_assets": assets,
        "viewable_without_audio": any(c.get("text") for c in in_seq),
        "legible_at_3m": False,
        "key_visual": key is not None,
        "key_scene_location": (key or {}).get("location"),
        "key_scene_subject": (key or {}).get("subject"),
        "key_scene_describe": (key or {}).get("key_scene_describe") or (key or {}).get("description"),
        "sort_order": idx,
    }


def _match_key_scene(keys: list, start: float | None, end: float | None) -> dict | None:
    if start is None or end is None:
        return None
    for k in keys:
        ks, ke = k.get("start_sec"), k.get("end_sec")
        if ks is not None and ke is not None and ks >= start and ke <= end:
            return k
    return None


def _build_cuts(parsed: dict, sources: dict) -> list:
    cuts = parsed.get("cuts") or []
    ca = _index_by_cut(sources.get("cut_analysis"))
    sa = _index_by_cut(sources.get("scene_analysis"))
    stt = sources.get("stt") or []
    return [_one_cut(c, i, ca, sa, stt) for i, c in enumerate(cuts)]


def _index_by_cut(items) -> dict:
    if not isinstance(items, list):
        return {}
    out: dict = {}
    for x in items:
        if isinstance(x, dict) and "cut_index" in x:
            out[x["cut_index"]] = x
    return out


def _one_cut(c: dict, idx: int, ca: dict, sa: dict, stt: list) -> dict:
    cid = c.get("cut_id")
    cut_an = ca.get(cid, {})
    scene_an = sa.get(cid, {})
    narr_fallback = _narration_for(stt, c.get("start_sec"), c.get("end_sec"))
    return {
        "sequence_id": c.get("sequence_id"),
        "cut_num": cid,
        "start_sec": c.get("start_sec"),
        "end_sec": c.get("end_sec"),
        "narrative_role": c.get("role"),
        "plot": c.get("plot"),
        "scene": _scene_desc(scene_an),
        "action": cut_an.get("flow"),
        "character": cut_an.get("cast"),
        "camera": scene_an.get("camera"),
        "audio": {"narration": c.get("narration") or narr_fallback, "sfx": None, "bgm": None},
        "narration": c.get("narration") or narr_fallback,
        "text_content": c.get("text") or cut_an.get("text_flow"),
        "brand_assets": ",".join(c.get("brand_assets") or []),
        "brand_visible": bool(c.get("brand_visible")),
        "product_visible": bool(c.get("product_visible")),
        "sort_order": idx,
    }


def _scene_desc(scene_an: dict) -> str | None:
    parts = [v for k in ("foreground", "background", "mood") if (v := scene_an.get(k))]
    return " / ".join(parts) if parts else None


def _narration_for(stt: list, start: float | None, end: float | None) -> str | None:
    if start is None or end is None:
        return None
    chunks = [s.get("text", "") for s in stt if start <= s.get("start_sec", -1) < end]
    return " ".join(chunks).strip() or None


def _build_key_scenes(parsed: dict) -> list:
    return [
        {
            "start_sec": k.get("start_sec"),
            "end_sec": k.get("end_sec"),
            "location": k.get("location"),
            "subject": k.get("subject"),
            "description": k.get("key_scene_describe") or k.get("description"),
        }
        for k in (parsed.get("key_scenes") or [])
    ]


def _lookup_filename(video_id: int) -> str:
    from pipeline.video_loader import get_video_info
    path, _meta = get_video_info(video_id)
    return Path(path).name


def _iter_video_dirs(root: Path, filename: str) -> list[Path]:
    return sorted(d for d in root.iterdir() if d.is_dir() and (d / filename).exists())


def _process_parsed(video_dir: Path, out_dir: Path) -> None:
    try:
        video_id = int(video_dir.name)
    except ValueError:
        print(f"      건너뜀(폴더명이 정수 아님): {video_dir.name}")
        return
    try:
        video_filename = _lookup_filename(video_id)
    except Exception as e:
        print(f"      [{video_id}] 영상 파일명 조회 실패 ({e}) — 빈 문자열로 진행")
        video_filename = ""
    sources = load_sources(video_dir)
    payload = convert(sources, video_filename, video_id)
    out_path = out_dir / f"{video_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      [{video_id}] saved → {out_path}")


def _process_brief(video_dir: Path, out_dir: Path) -> None:
    try:
        video_id = int(video_dir.name)
    except ValueError:
        print(f"      건너뜀(폴더명이 정수 아님): {video_dir.name}")
        return
    brief_path = video_dir / "brief_analysis.json"
    payload = json.loads(brief_path.read_text(encoding="utf-8"))
    out_path = out_dir / f"{video_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      [{video_id}] saved → {out_path}")


def main() -> None:
    args = _build_parser().parse_args()
    if not args.video_dir.is_dir():
        raise SystemExit(f"오류: --video_dir 가 디렉토리가 아님: {args.video_dir}")

    source_file = "parsed_analysis.json" if args.mode == "parsed" else "brief_analysis.json"
    targets = _iter_video_dirs(args.video_dir, source_file)
    if not targets:
        raise SystemExit(f"오류: {source_file} 을 포함한 하위 폴더 없음: {args.video_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    process_fn = _process_parsed if args.mode == "parsed" else _process_brief
    print(f"변환 대상: {len(targets)}개  (mode={args.mode})")
    for i, vdir in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {vdir.name}")
        try:
            process_fn(vdir, args.out_dir)
        except Exception as e:
            print(f"      실패: {e}")
    print(f"\n완료 → {args.out_dir}")


if __name__ == "__main__":
    main()
