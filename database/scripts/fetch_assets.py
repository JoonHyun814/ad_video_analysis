"""매칭 유닛(prompt·스토리보드 이미지·영상)을 로컬 디렉토리로 내려받는다."""
from pathlib import Path
from typing import Any

from export_run_assets import download
from matching import MatchedUnit


def fetch_unit_assets(unit: MatchedUnit, assets_dir: Path, overwrite: bool = False) -> dict[str, Any]:
    """assets_dir/{prompts,images,videos} 에 원본을 저장하고 로컬 경로를 반환한다.

    영상 다운로드 실패 시 이후 단계(scenario 생성)를 진행할 수 없으므로 즉시 예외를 던진다.
    """
    prompt_path = _save_prompt(unit, assets_dir / "prompts")
    video_path, video_status = _download_video(unit, assets_dir / "videos", overwrite)
    if not video_path.exists():
        raise RuntimeError(f"영상 다운로드 실패: {unit.video_url} ({video_status})")

    images = _download_images(unit, assets_dir / "images", overwrite)

    return {
        "prompt_path": prompt_path,
        "video_path": video_path,
        "video_download": video_status,
        "images": images,
    }


def _save_prompt(unit: MatchedUnit, prompts_dir: Path) -> Path:
    prompt_path = prompts_dir / f"video{unit.video_id}_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(unit.prompt or "", encoding="utf-8")
    return prompt_path


def _download_video(unit: MatchedUnit, videos_dir: Path, overwrite: bool) -> tuple[Path, str]:
    video_path = videos_dir / f"video{unit.video_id}.mp4"
    status = download(unit.video_url, video_path, overwrite)
    return video_path, status


def _download_images(unit: MatchedUnit, images_dir: Path, overwrite: bool) -> list[dict]:
    results = []
    for scene in unit.scenes:
        dest = images_dir / f"scene{scene.get('no')}.png"
        status = download(scene["sketchurl"], dest, overwrite)
        results.append({"scene_no": scene.get("no"), "file": dest, "download": status})
    return results
