"""FastAPI server for video + scenario to cut-scene mapping."""
import json
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from mapping_pipeline.runner import DEFAULT_BACKEND, _DEFAULT_THRESHOLD, run_mapping_pipeline
from utils.gemini_caller import DEFAULT_MODEL

app = FastAPI(
    title="Ad Video Cut-Scene Mapping API",
    description="Returns cut_analysis and cut_scene_mapping from a video file and scenario text.",
    version="1.0.0",
)

_OUTPUT_ROOT = Path("output")


@app.get("/health")
def health() -> dict:
    """Server health check."""
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    video_file: UploadFile = File(..., description="Video file to analyze, usually mp4."),
    scenario_file: UploadFile | None = File(None, description="Scenario .txt or .json file. Takes precedence over scenario_text."),
    scenario_text: str = Form("", description="Scenario text. Used when scenario_file is omitted."),
    min_cuts: int | None = Form(None, description="Minimum number of cuts. Omit to disable threshold auto-tuning."),
    max_cuts: int = Form(15, description="Maximum number of cuts."),
    backend: str = Form(DEFAULT_BACKEND, description="Cut detection backend: transnetv2 or scenedetect."),
    threshold: float | None = Form(None, description="Initial cut detection threshold. Uses backend default when omitted."),
    gemini_model: str = Form(DEFAULT_MODEL, description="Gemini model name."),
) -> JSONResponse:
    """Return cut_analysis and cut_scene_mapping for a video + scenario.

    Provide either scenario_file or scenario_text. If both are provided,
    scenario_file takes precedence.
    """
    tmp_dir: Path | None = None
    out_dir: Path | None = None
    try:
        scenario = await _resolve_scenario(scenario_file, scenario_text)
        tmp_dir = Path(tempfile.mkdtemp(prefix="ad_api_"))
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
            backend=backend.strip(),
            gemini_model=gemini_model.strip(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "out_dir": str(out_dir) if out_dir is not None else None,
            },
        )
    finally:
        if tmp_dir is not None:
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
        detail="Either scenario_file or scenario_text is required.",
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
