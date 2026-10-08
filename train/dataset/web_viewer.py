"""DHF1K / Hollywood-2 웹 뷰어 (Flask).

실행:
    python -m train.dataset.web_viewer
    python -m train.dataset.web_viewer --host 0.0.0.0 --port 4000
"""

import argparse
import io
import subprocess
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify, render_template, request
from PIL import Image

from train.dataset._dhf1k_frames import overlay_fix, overlay_sal, read_frame
from train.dataset._gaze import load_gaze_for_frame, overlay_gaze
from utils.env_loader import get_dhf1k_path, get_hollywood2_path

app = Flask(__name__, template_folder="templates")

_BSDTAR = "C:/Windows/System32/tar.exe"
_SPLITS = {"Train": (1, 600), "Val": (601, 700), "Test": (701, 1000)}
_ACTIONS = ["AnswerPhone", "DriveCar", "Eat", "FightPerson", "GetOutCar",
            "HandShake", "HugPerson", "Kiss", "Run", "SitDown", "SitUp", "StandUp"]

# ── 전역 상태 ──────────────────────────────────────────────────────────────────
_dhf1k_path: Path = Path()
_rar_path: str = ""
_rar_index: dict[str, list[str]] = {}
_hw2_path: Path = Path()
_gaze_dir: Path = Path()
_labels: dict[str, dict[str, int]] = {}


def _split_of(n: int) -> str:
    return "Train" if n <= 600 else ("Val" if n <= 700 else "Test")


