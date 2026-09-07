"""주어진 runid 목록에 대해 스토리보드 이미지, 사용된 프롬프트, 영상 결과물을
runid별 폴더로 다운로드한다.

출력 구조:
  exports/<runid>/
    images/sb{storyboardid}_concept{conceptindex}_scene{no}.png
    videos/video{id}.mp4
    videos/video{id}_original.mp4        (originalvideourl이 videourl과 다를 때만)
    videos/video{id}_caption.mp4         (captionvideourl이 있을 때만)
    videos/video{id}_narration.mp4       (narrationvideourl이 있을 때만)
    prompts/video{id}_prompt.txt
    metadata.json

사용 예:
  python scripts/export_run_assets.py v5s5a256db73b76 v5s52f3602c18a1
  python scripts/export_run_assets.py --file runids.txt --out-dir exports
  python scripts/export_run_assets.py --file runs.json    # list_recent_runs.py --save 결과 그대로 사용
  python scripts/export_run_assets.py --file runs.csv
  python scripts/export_run_assets.py v5s5a256db73b76 --overwrite

--file 은 list_recent_runs.py --save 로 만든 .json/.csv 파일이거나, runid를 한 줄에
하나씩 담은 일반 텍스트 파일(.txt 등)을 그대로 받을 수 있다. 형식은 확장자로 판단한다.

--file로 목록을 넘기면 v5videos에 영상 결과가 없는 runid는 기본적으로 건너뛴다
(직접 지정한 runid에도 같은 동작을 적용하려면 --skip-no-video 를 추가).
"""
import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from db_config import get_connection

URL_RE = re.compile(r"https?://\S+")


def parse_args():
    p = argparse.ArgumentParser(description="runid별 이미지/프롬프트/영상 추출")
    p.add_argument("runids", nargs="*", help="추출할 runid 목록")
    p.add_argument(
        "--file",
        help=(
            "runid 목록 파일. list_recent_runs.py --save 로 만든 .json/.csv 파일 "
            "또는 runid를 한 줄에 하나씩 담은 텍스트 파일(.txt 등)"
        ),
    )
    p.add_argument("--out-dir", default="exports", help="출력 루트 디렉토리 (기본: exports)")
    p.add_argument("--overwrite", action="store_true", help="이미 존재하는 파일도 다시 다운로드")
    p.add_argument(
        "--skip-no-video",
        action="store_true",
        help="영상 결과(v5videos)가 없는 runid는 건너뜀 (--file 사용 시 기본으로 켜짐)",
    )
    return p.parse_args()


def load_runids_from_file(path: str):
    p = Path(path)
    suffix = p.suffix.lower()
    text = p.read_text(encoding="utf-8-sig")

    if suffix == ".json":
        data = json.loads(text)
        runids = []
        for item in data:
            if isinstance(item, dict):
                if not item.get("runid"):
                    raise ValueError(f"JSON 항목에 'runid' 키가 없습니다: {item}")
                runids.append(item["runid"])
            else:
                runids.append(str(item))
        return runids

    if suffix == ".csv":
        reader = csv.DictReader(text.splitlines())
        if "runid" not in (reader.fieldnames or []):
            raise ValueError(f"CSV에 'runid' 컬럼이 없습니다: {reader.fieldnames}")
        return [row["runid"] for row in reader if row.get("runid")]

    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def load_runids(args):
    runids = list(args.runids)
    if args.file:
        runids += load_runids_from_file(args.file)
    seen = set()
    unique = []
    for r in runids:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


def download(url: str, dest: Path, overwrite: bool):
    if not url:
        return "skip(no-url)"
    if dest.exists() and not overwrite:
        return "skip(exists)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        return "ok"
    except urllib.error.URLError as e:
        return f"fail({e})"


def fetch_storyboards(cur, runids):
    fmt = ",".join(["%s"] * len(runids))
    cur.execute(
        f"SELECT id, runid, conceptindex, machinejson, regdt FROM v5storyboards "
        f"WHERE runid IN ({fmt}) ORDER BY runid, conceptindex, id",
        runids,
    )
    return cur.fetchall()


