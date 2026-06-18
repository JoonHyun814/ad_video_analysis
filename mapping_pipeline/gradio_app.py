"""Gradio GUI — 영상 + 시나리오 txt/json → cut_analysis·cut_scene_mapping 출력."""
import json
import queue
import threading
import time
from pathlib import Path

import gradio as gr

from mapping_pipeline.runner import (
    BACKEND_TRANSNETV2,
    BACKEND_SCENEDETECT,
    DEFAULT_BACKEND,
    DEFAULT_LLM_BACKEND,
    LLM_GEMINI,
    LLM_OPENAI,
    _DEFAULT_THRESHOLD,
    default_llm_model,
    run_mapping_pipeline,
)

_OUTPUT_ROOT = Path("output")


def _load_scenario(path: Path) -> str:
    """시나리오 파일을 읽는다. .json이면 포맷된 JSON 문자열로, 그 외엔 원문 그대로 반환한다."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    return text


def _make_out_dir(video_path: str) -> Path:
    stem = Path(video_path).stem
    ts = str(int(time.time()))
    return _OUTPUT_ROOT / f"{stem}_{ts}"


_BTN_LOADING = gr.update(interactive=False, value="⏳ 분석 중...")
_BTN_READY = gr.update(interactive=True, value="분석 시작")
_BTN_NOOP = gr.update()


def analyze(
    video_file: str | None,
    scenario_file: str | None,
    scenario_text: str,
    backend: str,
    min_cuts: int,
    max_cuts: int,
    threshold: float,
    llm_backend: str,
    llm_model: str,
):
    """파이프라인을 실행하고 로그·결과를 스트리밍으로 yield한다."""
    if not video_file:
        yield "영상 파일을 업로드하세요.", None, None, _BTN_NOOP
        return

    scenario = ""
    if scenario_file:
        scenario = _load_scenario(Path(scenario_file))
    elif scenario_text.strip():
        scenario = scenario_text.strip()
    else:
        yield "시나리오를 업로드하거나 텍스트로 입력하세요.", None, None, _BTN_NOOP
        return

    yield "파이프라인 시작...", None, None, _BTN_LOADING

    log_q: queue.Queue[tuple[str, object]] = queue.Queue()
    result_holder: dict = {}

    def on_progress(msg: str) -> None:
        log_q.put(("log", msg))

    def run_thread() -> None:
        try:
            out_dir = _make_out_dir(video_file)
            result_holder["data"] = run_mapping_pipeline(
                video_path=Path(video_file),
                scenario_txt=scenario,
                out_dir=out_dir,
                min_cuts=int(min_cuts) if int(min_cuts) > 0 else None,
                max_cuts=int(max_cuts),
                threshold=float(threshold),
                backend=backend,
                llm_backend=llm_backend,
                llm_model=llm_model.strip() or None,
                on_progress=on_progress,
            )
            log_q.put(("done", None))
        except Exception as exc:
            log_q.put(("error", str(exc)))

    thread = threading.Thread(target=run_thread, daemon=True)
    thread.start()

    logs: list[str] = []
    while True:
        kind, value = log_q.get()
        if kind == "log":
            logs.append(value)
            yield "\n".join(logs), None, None, _BTN_NOOP
        elif kind == "done":
            data = result_holder["data"]
            cut_analysis_json = json.dumps(data["cut_analysis"], ensure_ascii=False, indent=2)
            mapping_json = json.dumps(data["cut_scene_mapping"], ensure_ascii=False, indent=2)
            logs.append("\n파이프라인 완료!")
            yield "\n".join(logs), cut_analysis_json, mapping_json, _BTN_READY
            break
        elif kind == "error":
            logs.append(f"\n[오류] {value}")
            yield "\n".join(logs), None, None, _BTN_READY
            break


def _update_threshold(backend: str) -> float:
    return _DEFAULT_THRESHOLD[backend]


def _update_llm_model(llm_backend: str) -> str:
    return default_llm_model(llm_backend)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="광고 영상 컷-씬 매핑") as demo:
        gr.Markdown("## 광고 영상 컷-씬 매핑 분석기")
        gr.Markdown("영상 파일과 시나리오를 입력하면 **컷 분석** 및 **씬 매핑** 결과를 반환합니다.")

        with gr.Row():
            with gr.Column(scale=1):
                video_input = gr.Video(label="영상 파일 (mp4)", sources=["upload"])
                scenario_file_input = gr.File(
                    label="시나리오 파일 (.txt 또는 .json)", file_types=[".txt", ".json"]
                )
                scenario_text_input = gr.Textbox(
                    label="시나리오 직접 입력 (파일 업로드 우선)",
                    lines=8,
                    placeholder="파일을 업로드하거나 여기에 시나리오를 붙여넣으세요.",
                )

            with gr.Column(scale=1):
                backend_input = gr.Radio(
                    label="컷 감지 백엔드",
                    choices=[BACKEND_TRANSNETV2, BACKEND_SCENEDETECT],
                    value=DEFAULT_BACKEND,
                )
                min_cuts_input = gr.Slider(
                    label="최소 컷 수 (0=비활성)", minimum=0, maximum=50, value=0, step=1
                )
                max_cuts_input = gr.Slider(
                    label="최대 컷 수", minimum=1, maximum=50, value=15, step=1
                )
                threshold_input = gr.Number(
                    label="컷 감지 민감도 초기값 (transnetv2: 0.3 기본 / scenedetect: 27.0 기본)",
                    value=_DEFAULT_THRESHOLD[DEFAULT_BACKEND],
                    precision=3,
                )
                llm_backend_input = gr.Radio(
                    label="LLM 백엔드",
                    choices=[LLM_GEMINI, LLM_OPENAI],
                    value=DEFAULT_LLM_BACKEND,
                )
                llm_model_input = gr.Textbox(
                    label="LLM 모델 (비워두면 백엔드 기본값 사용)",
                    value=default_llm_model(DEFAULT_LLM_BACKEND),
                )
                run_btn = gr.Button("분석 시작", variant="primary")

        with gr.Row():
            log_output = gr.Textbox(label="진행 로그", lines=12, interactive=False)

        with gr.Row():
            cut_analysis_output = gr.Code(
                label="cut_analysis.json", language="json", lines=20
            )
            mapping_output = gr.Code(
                label="cut_scene_mapping.json", language="json", lines=20
            )

        backend_input.change(
            fn=_update_threshold,
            inputs=[backend_input],
            outputs=[threshold_input],
        )
        llm_backend_input.change(
            fn=_update_llm_model,
            inputs=[llm_backend_input],
            outputs=[llm_model_input],
        )

        run_btn.click(
            fn=analyze,
            inputs=[
                video_input,
                scenario_file_input,
                scenario_text_input,
                backend_input,
                min_cuts_input,
                max_cuts_input,
                threshold_input,
                llm_backend_input,
                llm_model_input,
            ],
            outputs=[log_output, cut_analysis_output, mapping_output, run_btn],
        )

    return demo


if __name__ == "__main__":
    import sys
    import os

    os.chdir(Path(__file__).parent.parent)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7860
    demo = build_ui()
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=port)
