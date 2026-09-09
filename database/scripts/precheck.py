"""본 파이프라인(scenario 생성, 10~30분 소요) 실행 전 저비용 사전 검증.

후반 합성(v5postwork)이 QA 테스트 등으로 오염돼 있으면 captionvideourl 이 스토리보드와 전혀
무관한 영상을 가리키는 경우가 있다(예: 원본은 15초 다트머신 광고인데 실제 파일은 27초 AI
서비스 데모 영상). duration 은 이 오매칭을 못 잡는다 — 플랫폼 영상 대부분이 15초 표준 규격이라
길이가 우연히 같기 때문이다. 대신 영상 프레임 여러 장 vs 스토리보드 이미지 여러 장을
claude -p 비전으로 빠르게 비교해 "같은 광고 캠페인인지"만 판정한다.

프레임 1장 vs 이미지 1장만 비교하면 안 된다 — 광고 안에서도 장면마다 구도가 크게 달라서
(예: 착장 장면 vs 제품 클로즈업) 같은 광고인데도 특정 두 순간만 비교하면 다른 광고로 오판된다.

반대로 "단 하나라도 일치하면 same_ad=true" 식으로 판단해도 안 된다 — 스토리보드 자체의
sketchurl 이미지 중 하나가 다른 프로젝트 이미지로 잘못 연결된 사례가 실제로 있었다(예:
지하철/보조배터리 스토리보드인데 참조 이미지 중 하나만 남성 스킨케어 제품 사진). 이런
경우 그 하나의 우연한 일치 때문에 진짜 오매칭 영상을 통과시키게 된다. 그래서 다수결로
판단한다 — 스토리보드 이미지 과반수와 무관한 영상이면 false.
"""
import subprocess
import sys
from pathlib import Path
from typing import Any

import cv2

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils.json_utils import parse_json  # noqa: E402

_SCHEMA = '{"same_ad": true, "reason": "판단 근거 한 문장"}'


def extract_sample_frames(video_path: Path, out_dir: Path, count: int = 3) -> list[Path]:
    """영상 전체 구간에 고르게 분포한 프레임 count장을 out_dir 에 저장하고 경로 리스트를 반환한다."""
    cap = cv2.VideoCapture(str(video_path))
    saved: list[Path] = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = (total_frames / fps) if fps else 0.0
        out_dir.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            t = duration * (i + 1) / (count + 1) if duration > 0 else float(i + 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * t))
            ret, frame = cap.read()
            if not ret:
                continue
            path = out_dir / f"_video_frame_{i + 1}.jpg"
            cv2.imwrite(str(path), frame)
            saved.append(path)
    finally:
        cap.release()
    return saved


def check_video_matches_storyboard(
    video_frames: list[Path], storyboard_images: list[Path], timeout: int = 120
) -> dict[str, Any]:
    """영상 프레임 여러 장과 스토리보드 이미지 여러 장이 같은 광고 캠페인인지 두 단계로 판정한다.

    1) 스토리보드 이미지 "과반수"가 가리키는 제품/업종을 먼저 정한다 — 이미지 1장만 다른
       프로젝트 사진으로 잘못 섞여 있어도(실측된 사례) 흔들리지 않도록 이상치 1장은 무시한다.
    2) 영상 프레임 "중 하나라도" 그 제품/업종과 일치하면 same_ad=true — 광고 안에서도 장면마다
       구도가 크게 달라(착장 장면 vs 제품 클로즈업) 프레임 1장만 안 맞는다고 곧바로 false로
       판정하면 진짜 정상 매칭까지 오탐지한다(실측으로 확인된 실패 모드).

    LLM 응답 파싱 실패 시 fail-open(same_ad 누락 → 상위에서 진행으로 간주)한다: 명백한 오매칭만
    저비용으로 거르는 것이 목적이지, 애매한 경우까지 차단하는 것이 아니다.
    """
    if not video_frames or not storyboard_images:
        return {}

    video_lines = "\n".join(f"- 영상 프레임 {i + 1}: {p}" for i, p in enumerate(video_frames))
    board_lines = "\n".join(f"- 스토리보드 이미지 {i + 1}: {p}" for i, p in enumerate(storyboard_images))

    prompt = (
        "너는 광고 QA 담당자다. 아래는 완성된 광고 영상에서 시간대별로 뽑은 프레임 여러 장과, "
        "그 영상을 만들 때 쓴 스토리보드 참고 이미지 여러 장이다. 두 단계로 판정해라.\n\n"
        "1단계: 스토리보드 이미지들의 '과반수'가 가리키는 제품/업종이 무엇인지 먼저 정해라. "
        "이미지 1장만 나머지와 다른 제품/업종을 보여준다면(스토리보드 자체에 다른 프로젝트 "
        "사진이 잘못 섞여 들어간 경우가 있음) 그 1장은 이상치로 보고 무시해라.\n"
        "2단계: 영상 프레임 여러 장 중 '하나라도' 1단계에서 정한 제품/업종과 일치하면 "
        "same_ad=true 다 — 광고 안에서도 장면마다 구도가 크게 다르므로(착장 장면 vs 제품 "
        "클로즈업 등) 특정 영상 프레임 하나가 안 맞는다고 곧바로 false 로 판정하지 않는다. "
        "영상 프레임 전체가 1단계 제품/업종과 무관하면 false.\n\n"
        f"[영상 프레임]\n{video_lines}\n\n[스토리보드 이미지]\n{board_lines}\n\n"
        f"첫 글자가 반드시 '{{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n{_SCHEMA}"
    )
    add_dirs = {p.parent for p in (*video_frames, *storyboard_images)}
    cmd = ["claude", "-p", prompt]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    return parse_json(result.stdout)
