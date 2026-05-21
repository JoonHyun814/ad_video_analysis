import re
import subprocess
import sys
import tempfile
from pathlib import Path

_DIARIZE_SCRIPT = Path(__file__).parent.parent / "tools" / "whisper_diarization" / "diarize.py"


def run_diarization(
    video_path: Path,
    out_dir: Path,
    language: str = "ko",
    whisper_model: str = "medium",
    device: str = "cuda",
    stemming: bool = False,
) -> list[dict]:
    """whisper-diarization으로 화자 분리 STT를 수행하고 세그먼트 리스트를 반환한다.

    stemming=False: 배경음악 분리 비활성화 (광고 영상은 음악이 많아 분리 시 오히려 품질 저하 가능)
    """
    audio_path = _extract_audio(video_path, out_dir)
    _run_diarize(audio_path, language, whisper_model, device, stemming)
    srt_path = audio_path.with_suffix(".srt")
    segments = _parse_srt(srt_path)
    return segments


def _extract_audio(video_path: Path, out_dir: Path) -> Path:
    """ffmpeg로 영상에서 WAV 오디오를 추출한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "audio.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-ar", "16000", "-ac", "1",
            str(audio_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return audio_path


def _run_diarize(
    audio_path: Path,
    language: str,
    whisper_model: str,
    device: str,
    stemming: bool,
) -> None:
    """diarize.py를 subprocess로 실행한다. 출력 SRT/TXT는 audio_path 와 동일 디렉토리에 생성된다."""
    cmd = [
        sys.executable, str(_DIARIZE_SCRIPT),
        "-a", str(audio_path),
        "--whisper-model", whisper_model,
        "--language", language,
        "--device", device,
    ]
    if not stemming:
        cmd.append("--no-stem")

    subprocess.run(
        cmd,
        check=True,
        cwd=str(_DIARIZE_SCRIPT.parent),
    )


def _parse_srt(srt_path: Path) -> list[dict]:
    """SRT 파일을 파싱해 [{speaker, start_sec, end_sec, text}, ...] 로 변환한다."""
    text = srt_path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\n+", text.strip())
    segments = []

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        # lines[0]: 인덱스, lines[1]: 타임코드, lines[2:]: 텍스트
        time_match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", lines[1]
        )
        if not time_match:
            continue

        start_sec = _srt_time_to_sec(time_match.group(1))
        end_sec = _srt_time_to_sec(time_match.group(2))
        full_text = " ".join(lines[2:]).strip()

        # "Speaker 0: 텍스트" 형태 분리
        speaker_match = re.match(r"^(Speaker\s+\d+):\s*(.*)", full_text, re.DOTALL)
        if speaker_match:
            speaker = speaker_match.group(1)
            content = speaker_match.group(2).strip()
        else:
            speaker = "Speaker 0"
            content = full_text

        segments.append({
            "speaker": speaker,
            "start_sec": round(start_sec, 3),
            "end_sec": round(end_sec, 3),
            "text": content,
        })

    return segments


def _srt_time_to_sec(t: str) -> float:
    """'HH:MM:SS,mmm' → 초(float)"""
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