def fetch_videos(cur, runids):
    fmt = ",".join(["%s"] * len(runids))
    cur.execute(
        f"SELECT id, runid, storyboardid, prompt, videourl, originalvideourl, "
        f"narrationvideourl, captionvideourl, status, processstatus, regdt "
        f"FROM v5videos WHERE runid IN ({fmt}) ORDER BY runid, id",
        runids,
    )
    return cur.fetchall()


def extract_scene_images(storyboard_row):
    """machinejson의 m9.scenes[].sketchurl 을 (scene_no, url, brief) 리스트로 추출."""
    images = []
    try:
        data = json.loads(storyboard_row["machinejson"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return images
    scenes = (data.get("m9") or {}).get("scenes") or []
    for scene in scenes:
        url = scene.get("sketchurl")
        if url:
            images.append(
                {
                    "scene_no": scene.get("no"),
                    "url": url,
                    "brief": scene.get("brief"),
                }
            )
    return images


def process_run(cur, runid, videos, out_root: Path, overwrite: bool):
    run_dir = out_root / runid
    images_dir = run_dir / "images"
    videos_dir = run_dir / "videos"
    prompts_dir = run_dir / "prompts"

    storyboards = fetch_storyboards(cur, [runid])

    meta = {"runid": runid, "storyboards": [], "videos": []}

    for sb in storyboards:
        images = extract_scene_images(sb)
        sb_meta = {
            "storyboard_id": sb["id"],
            "conceptindex": sb["conceptindex"],
            "regdt": str(sb["regdt"]),
            "images": [],
        }
        for img in images:
            fname = f"sb{sb['id']}_concept{sb['conceptindex']}_scene{img['scene_no']}.png"
            dest = images_dir / fname
            result = download(img["url"], dest, overwrite)
            sb_meta["images"].append(
                {
                    "scene_no": img["scene_no"],
                    "brief": img["brief"],
                    "url": img["url"],
                    "file": str(dest.relative_to(out_root)),
                    "download": result,
                }
            )
            print(f"[{runid}] image sb{sb['id']} scene{img['scene_no']}: {result}")
        meta["storyboards"].append(sb_meta)

    for v in videos:
        vid = v["id"]

        prompt_path = prompts_dir / f"video{vid}_prompt.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(v["prompt"] or "", encoding="utf-8")

        video_targets = [("main", v["videourl"], f"video{vid}.mp4")]
        if v["originalvideourl"] and v["originalvideourl"] != v["videourl"]:
            video_targets.append(("original", v["originalvideourl"], f"video{vid}_original.mp4"))
        if v["narrationvideourl"]:
            video_targets.append(("narration", v["narrationvideourl"], f"video{vid}_narration.mp4"))
        if v["captionvideourl"]:
            video_targets.append(("caption", v["captionvideourl"], f"video{vid}_caption.mp4"))

        v_meta = {
            "video_id": vid,
            "storyboard_id": v["storyboardid"],
            "status": v["status"],
            "processstatus": v["processstatus"],
            "regdt": str(v["regdt"]),
            "prompt_file": str(prompt_path.relative_to(out_root)),
            "files": [],
        }
        for kind, url, fname in video_targets:
            dest = videos_dir / fname
            result = download(url, dest, overwrite)
            v_meta["files"].append(
                {"kind": kind, "url": url, "file": str(dest.relative_to(out_root)), "download": result}
            )
            print(f"[{runid}] video{vid} ({kind}): {result}")

        meta["videos"].append(v_meta)

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def main():
    args = parse_args()
    runids = load_runids(args)
    if not runids:
        print("runid를 하나 이상 지정하세요 (인자 또는 --file).", file=sys.stderr)
        sys.exit(1)

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    # --file로 목록을 받은 경우 영상 결과 없는 runid는 기본적으로 건너뛴다.
    skip_no_video = args.skip_no_video or bool(args.file)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for runid in runids:
                videos = fetch_videos(cur, [runid])
                if skip_no_video and not videos:
                    print(f"[{runid}] 영상 결과 없음 - pass")
                    continue
                print(f"=== {runid} 처리 시작 ===")
                process_run(cur, runid, videos, out_root, args.overwrite)
    finally:
        conn.close()

    print(f"\n완료. 출력 위치: {out_root.resolve()}")


if __name__ == "__main__":
    main()
