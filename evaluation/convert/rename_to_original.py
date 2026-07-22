"""<video_id>.json 결과 파일을 DB 의 original_filename 으로 재명명해 저장한다.

convert_v2 등이 만든 `<id>.json` 묶음을 시각적으로 식별 가능한 원본 영상 파일명
(예: '휴온스 메노락토_4년 연속 ... 만나보세요!.json')으로 복사한다.
이름 충돌 / Windows 금지문자는 살균하며, DB 는 IN 쿼리 1회로 일괄 조회한다.
"""
import argparse
import re
import shutil
from pathlib import Path

from db.connection import get_connection

_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="<id>.json → <original_filename>.json 재명명")
    p.add_argument("--video_dir", type=Path, required=True, help="`<id>.json` 파일이 들어있는 입력 디렉토리")
    p.add_argument("--out_dir", type=Path, required=True, help="재명명된 JSON 을 저장할 디렉토리")
    return p


def _collect_video_ids(video_dir: Path) -> dict[int, Path]:
    """디렉토리에서 정수 stem 을 가진 .json 파일들을 {video_id: 경로} 로 모은다."""
    out: dict[int, Path] = {}
    for path in sorted(video_dir.glob("*.json")):
        try:
            out[int(path.stem)] = path
        except ValueError:
            print(f"      건너뜀(파일명이 정수 아님): {path.name}")
    return out


def fetch_original_filenames(video_ids: list[int]) -> dict[int, str]:
    """video_uploads.id IN (...) 1회 호출로 {id: original_filename} 매핑을 만든다."""
    if not video_ids:
        return {}
    placeholders = ",".join(["%s"] * len(video_ids))
    sql = f"SELECT id, original_filename FROM video_uploads WHERE id IN ({placeholders})"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(video_ids))
        return {row[0]: row[1] for row in cursor.fetchall()}


def sanitize_filename(name: str) -> str:
    """Windows 금지문자(`<>:"/\\|?*`)와 제어문자를 `_` 로 치환하고 trailing dot/space 를 제거한다."""
    cleaned = _FORBIDDEN_RE.sub("_", name).rstrip(". ")
    return cleaned or "_"


def _target_name(original_filename: str) -> str:
    """원본 파일명에서 확장자를 떼고 `.json` 을 붙여 안전한 출력 파일명을 만든다."""
    stem = Path(original_filename).stem
    return f"{sanitize_filename(stem)}.json"


def _copy_one(video_id: int, src: Path, original: str, out_dir: Path, used: set[str]) -> None:
    target = _target_name(original)
    if target in used:
        target = f"{Path(target).stem}__{video_id}.json"
        print(f"      [{video_id}] 이름 충돌 → 접미사 부여: {target}")
    used.add(target)
    dst = out_dir / target
    shutil.copyfile(src, dst)
    print(f"      [{video_id}] {src.name} → {dst.name}")


def rename_all(video_dir: Path, out_dir: Path) -> None:
    """입력 디렉토리의 `<id>.json` 들을 DB original_filename 기반으로 복사한다."""
    src_map = _collect_video_ids(video_dir)
    if not src_map:
        raise SystemExit(f"오류: <id>.json 파일이 없음: {video_dir}")
    names = fetch_original_filenames(list(src_map))
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"대상: {len(src_map)}개  / DB 매칭: {len(names)}개")
    used: set[str] = set()
    for i, (vid, src) in enumerate(src_map.items(), 1):
        print(f"[{i}/{len(src_map)}] video_id={vid}")
        original = names.get(vid)
        if not original:
            print(f"      [{vid}] DB 매칭 없음 — 건너뜀")
            continue
        try:
            _copy_one(vid, src, original, out_dir, used)
        except OSError as e:
            print(f"      [{vid}] 복사 실패: {e}")
    print(f"\n완료 → {out_dir}")


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if not args.video_dir.is_dir():
        raise SystemExit(f"오류: --video_dir 가 디렉토리가 아님: {args.video_dir}")
    rename_all(args.video_dir, args.out_dir)


if __name__ == "__main__":
    main()