def _rar_read(member: str) -> bytes:
    """bsdtar subprocess로 RAR에서 파일 한 개를 추출한다."""
    result = subprocess.run(
        [_BSDTAR, "-xf", _rar_path, "-O", member],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        raise FileNotFoundError(member)
    return result.stdout


def _init(dhf1k: Path, hw2: Path) -> None:
    global _dhf1k_path, _rar_path, _rar_index, _hw2_path, _gaze_dir, _labels
    _dhf1k_path = dhf1k
    _hw2_path = hw2
    _gaze_dir = hw2.parent  # gaze_*.zip 파일이 Hollywood-2/ 아래에 있음

    rar_file = dhf1k / "annotation.rar"
    if rar_file.exists():
        _rar_path = str(rar_file)
        result = subprocess.run(
            [_BSDTAR, "--list", "-f", _rar_path],
            capture_output=True, text=True,
        )
        for name in result.stdout.splitlines():
            name = name.strip()
            parts = name.split("/")
            if (len(parts) == 4 and parts[0] == "annotation"
                    and parts[2] == "maps" and name.endswith(".png")):
                _rar_index.setdefault(parts[1], []).append(parts[3][:-4])
        for v in _rar_index:
            _rar_index[v].sort()

    cs = hw2 / "ClipSets"
    for action in _ACTIONS:
        for split in ("train", "test"):
            f = cs / f"{action}_{split}.txt"
            if not f.exists():
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    _labels.setdefault(parts[0], {})[action] = int(parts[1])


# ── HTML ───────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template("viewer.html")


# ── DHF1K API ──────────────────────────────────────────────────────────────────

@app.get("/api/dhf1k/videos")
def dhf1k_videos():
    split = request.args.get("split", "All")
    lo, hi = (1, 1000) if split == "All" else _SPLITS[split]
    videos = [
        {"id": v, "split": _split_of(int(v)), "frames": len(_rar_index[v])}
        for v in sorted(_rar_index) if lo <= int(v) <= hi
    ]
    return jsonify(videos)


@app.get("/api/dhf1k/frames")
def dhf1k_frames():
    return jsonify(_rar_index.get(request.args.get("vid", ""), []))


@app.get("/api/dhf1k/image")
def dhf1k_image():
    vid, frame = request.args.get("vid", ""), request.args.get("frame", "")
    kind = request.args.get("kind", "sal")
    path = (f"annotation/{vid}/maps/{frame}.png" if kind == "sal"
            else f"annotation/{vid}/fixation/{frame}.png")
    try:
        data = _rar_read(path)
        return Response(data, mimetype="image/png")
    except Exception:
        return Response(status=404)


@app.get("/api/dhf1k/frame")
def dhf1k_frame():
    """영상 프레임 + 선택적 saliency/fixation 오버레이를 JPEG로 반환한다."""
    vid = request.args.get("vid", "")
    idx = int(request.args.get("idx", 0))
    mode = request.args.get("mode", "sal")  # original | sal | fix | both
    frames = _rar_index.get(vid, [])
    if not frames or idx >= len(frames):
        return Response(status=404)

    video_rar = str(_dhf1k_path / "video.rar")
    frame_stem = frames[idx]
    try:
        img, total = read_frame(video_rar, vid, idx)
    except Exception:
        return Response(status=404)

    if mode in ("sal", "both"):
        try:
            sal = _rar_read(f"annotation/{vid}/maps/{frame_stem}.png")
            img = overlay_sal(img, sal)
        except Exception:
            pass
    if mode in ("fix", "both"):
        try:
            fix = _rar_read(f"annotation/{vid}/fixation/{frame_stem}.png")
            img = overlay_fix(img, fix)
        except Exception:
            pass

    img.thumbnail((640, 360))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    resp = Response(buf.getvalue(), mimetype="image/jpeg")
    resp.headers["X-Total-Frames"] = total
    return resp


# ── Hollywood-2 API ────────────────────────────────────────────────────────────

@app.get("/api/hw2/clips")
def hw2_clips():
    action = request.args.get("action", "All")
    lf = request.args.get("label", "All")
    lv = int(lf) if lf != "All" else None
    all_ids = {p.stem for p in (_hw2_path / "AVIClips").glob("*.avi")}
    result = []
    for cid in sorted(all_ids):
        acts = _labels.get(cid, {})
        if action != "All" and action not in acts:
            continue
        if lv is not None:
            check = acts.get(action) if action != "All" else None
            if action != "All" and check != lv:
                continue
            if action == "All" and lv not in acts.values():
                continue
        pos = sum(1 for v in acts.values() if v == 1)
        result.append({"id": cid, "pos": pos, "neg": len(acts) - pos})
    return jsonify(result)


@app.get("/api/hw2/labels")
def hw2_labels():
    return jsonify(_labels.get(request.args.get("clip", ""), {}))


@app.get("/api/hw2/frame")
def hw2_frame():
    cid = request.args.get("clip", "")
    idx = int(request.args.get("idx", 0))
    show_gaze = request.args.get("gaze", "1") == "1"

    avi = _hw2_path / "AVIClips" / f"{cid}.avi"
    cap = cv2.VideoCapture(str(avi))
    fps = cap.get(cv2.CAP_PROP_FPS) or 23.976
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return Response(status=404)

    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    img.thumbnail((800, 450))

    if show_gaze and _gaze_dir.exists():
        gaze = load_gaze_for_frame(_gaze_dir, cid, idx, fps)
        img = overlay_gaze(img, gaze)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    resp = Response(buf.getvalue(), mimetype="image/jpeg")
    resp.headers["X-Total-Frames"] = total
    resp.headers["X-Gaze-Subjects"] = str(
        len(load_gaze_for_frame(_gaze_dir, cid, idx, fps)) if show_gaze else 0
    )
    return resp


@app.get("/api/hw2/gaze_subjects")
def hw2_gaze_subjects():
    """현재 로드된 gaze zip 파일 목록 반환."""
    zips = sorted(_gaze_dir.glob("gaze_*.zip"))
    return jsonify([z.name for z in zips])


# ── 진입점 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=4000)
    ap.add_argument("--dhf1k", type=Path, default=None)
    ap.add_argument("--hollywood2", type=Path, default=None)
    args = ap.parse_args()

    dhf1k = args.dhf1k or get_dhf1k_path()
    hw2 = args.hollywood2 or get_hollywood2_path()
    print(f"DHF1K:       {dhf1k}")
    print(f"Hollywood-2: {hw2}")
    print("인덱싱 중…")
    _init(dhf1k, hw2)
    print(f"DHF1K 영상 {len(_rar_index)}개 | Hollywood-2 레이블 {len(_labels)}개")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
