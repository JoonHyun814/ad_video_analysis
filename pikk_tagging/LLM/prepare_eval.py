"""SQL 덤프에서 도메인별 레이블당 영상 1개를 추출해 VL 평가 계획을 생성.

1. stills_pikk.sql 파싱 → 레이블별 youtube_id 결정
2. 영상 다운로드 (yt-dlp, skip_download 로 생략 가능)
3. video_gt_tags.json + eval_plan.json 생성

python -m pikk_tagging.LLM.prepare_eval
python -m pikk_tagging.LLM.prepare_eval --sql path/to/stills_pikk.sql --skip_download
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# ── 레이블 → 픽 태그 매핑 ─────────────────────────────────────────────────────
# (domain, vl_label): (canonical_tag_id, pikk_tag_name)
_TAG_MAP: dict[tuple[str, str], tuple[int, str]] = {
    ("angle",     "탑뷰"):           (110,   "탑뷰/버드아이뷰"),
    ("angle",     "드론샷"):          (3196,  "드론 샷"),
    ("angle",     "로우앵글"):        (9,     "로우 앵글"),
    ("angle",     "아이레벨"):        (425,   "아이 레벨 샷"),
    ("angle",     "하이앵글"):        (412,   "하이 앵글"),
    ("angle",     "더치앵글"):        (12935, "더치 앵글"),
    ("shot_size", "익스트림클로즈업"): (31,   "익스트림 클로즈업"),
    ("shot_size", "클로즈업"):        (40,   "클로즈업"),
    ("shot_size", "미디엄클로즈업"):   (553,  "미디엄 클로즈업"),
    ("shot_size", "미디엄샷"):        (49,   "미디엄 샷"),
    ("shot_size", "롱샷"):            (11249,"와이드 롱샷"),
    ("shot_size", "와이드샷"):        (41,   "와이드 샷"),
    ("shot_size", "풀샷"):            (497,  "풀 샷"),
    ("lighting",  "역광"):            (486,  "역광"),
    ("lighting",  "실루엣"):          (7,    "실루엣"),
    ("lighting",  "로우키"):          (42,   "로우키 조명"),
    ("lighting",  "하이키"):          (587,  "하이키 조명"),
    ("lighting",  "흑백"):            (2248, "흑백 전환"),
    ("lighting",  "레트로"):          (57,   "#레트로"),
    ("focus",     "아웃포커스"):       (113,  "얕은 심도 (아웃포커스)"),
    ("focus",     "딥포커스"):        (33,   "깊은 심도"),
    ("focus",     "랙포커스"):        (25078,"랙 포커스 (Rack Focus)"),
    ("focus",     "소프트포커스"):     (264,  "소프트 포커스"),
    ("focus",     "팬포커스"):        (1009, "딥 포커스"),
}

_SQL_DEFAULT  = Path(r"C:\Users\llm\workspace\outputs\stills_pikk.sql")
_OUT_DEFAULT  = Path(r"C:\Users\llm\workspace\outputs\pikk_output\LLM\qwen_vl")
_VID_DEFAULT  = Path(r"C:\Users\llm\workspace\outputs\pikk_output\videos")

_SCENE_TAG_RE = re.compile(r"^\s*\((\d+),\s*(\d+),\s*\d+\)")
_SCENE_ROW_RE = re.compile(r"^\s*\((\d+),\s*'([^'\\]*(?:\\.[^'\\]*)*)'")
# groups: (id, name, canonical_id_or_NULL)
_TAG_ROW_RE   = re.compile(
    r"^\s*\((\d+),\s*'(?:mood|visual)',\s*'((?:\\.|[^'\\])*)',\s*'(?:\\.|[^'\\])*',"
    r"\s*'(?:\\.|[^'\\])*',\s*(NULL|\d+),\s*\d+\)"
)


def _parse_sql(
    sql_path: Path,
) -> tuple[dict[int, str], dict[int, list[int]], dict[int, set[int]], dict[int, str]]:
    """SQL 덤프 1회 파싱. (scene_video, tag_scenes, canonical_variants, tag_id_to_name) 반환."""
    scene_video:        dict[int, str]       = {}
    tag_scenes:         dict[int, list[int]] = defaultdict(list)
    canonical_variants: dict[int, set[int]]  = defaultdict(set)
    tag_id_to_name:     dict[int, str]       = {}

    in_table = ""
    with sql_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("INSERT INTO `"):
                in_table = line.split("`")[1]
                continue

            if in_table == "scenes":
                m = _SCENE_ROW_RE.match(line)
                if m:
                    scene_video[int(m.group(1))] = m.group(2)

            elif in_table == "scene_tags":
                m = _SCENE_TAG_RE.match(line)
                if m:
                    tag_scenes[int(m.group(2))].append(int(m.group(1)))

            elif in_table == "tags":
                m = _TAG_ROW_RE.match(line)
                if m:
                    tag_id    = int(m.group(1))
                    name      = m.group(2).replace("\\'", "'")
                    raw_canon = m.group(3)
                    canon_id  = tag_id if raw_canon == "NULL" else int(raw_canon)
                    tag_id_to_name[tag_id] = name
                    if canon_id != tag_id:
                        canonical_variants[canon_id].add(tag_id)

    return scene_video, tag_scenes, canonical_variants, tag_id_to_name


def _find_videos(
    scene_video: dict[int, str],
    tag_scenes: dict[int, list[int]],
    canonical_variants: dict[int, set[int]],
) -> dict[tuple[str, str], str | None]:
    """레이블별 youtube_id 결정. 중복 없이 1개씩 할당."""
    used_vids: set[str] = set()
    result: dict[tuple[str, str], str | None] = {}

    for (domain, label), (canon_id, _) in _TAG_MAP.items():
        all_ids = {canon_id} | canonical_variants.get(canon_id, set())
        found: str | None = None
        for tid in sorted(all_ids, key=lambda x: -len(tag_scenes.get(x, []))):
            for scene_id in tag_scenes.get(tid, []):
                vid = scene_video.get(scene_id)
                if vid and vid not in used_vids:
                    found = vid
                    break
            if found:
                break
        if found:
            used_vids.add(found)
        result[(domain, label)] = found
    return result


def _download_video(youtube_id: str, video_dir: Path, cookies: Path | None) -> Path | None:
    """yt-dlp 로 영상 1개 다운로드. 성공 시 파일 경로 반환."""
    try:
        import yt_dlp
    except ImportError:
        print("  yt-dlp 없음 (pip install yt-dlp)")
        return None

    vid_dir = video_dir / youtube_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("mp4", "webm", "mkv"):
        existing = list(vid_dir.glob(f"*.{ext}"))
        if existing:
            return existing[0]

    opts: dict = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "outtmpl": str(vid_dir / f"{youtube_id}.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True, "no_warnings": True,
    }
    if cookies:
        opts["cookiefile"] = str(cookies)

    url = f"https://www.youtube.com/watch?v={youtube_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        for ext in ("mp4", "webm", "mkv"):
            found = list(vid_dir.glob(f"*.{ext}"))
            if found:
                return found[0]
    except Exception as e:
        print(f"  다운로드 실패 [{youtube_id}]: {e}")
    return None


def _all_video_tags(
    youtube_ids: list[str],
    scene_video: dict[int, str],
    tag_scenes: dict[int, list[int]],
    canonical_variants: dict[int, set[int]],
    tag_id_to_name: dict[int, str],
) -> dict[str, dict]:
    """SQL 파싱 결과에서 각 영상의 전체 GT 태그(도메인 무관)를 반환."""
    # variant_id → canonical_id
    variant_to_canon: dict[int, int] = {
        v_id: canon_id
        for canon_id, variants in canonical_variants.items()
        for v_id in variants
    }

    # canonical_id → domain (4개 도메인 분류용)
    canon_to_domain: dict[int, str] = {}
    for (domain, _label), (canon_id, _) in _TAG_MAP.items():
        canon_to_domain[canon_id] = domain
        for v_id in canonical_variants.get(canon_id, set()):
            canon_to_domain[v_id] = domain

    # scene_id → set[tag_id]
    scene_to_tags: dict[int, set[int]] = defaultdict(set)
    for tag_id, scenes in tag_scenes.items():
        for scene_id in scenes:
            scene_to_tags[scene_id].add(tag_id)

    # youtube_id → [scene_ids]
    video_scenes: dict[str, list[int]] = defaultdict(list)
    for scene_id, vid in scene_video.items():
        video_scenes[vid].append(scene_id)

    result: dict[str, dict] = {}
    for yt_id in youtube_ids:
        all_tag_ids: set[int] = set()
        for scene_id in video_scenes.get(yt_id, []):
            all_tag_ids.update(scene_to_tags.get(scene_id, set()))

        domain_tags: dict[str, list[str]] = {"angle": [], "shot_size": [], "lighting": [], "focus": []}
        all_tags: list[str] = []
        seen_names: set[str] = set()

        for tid in all_tag_ids:
            canon = variant_to_canon.get(tid, tid)
            name  = tag_id_to_name.get(canon) or tag_id_to_name.get(tid, "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            all_tags.append(name)
            dom = canon_to_domain.get(canon) or canon_to_domain.get(tid)
            if dom:
                domain_tags[dom].append(name)

        result[yt_id] = {
            "all_tags":       all_tags,
            "angle_tags":     domain_tags["angle"],
            "shot_size_tags": domain_tags["shot_size"],
            "lighting_tags":  domain_tags["lighting"],
            "focus_tags":     domain_tags["focus"],
        }
    return result


def _write_outputs(
    label_video: dict[tuple[str, str], str | None],
    vid_paths: dict[str, Path | None],
    out_dir: Path,
    scene_video: dict[int, str],
    tag_scenes: dict[int, list[int]],
    canonical_variants: dict[int, set[int]],
    tag_id_to_name: dict[int, str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # video_gt_tags.json — 영상별 전체 태그(도메인 무관) 조회
    unique_vids = [v for v in dict.fromkeys(v for v in label_video.values() if v)]
    gt = _all_video_tags(unique_vids, scene_video, tag_scenes, canonical_variants, tag_id_to_name)

    gt_path = out_dir / "video_gt_tags.json"
    gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"GT 태그: {gt_path}")

    # eval_plan.json
    videos: dict[str, dict] = {}
    for (domain, label), youtube_id in label_video.items():
        if not youtube_id:
            continue
        if youtube_id not in videos:
            videos[youtube_id] = {
                "youtube_id": youtube_id,
                "video_path": str(vid_paths.get(youtube_id)) if vid_paths.get(youtube_id) else None,
                "labels": [],
            }
        videos[youtube_id]["labels"].append({"domain": domain, "vl_label": label, "pikk_tag": _TAG_MAP[(domain, label)][1]})

    plan = {"videos": list(videos.values()), "missing_labels": [
        {"domain": d, "vl_label": l} for (d, l), v in label_video.items() if not v
    ]}
    plan_path = out_dir / "eval_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"평가 계획: {plan_path}  ({len(videos)}개 영상, {sum(1 for v in label_video.values() if not v)}개 레이블 미매칭)")


def main() -> None:
    p = argparse.ArgumentParser(description="pikk DB에서 레이블별 대표 영상 추출 + VL 평가 계획 생성")
    p.add_argument("--sql",           default=str(_SQL_DEFAULT), help="stills_pikk.sql 경로")
    p.add_argument("--out_dir",       default=str(_OUT_DEFAULT), help="결과 저장 루트")
    p.add_argument("--video_dir",     default=str(_VID_DEFAULT), help="영상 다운로드/검색 루트")
    p.add_argument("--skip_download", action="store_true",       help="다운로드 생략")
    p.add_argument("--cookies",       default=None,              help="yt-dlp 쿠키 파일 경로")
    args = p.parse_args()

    sql_path   = Path(args.sql)
    out_dir    = Path(args.out_dir)
    video_dir  = Path(args.video_dir)
    cookies    = Path(args.cookies) if args.cookies else None

    if not sql_path.exists():
        sys.exit(f"SQL 덤프 없음: {sql_path}")

    print(f"SQL 파싱 중: {sql_path}  ({sql_path.stat().st_size // 1024 // 1024}MB)")
    scene_video, tag_scenes, canonical_variants, tag_id_to_name = _parse_sql(sql_path)
    print(f"  씬 수: {len(scene_video):,}  태그-씬 연결: {sum(len(v) for v in tag_scenes.values()):,}")

    label_video = _find_videos(scene_video, tag_scenes, canonical_variants)
    found  = sum(1 for v in label_video.values() if v)
    missed = sum(1 for v in label_video.values() if not v)
    print(f"\n레이블 매칭: {found}개 성공  {missed}개 미매칭")
    for (d, l), vid in label_video.items():
        status = vid or "❌ 없음"
        print(f"  [{d}] {l:20s} → {status}")

    vid_paths: dict[str, Path | None] = {}
    unique_vids = [v for v in dict.fromkeys(v for v in label_video.values() if v)]
    if not args.skip_download:
        print(f"\n영상 다운로드: {len(unique_vids)}개")
        for i, youtube_id in enumerate(unique_vids, 1):
            print(f"  [{i}/{len(unique_vids)}] {youtube_id}", end=" ", flush=True)
            path = _download_video(youtube_id, video_dir, cookies)
            vid_paths[youtube_id] = path
            print("OK" if path else "FAIL")
    else:
        print("\n다운로드 생략 - 기존 파일 탐색")
        for youtube_id in unique_vids:
            for ext in ("mp4", "webm", "mkv"):
                found_files = list((video_dir / youtube_id).glob(f"*.{ext}"))
                if found_files:
                    vid_paths[youtube_id] = found_files[0]
                    break
            else:
                vid_paths[youtube_id] = None

    _write_outputs(label_video, vid_paths, out_dir, scene_video, tag_scenes, canonical_variants, tag_id_to_name)


if __name__ == "__main__":
    main()
