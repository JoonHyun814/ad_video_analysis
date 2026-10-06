"""URL에서 영상을 다운로드해 로컬 파일로 저장.

download_videos.py 와 동일한 yt-dlp 옵션 구조(쿠키·JS 런타임·원격 컴포넌트)를 사용한다.
직접 HTTP(S) 링크는 urllib 로 처리한다.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_YOUTUBE_DOMAINS = frozenset({
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
})


def is_youtube_url(url: str) -> bool:
    return urlparse(url).netloc.lower() in _YOUTUBE_DOMAINS


def _video_id_from_youtube(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    seg = parsed.path.strip("/").split("/")[-1]
    return seg or "video"


def _find_video_file(directory: Path) -> Path | None:
    for ext in ("mp4", "webm", "mkv"):
        hits = list(directory.glob(f"*.{ext}"))
        if hits:
            return hits[0]
    return None


def _ydl_opts(
    out_dir: Path,
    cookies: Path | None,
    cookies_from_browser: str | None,
    js_runtimes: list[str] | None,
    remote_components: list[str] | None,
) -> dict:
    """download_videos.py 와 동일한 yt-dlp 옵션 딕셔너리 생성."""
    opts: dict = {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
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


def download_youtube(
    url: str,
    out_dir: Path,
    cookies: Path | None = None,
    cookies_from_browser: str | None = None,
    js_runtimes: list[str] | None = None,
    remote_components: list[str] | None = None,
) -> Path:
    """yt-dlp로 YouTube 영상 다운로드 → 파일 경로 반환."""
    try:
        import yt_dlp
    except ImportError:
        raise SystemExit("pip install yt-dlp")

    opts = _ydl_opts(out_dir, cookies, cookies_from_browser, js_runtimes, remote_components)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)

    found = _find_video_file(out_dir)
    if found is None:
        raise RuntimeError(f"다운로드 후 파일을 찾지 못했습니다: {out_dir}")
    return found


def download_direct(url: str, out_path: Path) -> Path:
    """직접 HTTP(S) 다운로드 → 파일 경로 반환."""
    _log(f"다운로드: {url}")
    urllib.request.urlretrieve(url, out_path)
    return out_path


def download_video(
    url: str,
    out_dir: Path,
    cookies: Path | None = None,
    cookies_from_browser: str | None = None,
    js_runtimes: list[str] | None = None,
    remote_components: list[str] | None = None,
) -> Path:
    """URL → 로컬 영상 파일. out_dir 하위에 저장.

    이미 파일이 있으면 재다운로드 없이 기존 경로를 반환한다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if is_youtube_url(url):
        existing = _find_video_file(out_dir)
        if existing:
            _log(f"이미 존재: {existing}")
            return existing
        return download_youtube(
            url, out_dir, cookies, cookies_from_browser, js_runtimes, remote_components
        )

    filename = Path(urlparse(url).path).name or "video.mp4"
    out_path = out_dir / filename
    if out_path.exists():
        _log(f"이미 존재: {out_path}")
        return out_path
    return download_direct(url, out_path)


def video_id_from_url(url: str) -> str:
    """URL에서 영상 식별자 추출 (출력 폴더명에 사용)."""
    if is_youtube_url(url):
        return _video_id_from_youtube(url)
    seg = Path(urlparse(url).path).stem
    return seg or "video"


def _log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
