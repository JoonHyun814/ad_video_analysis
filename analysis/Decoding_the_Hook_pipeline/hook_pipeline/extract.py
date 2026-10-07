"""단일 영상 처리: 프레임 샘플링 → 오디오·ASR → 음향 피처 → RAFT 카메라 모션 → MLLM 기법 추출."""
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from hook_pipeline import frame_sampling as fs
from hook_pipeline.acoustic import extract_acoustic_features
from hook_pipeline.hook_audio import extract_hook_audio, transcribe
from hook_pipeline.mllm import extract_methodology
from hook_pipeline.video_source import VideoSource

ANALYSIS_FILE = "hook_analysis.json"
ACOUSTIC_FILE = "acoustic_features.json"


@dataclass
class ExtractOptions:
    out_root: Path
    sampling: str  # "keyframe" | "random"
    num_frames: int  # random 샘플링의 m
    alpha: float  # keyframe τ 스케일
    min_interval: int  # keyframe Δt (프레임 수)
    seed: int
    hook_sec: float
    llm_backend: str
    llm_model: str | None
    asr_model: str
    asr_language: str | None
    qwen_model_path: str | None = None   # qwen_vl 백엔드 전용; None 이면 model.env 기본값 사용
    raft_device: str = "cuda"            # RAFT 추론 디바이스
    raft_model_size: str = "large"       # RAFT 모델 크기
    raft_step: int = 3                   # 카메라 모션 분석 프레임 간격
    raft_model_dir: str | None = None    # RAFT 가중치 캐시 디렉토리 (None = torch hub 기본)


def run_extract(src: VideoSource, opt: ExtractOptions) -> dict:
    """결과를 <out_root>/<key>/ 아래에 저장하고 hook_analysis 내용을 반환한다."""
    out = opt.out_root / src.key
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    print(f"  [1/5] 프레임 샘플링 ({opt.sampling})")
    frames, sampling_meta = _sample_frames(src.path, opt, out)
    _save_json(out / "frames.json", {"frames": frames, **sampling_meta})
    print(f"        {len(frames)}장 선택 (K={sampling_meta['hook_frame_count']}, fps={sampling_meta['fps']:.2f})")

    print("  [2/5] 훅 오디오 추출 + ASR")
    audio = extract_hook_audio(src.path, opt.hook_sec, out / "hook_audio.wav")
    asr = transcribe(audio, opt.asr_model, opt.asr_language) if audio else {"language": None, "text": "", "segments": []}
    _save_json(out / "asr.json", asr)
    print(f"        오디오={'있음' if audio else '없음'}, 전사='{asr['text'][:60]}'")

    print("  [3/5] 음향 피처 추출 (librosa)")
    acoustic = extract_acoustic_features(audio)
    _save_json(out / ACOUSTIC_FILE, acoustic)

    print(f"  [4/5] 카메라 모션 분석 (RAFT step={opt.raft_step})")
    camera_motion = _analyze_camera_motion(src.path, sampling_meta, opt)
    _save_json(out / "camera_motion.json", camera_motion)
    print(f"        dominant={camera_motion.get('dominant_label')}  n_pairs={camera_motion.get('n_pairs')}")
    # RAFT 해제 — Qwen 로드 전 VRAM 확보
    from hook_pipeline.camera_motion import release_raft
    release_raft()

    print(f"  [5/5] 훅 기법 추출 ({opt.llm_backend})")
    llm_out = extract_methodology(
        frames, src.title, asr["text"], opt.llm_backend, opt.hook_sec,
        opt.llm_model, qwen_model_path=opt.qwen_model_path,
        camera_motion=camera_motion,
    )
    analysis = {
        "key": src.key, "video_id": src.video_id, "video_path": str(src.path),
        "title": src.title, "body": asr["text"], "sampling": opt.sampling,
        "frame_times": [f["time_sec"] for f in frames], "llm_backend": opt.llm_backend,
        "camera_dominant_motion": camera_motion.get("dominant_label"),
        **llm_out,
    }
    _save_json(out / ANALYSIS_FILE, analysis)
    print(f"        methodology: {analysis.get('methodology', analysis.get('error'))}")
    return analysis


def _analyze_camera_motion(video_path: Path, sampling_meta: dict, opt: ExtractOptions) -> dict:
    from hook_pipeline.camera_motion import analyze_hook_camera_motion

    try:
        return analyze_hook_camera_motion(
            video_path,
            hook_frame_count=sampling_meta["hook_frame_count"],
            fps=sampling_meta["fps"],
            device=opt.raft_device,
            model_size=opt.raft_model_size,
            step=opt.raft_step,
            model_dir=opt.raft_model_dir,
        )
    except Exception as exc:
        print(f"        [경고] RAFT 분석 실패: {exc}")
        return {"step": opt.raft_step, "n_pairs": 0, "dominant_label": "unknown",
                "label_counts": {}, "mean_mag": 0.0, "pairs": [], "error": str(exc)}


def _sample_frames(video_path: Path, opt: ExtractOptions, out: Path) -> tuple[list[dict], dict]:
    k, fps = fs.hook_frame_count(video_path, opt.hook_sec)
    if k <= 0:
        raise RuntimeError(f"프레임을 읽을 수 없습니다: {video_path}")
    meta: dict = {"strategy": opt.sampling, "hook_frame_count": k, "fps": fps}
    if opt.sampling == "random":
        indices = fs.random_sampling(k, opt.num_frames, opt.seed)
        meta.update(m=opt.num_frames, seed=opt.seed)
    else:
        indices, diffs = fs.keyframe_selection(video_path, k, opt.alpha, opt.min_interval)
        meta.update(alpha=opt.alpha, min_interval=opt.min_interval,
                    tau=opt.alpha * max(diffs) if diffs else 0.0, ssim_diffs=[round(d, 4) for d in diffs])
    return fs.save_frames(video_path, indices, fps, out / "frames"), meta


def _save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
