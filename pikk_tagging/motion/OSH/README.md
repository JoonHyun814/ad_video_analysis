# OSH — ORB / SIFT + RANSAC + Homography

영상 프레임 간 특징점을 매칭해 호모그라피를 추정하고 카메라 모션을 분류한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `feature_match.py` | ORB/SIFT 특징 검출 → BFMatcher + 비율 테스트 → RANSAC 호모그라피 → 모션 분류 |

## CLI 사용법

```bash
# 영상 전체 프레임 간 모션 분석
python -m pikk_tagging.OSH.feature_match video path/to/video.mp4 --detector orb --step 30

# 두 영상 간 시각 유사도
python -m pikk_tagging.OSH.feature_match similarity a.mp4 b.mp4 --detector orb --frames 5
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--detector` | `orb` | `orb` (빠름) \| `sift` (정확) |
| `--step N` | `30` | video 모드: N 프레임마다 샘플링 |
| `--out CSV` | 없음 | video 모드: 결과 CSV 저장 |
| `--frames N` | `5` | similarity 모드: 영상당 샘플 프레임 수 |

## 출력 컬럼 (video CSV)

`frame_a, frame_b, detector, kp_a, kp_b, raw_matches, inliers, inlier_ratio, homography_ok, motion_type`

`motion_type`: `pan` / `zoom` / `rotate` / `static` / `cut`

## 한계

호모그라피 기반 scale 변화는 프레임 단위 변화가 너무 작아 **느린 줌**에 민감하지 않다.
씬컷이 분석창 안에 있으면 호모그라피가 폭발적으로 오류를 낸다.
카메라 앵글(하이앵글·탑뷰), 샷 크기(클로즈업), 조명(하이키) 등 **구도·조명** 기법은 감지 불가.

→ 모션 감지에는 [`../optical_flow/`](../optical_flow/README.md) 사용 권장.
