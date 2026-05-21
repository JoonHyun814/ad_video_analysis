from pathlib import Path

from db.connection import get_connection
from utils.env_loader import load_env

_DIR_ENV_PATH = Path(__file__).parent.parent / "env" / "dir.env"


def get_video_info(video_id: int) -> tuple[Path, dict]:
    """DB에서 video_id에 해당하는 행을 조회하고 (절대경로, 행 딕셔너리)를 반환한다."""
    row = _fetch_row(video_id)
    video_path = _resolve_path(row["file_path"])
    if not video_path.exists():
        raise FileNotFoundError(f"영상 파일 없음: {video_path}")
    return video_path, row


def _fetch_row(video_id: int) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM video_uploads WHERE id = %s", (video_id,))
        row = cursor.fetchone()
    if row is None:
        raise ValueError(f"video_id={video_id} 를 찾을 수 없습니다.")
    return row


def _resolve_path(file_path: str) -> Path:
    env = load_env(_DIR_ENV_PATH)
    root = Path(env["ROOT_VIDEO_DIR"])
    normalized = file_path.replace("\\", "/")
    return root / normalized
