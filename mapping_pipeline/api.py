"""FastAPI 서버 — 영상 + 시나리오 txt/json → cut_analysis·cut_scene_mapping JSON 반환."""
import json
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from mapping_pipeline.runner import run_mapping_pipeline
from utils.gemini_caller import DEFAULT_MODEL

app = FastAPI(
    title="광고 영상 컷-씬 매핑 API",
    description="영상 파일과 시나리오 텍스트를 받아 cut_analysis·cut_scene_mapping을 반환한다.",
    version="1.0.0",
)

_OUTPUT_ROOT = Path("output")


@app.get("/health")
def health() -> dict:
    """서버 상태 확인."""
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    video_file: UploadFile = File(..., description="분석할 영상 파일 (mp4)"),
    scenario_file: UploadFile | None = File(None, description="시나리오 .txt 또는 .json 파일 (scenario_text 대신 사용 가능)"),
    scenario_text: str = Form("", description="시나리오 텍스트 (scenario_file 대신 사용 가능)"),
    min_cuts: int | None = Form(7, description="최소 컷 수 (None이면 자동 조정 비활성)"),
    max_cuts: int = Form(15, description="최대 컷 수"),
    threshold: float = Form(27.0, description="scenedetect 컷 감지 초기 민감도"),
    gemini_model: str = Form(DEFAULT_MODEL, description="사용할 Gemini 모델명"),
) -> JSONResponse:
    """영상 + 시나리오 → cut_analysis·cut_scene_mapping을 JSON으로 반환한다.

    시나리오는 scenario_file 또는 scenario_text 중 하나를 반드시 제공해야 한다.
    둘 다 제공되면 scenario_file이 우선된다.
    """
    scenario = await _resolve_scenario(scenario_file, scenario_text)

    tmp_dir = Path(tempfile.mkdtemp(prefix="ad_api_"))
    try:
        video_path = await _save_upload(video_file, tmp_dir)
        stem = video_path.stem
        out_dir = _OUTPUT_ROOT / f"{stem}_{int(time.time())}"

        result = run_mapping_pipeline(
            video_path=video_path,
            scenario_txt=scenario,
            out_dir=out_dir,
            min_cuts=min_cuts,
            max_cuts=max_cuts,
            threshold=threshold,
            gemini_model=gemini_model.strip(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return JSONResponse(content=result)


async def _resolve_scenario(
    scenario_file: UploadFile | None,
    scenario_text: str,
) -> str:
    if scenario_file and scenario_file.filename:
        text = (await scenario_file.read()).decode("utf-8")
        if (scenario_file.filename or "").endswith(".json"):
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        return text
    if scenario_text.strip():
        return scenario_text.strip()
    raise HTTPException(
        status_code=422,
        detail="scenario_file 또는 scenario_text 중 하나를 반드시 제공해야 합니다.",
    )


async def _save_upload(upload: UploadFile, tmp_dir: Path) -> Path:
    suffix = Path(upload.filename or "video.mp4").suffix or ".mp4"
    dest = tmp_dir / f"video{suffix}"
    content = await upload.read()
    dest.write_bytes(content)
    return dest


if __name__ == "__main__":
    import sys
    import os

    os.chdir(Path(__file__).parent.parent)
    import uvicorn

    host = "0.0.0.0"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run("mapping_pipeline.api:app", host=host, port=port, reload=False)
