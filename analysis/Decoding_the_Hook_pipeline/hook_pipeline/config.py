"""경로·상수 설정. 영상 조회는 기존 ad_video_analysis 프로젝트의 DB/env 를 그대로 재사용한다."""
import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT / "output"

# 상위 프로젝트(db/, pipeline/video_loader.py, env/*.env) 위치. 필요하면 환경변수로 덮어쓴다.
LEGACY_PROJECT_ROOT = Path(os.environ.get("LEGACY_PROJECT_ROOT", PACKAGE_ROOT.parent)).resolve()

HOOK_SEC = 3.0  # 논문의 hooking period: 첫 3초
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # BERTopic 기본 영어 임베딩 모델 (rationale 이 영어로 생성됨)


def ensure_legacy_on_path() -> None:
    """기존 프로젝트 모듈(pipeline.video_loader, utils.json_utils)을 import 할 수 있게 한다."""
    if not LEGACY_PROJECT_ROOT.exists():
        raise FileNotFoundError(f"기존 프로젝트 경로 없음: {LEGACY_PROJECT_ROOT} (LEGACY_PROJECT_ROOT 로 지정)")
    root = str(LEGACY_PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
