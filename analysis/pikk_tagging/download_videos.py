"""Download YouTube videos listed in a pikk_video_catalog CSV via yt-dlp."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def _ydl_opts(
    video_dir: Path,
    cookies: Path | None,
    cookies_from_browser: str | None,
    js_runtimes: list[str] | None,
    remote_components: list[str] | None,
) -> dict:
    opts: dict = {
        "format": "best[ext=mp4]/best",  # single-stream: no ffmpeg merge needed
        "outtmpl": str(video_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    if cookies:
        opts["cookiefile"] = str(cookies)
    elif cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if js_runtimes:
        opts["js_runtimes"] = {r: {} for r in js_runtimes}
    if remote_components:
        opts["remote_components"] = set(remote_components)
    return opts


def _already_downloaded(video_dir: Path) -> Path | None:
    """Return the existing video file path, or None."""
    for ext in ("mp4", "webm", "mkv"):
        found = list(video_dir.glob(f"*.{ext}"))
        if found:
            return found[0]
    return None


def download_one(
    youtube_id: str,
    youtube_url: str,
    out_dir: Path,
    cookies: Path | None,
    cookies_from_browser: str | None,
    js_runtimes: list[str] | None,
    remote_components: list[str] | None,
) -> dict:
    """Download a single video; return status dict with youtube_id, status, path/error."""
    import yt_dlp

    video_dir = out_dir / youtube_id
    video_dir.mkdir(parents=True, exist_ok=True)

    existing = _already_downloaded(video_dir)
    if existing:
        return {"youtube_id": youtube_id, "status": "skipped", "path": str(existing)}

    try:
        with yt_dlp.YoutubeDL(_ydl_opts(video_dir, cookies, cookies_from_browser, js_runtimes, remote_components)) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            if info:
                _write_info(video_dir, info)
        downloaded = _already_downloaded(video_dir)
        return {"youtube_id": youtube_id, "status": "ok", "path": str(downloaded) if downloaded else None}
    except Exception as exc:
        return {"youtube_id": youtube_id, "status": "error", "error": str(exc)}


def _write_info(video_dir: Path, info: dict) -> None:
    summary = {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
    }
    (video_dir / "video_info.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_catalog(csv_path: Path, limit: int | None) -> list[dict]:
    """Read pikk_video_catalog CSV; optionally cap at limit rows."""
    with csv_path.open("r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return rows[:limit] if limit else rows


def download_catalog(
    csv_path: Path,
    out_dir: Path,
    *,
    limit: int | None = None,
    workers: int = 4,
    cookies: Path | None = None,
    cookies_from_browser: str | None = None,
    js_runtimes: list[str] | None = None,
    remote_components: list[str] | None = None,
) -> list[dict]:
    """Download all videos from a pikk_video_catalog CSV; return per-video status list."""
    rows = _load_catalog(csv_path, limit)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                download_one, row["youtube_id"], row["youtube_url"],
                out_dir, cookies, cookies_from_browser, js_runtimes, remote_components,
            ): row["youtube_id"]
            for row in rows
        }
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            icon = {"ok": "OK", "skipped": "--", "error": "ERR"}.get(result["status"], "?")
            _log(f"[{i:>5}/{total}] {icon} {result['youtube_id']}  ({result['status']})")

    return results


def _log(msg: str) -> None:
    """Print with utf-8 encoding guard for Windows terminals."""
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


def _print_summary(results: list[dict]) -> None:
    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = [r for r in results if r["status"] == "error"]
    _log(f"\n[done] download={ok}  skipped={skipped}  error={len(errors)}")
    for err in errors:
        _log(f"  ERR [{err['youtube_id']}]: {err['error']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download YouTube videos from pikk_video_catalog CSV")
    parser.add_argument("--catalog", type=Path, default=Path("output/pikk_output/pikk_video_catalog.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("output/pikk_output"))
    parser.add_argument("--limit", type=int, default=None, metavar="N", help="max videos to download (for testing)")
    parser.add_argument("--workers", type=int, default=4, metavar="N", help="parallel download threads")
    parser.add_argument("--cookies", type=Path, default=None, metavar="FILE",
                        help="Netscape cookies.txt file for YouTube auth")
    parser.add_argument("--cookies-from-browser", dest="cookies_from_browser", metavar="BROWSER", default=None,
                        help="read cookies from browser profile (chrome|edge|firefox); browser must be closed")
    parser.add_argument("--js-runtimes", dest="js_runtimes", nargs="+", metavar="RUNTIME", default=None,
                        help="JS runtimes for n-challenge solving, e.g. deno")
    parser.add_argument("--remote-components", dest="remote_components", nargs="+", metavar="SPEC", default=None,
                        help="remote component specs for EJS challenge solver, e.g. ejs:npm")
    args = parser.parse_args()

    results = download_catalog(
        args.catalog, args.out_dir,
        limit=args.limit, workers=args.workers,
        cookies=args.cookies, cookies_from_browser=args.cookies_from_browser,
        js_runtimes=args.js_runtimes, remote_components=args.remote_components,
    )
    _print_summary(results)


if __name__ == "__main__":
    main()
