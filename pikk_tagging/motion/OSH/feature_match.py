"""ORB/SIFT + RANSAC + Homography 기반 영상 프레임 분석.

- 단일 영상: 연속 프레임 간 특징 매칭 → 카메라 모션 분류 / 컷 감지
- 영상 쌍: 대표 프레임 간 매칭 → 씬 유사도 스코어
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np


DetectorName = Literal["orb", "sift"]

@dataclass
class MatchResult:
    frame_a: int
    frame_b: int
    detector: str
    kp_a: int
    kp_b: int
    raw_matches: int
    inliers: int
    inlier_ratio: float
    homography_ok: bool
    motion_type: str   # pan / zoom / rotate / cut / static


def make_detector(name: DetectorName) -> cv2.Feature2D:
    if name == "orb":
        return cv2.ORB_create(nfeatures=2000)
    return cv2.SIFT_create(nfeatures=2000)


def make_matcher(name: DetectorName) -> cv2.DescriptorMatcher:
    if name == "orb":
        return cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    return cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)


def detect_and_compute(
    detector: cv2.Feature2D, gray: np.ndarray
) -> tuple[list, np.ndarray | None]:
    kps, desc = detector.detectAndCompute(gray, None)
    return kps, desc


def ratio_test(matches: list, threshold: float = 0.75) -> list:
    good = []
    for pair in matches:
        if len(pair) == 2 and pair[0].distance < threshold * pair[1].distance:
            good.append(pair[0])
    return good


def compute_homography(
    kp_a: list, kp_b: list, good: list
) -> tuple[np.ndarray | None, np.ndarray | None]:
    if len(good) < 4:
        return None, None
    pts_a = np.float32([kp_a[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    pts_b = np.float32([kp_b[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(pts_a, pts_b, cv2.RANSAC, ransacReprojThreshold=5.0)
    return H, mask


def classify_motion(H: np.ndarray | None, mask: np.ndarray | None, inliers: int) -> str:
    if inliers < 6 or H is None:
        return "cut"
    tx, ty = H[0, 2], H[1, 2]
    sx = np.sqrt(H[0, 0] ** 2 + H[1, 0] ** 2)
    sy = np.sqrt(H[0, 1] ** 2 + H[1, 1] ** 2)
    angle = np.degrees(np.arctan2(H[1, 0], H[0, 0]))
    if abs(angle) > 5:
        return "rotate"
    if abs(sx - 1) > 0.08 or abs(sy - 1) > 0.08:
        return "zoom"
    if abs(tx) > 5 or abs(ty) > 5:
        return "pan"
    return "static"


def motion_for_shot(
    frames: list[tuple[int, np.ndarray]],
    detector_name: DetectorName = "orb",
) -> str:
    """샷의 첫 프레임 vs 마지막 프레임을 매칭해 누적 모션 유형 반환.

    첫·끝 비교이므로 샷 전체 스케일 변화가 축적되어 느린 줌도 감지 가능.
    임계값: scale ±3% (연속쌍 8% 대비 낮춤), pan 4.7% (15px/320px).
    """
    if len(frames) < 2:
        return "static"

    detector = make_detector(detector_name)
    matcher = make_matcher(detector_name)

    _, gray_a = frames[0]
    _, gray_b = frames[-1]
    kps_a, desc_a = detect_and_compute(detector, gray_a)
    kps_b, desc_b = detect_and_compute(detector, gray_b)

    if desc_a is None or desc_b is None or len(desc_a) < 8 or len(desc_b) < 8:
        return "unknown"

    raw = matcher.knnMatch(desc_a, desc_b, k=2)
    good = ratio_test(raw)
    H, mask = compute_homography(kps_a, kps_b, good)
    if H is None or mask is None or int(mask.sum()) < 8:
        return "unknown"

    tx, ty = float(H[0, 2]), float(H[1, 2])
    sx = float(np.sqrt(H[0, 0] ** 2 + H[1, 0] ** 2))
    sy = float(np.sqrt(H[0, 1] ** 2 + H[1, 1] ** 2))
    scale = (sx + sy) / 2
    angle = float(np.degrees(np.arctan2(H[1, 0], H[0, 0])))

    pan_frac = max(abs(tx), abs(ty)) / 320
    scale_dev = abs(scale - 1.0)

    if abs(angle) > 8:
        return "rotate"
    if scale_dev > 0.03 and scale_dev > pan_frac * 1.5:
        return "zoom_in" if scale > 1.0 else "zoom_out"
    if pan_frac > 0.047:  # 15px / 320px
        return "pan"
    return "static"


def extract_frames(video_path: Path, step: int = 30) -> list[tuple[int, np.ndarray]]:
    """step 프레임마다 그레이스케일 프레임 추출."""
    cap = cv2.VideoCapture(str(video_path))
    frames: list[tuple[int, np.ndarray]] = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frames.append((idx, gray))
        idx += 1
    cap.release()
    return frames


def analyze_video(
    video_path: Path,
    detector_name: DetectorName,
    step: int = 30,
) -> list[MatchResult]:
    detector = make_detector(detector_name)
    matcher = make_matcher(detector_name)
    frames = extract_frames(video_path, step)
    _log(f"  추출 프레임: {len(frames)} (step={step})")
    results: list[MatchResult] = []
    for i in range(len(frames) - 1):
        fidx_a, gray_a = frames[i]
        fidx_b, gray_b = frames[i + 1]
        kps_a, desc_a = detect_and_compute(detector, gray_a)
        kps_b, desc_b = detect_and_compute(detector, gray_b)
        if desc_a is None or desc_b is None or len(desc_a) < 2 or len(desc_b) < 2:
            results.append(MatchResult(fidx_a, fidx_b, detector_name,
                                       len(kps_a), len(kps_b), 0, 0, 0.0, False, "cut"))
            continue
        raw = matcher.knnMatch(desc_a, desc_b, k=2)
        good = ratio_test(raw)
        H, mask = compute_homography(kps_a, kps_b, good)
        inliers = int(mask.sum()) if mask is not None else 0
        inlier_ratio = inliers / len(good) if good else 0.0
        motion = classify_motion(H, mask, inliers)
        results.append(MatchResult(
            frame_a=fidx_a, frame_b=fidx_b, detector=detector_name,
            kp_a=len(kps_a), kp_b=len(kps_b),
            raw_matches=len(good), inliers=inliers,
            inlier_ratio=round(inlier_ratio, 3),
            homography_ok=H is not None, motion_type=motion,
        ))
    return results


def video_similarity(
    path_a: Path,
    path_b: Path,
    detector_name: DetectorName,
    sample_frames: int = 5,
) -> dict:
    """두 영상에서 대표 프레임을 교차 매칭 → 평균 inlier 수를 유사도로 반환."""
    detector = make_detector(detector_name)
    matcher = make_matcher(detector_name)

    def pick_frames(path: Path) -> list[np.ndarray]:
        cap = cv2.VideoCapture(str(path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        indices = [int(total * k / (sample_frames + 1)) for k in range(1, sample_frames + 1)]
        picked = []
        for target in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            ret, frame = cap.read()
            if ret:
                picked.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        cap.release()
        return picked

    frames_a, frames_b = pick_frames(path_a), pick_frames(path_b)
    total_inliers = 0
    pair_count = 0
    for fa in frames_a:
        kps_a, desc_a = detect_and_compute(detector, fa)
        if desc_a is None or len(desc_a) < 2:
            continue
        for fb in frames_b:
            kps_b, desc_b = detect_and_compute(detector, fb)
            if desc_b is None or len(desc_b) < 2:
                continue
            raw = matcher.knnMatch(desc_a, desc_b, k=2)
            good = ratio_test(raw)
            _, mask = compute_homography(kps_a, kps_b, good)
            total_inliers += int(mask.sum()) if mask is not None else 0
            pair_count += 1
    avg_inliers = total_inliers / pair_count if pair_count else 0.0
    return {
        "video_a": path_a.name, "video_b": path_b.name,
        "detector": detector_name, "pairs_compared": pair_count,
        "avg_inliers": round(avg_inliers, 2), "similar": avg_inliers > 10,
    }


def _log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


def _save_results(results: list[MatchResult], out_path: Path) -> None:
    rows = [asdict(r) for r in results]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(results: list[MatchResult]) -> None:
    from collections import Counter
    counts = Counter(r.motion_type for r in results)
    avg_kp = sum(r.kp_a for r in results) / len(results) if results else 0
    avg_inliers = sum(r.inliers for r in results) / len(results) if results else 0
    _log(f"\n[요약]  쌍={len(results)}  평균kp={avg_kp:.0f}  평균inlier={avg_inliers:.1f}")
    _log(f"  모션 분류: {dict(counts)}")
    cuts = [r for r in results if r.motion_type == "cut"]
    if cuts:
        _log(f"  컷 감지: {[r.frame_a for r in cuts]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OSH: ORB/SIFT+RANSAC+Homography 영상 분석")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_vid = sub.add_parser("video", help="단일 영상 모션 분석")
    p_vid.add_argument("video", type=Path)
    p_vid.add_argument("--detector", choices=["orb", "sift"], default="orb")
    p_vid.add_argument("--step", type=int, default=30, metavar="N")
    p_vid.add_argument("--out", type=Path, default=None, metavar="CSV")

    p_sim = sub.add_parser("similarity", help="영상 쌍 유사도")
    p_sim.add_argument("video_a", type=Path)
    p_sim.add_argument("video_b", type=Path)
    p_sim.add_argument("--detector", choices=["orb", "sift"], default="orb")
    p_sim.add_argument("--frames", type=int, default=5, metavar="N")

    args = parser.parse_args()
    if args.cmd == "video":
        _log(f"[OSH:video] {args.video.name}  detector={args.detector}  step={args.step}")
        results = analyze_video(args.video, args.detector, args.step)
        _print_summary(results)
        if args.out:
            _save_results(results, args.out)
            _log(f"  저장: {args.out}")
    else:
        _log(f"[OSH:similarity] {args.video_a.name} vs {args.video_b.name}")
        sim = video_similarity(args.video_a, args.video_b, args.detector, args.frames)
        _log(json.dumps(sim, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
