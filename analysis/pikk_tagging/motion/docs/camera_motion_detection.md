# 카메라 모션 감지: 방법론 및 실험 기록

> 작성일: 2026-09-29  
> 대상 모듈: `pikk_tagging/RAFT/`, `pikk_tagging/RAFT_step/`

---

## 1. 카메라 모션 감지 방법론

### 1.1 광학 흐름(Optical Flow) 개요

광학 흐름은 연속된 두 프레임 사이에서 각 픽셀이 이동한 방향과 크기를 벡터 필드로 표현한다. 카메라 모션 감지는 이 벡터 필드에서 **전역(global) 패턴**을 분석하는 방식으로 이루어진다.

| 카메라 모션 | 광학 흐름 특성 |
|------------|-------------|
| Pan (수평/수직 이동) | 전체 벡터 평균(`mean(u)`, `mean(v)`)이 한 방향으로 편향 |
| Zoom In/Out | 벡터가 중앙에서 바깥(in) 또는 안쪽(out)으로 발산/수렴 → divergence `∂u/∂x + ∂v/∂y` |
| Rotation (Roll) | 벡터가 중심을 기준으로 회전 → curl `∂v/∂x − ∂u/∂y` |
| Static | 전체 평균 이동량(mean magnitude) ≈ 0 |

---

### 1.2 RAFT: Recurrent All-Pairs Field Transforms

> Teed, Z., & Deng, J. (2020). *RAFT: Recurrent All-Pairs Field Transforms for Optical Flow.* ECCV 2020. [[arXiv:2003.12039]](https://arxiv.org/abs/2003.12039)

#### 핵심 문제

기존 coarse-to-fine 방식의 딥러닝 광학 흐름 추정은 해상도를 단계적으로 낮추며 흐름을 예측하기 때문에, 낮은 해상도 단계에서 놓친 픽셀 대응 관계를 나중에 복구하기 어렵다. 또한 각 해상도 단계마다 별도 파라미터를 사용하여 모델이 비대해진다.

#### 아키텍처

```
프레임 I₁, I₂
    │
    ▼
[Feature Encoder]  ← I₁, I₂ 모두 처리, 1/8 해상도로 특징 추출 (6개 residual block)
[Context Network]  ← I₁ 만 처리, GRU hidden state 초기화에 사용
    │
    ▼
[4D Correlation Volume]
  C(g(I₁), g(I₂)) ∈ ℝ^(H×W×H×W)
  모든 픽셀 쌍의 dot product → 4단계 average pooling으로 multi-scale pyramid
    │
    ▼
[Recurrent Update Operator] (GRU, 2.7M params, 가중치 공유)
  - 현재 흐름 추정값 f_k 기준 correlation volume lookup
  - Δf 예측 후 f_{k+1} = f_k + Δf 로 반복 갱신
  - 기본 12회, 추론 시 최대 100회 이상 반복 가능
    │
    ▼
[Learned Upsampling]  ← 1/8 → 원본 해상도 복원
    │
    ▼
최종 흐름 필드 (H, W, 2)
```

#### 핵심 특징

- **단일 해상도 유지**: coarse-to-fine 방식을 버리고 1/8 해상도의 흐름 필드 하나만 유지하며 반복 갱신
- **가중치 공유(tied weights)**: 모든 반복 단계가 동일한 GRU 가중치 사용 → 정규화 효과, 빠른 학습
- **Warm-start**: 비디오 시퀀스에서 이전 프레임의 흐름을 다음 예측의 초기값으로 활용
- **파라미터 효율**: 5.3M params (large), 1.0M (small)

#### 벤치마크 성능

| 데이터셋 | EPE (RAFT) | 비고 |
|---------|-----------|------|
| Sintel Clean (train) | 1.43 | 이전 최고 대비 29% 개선 |
| Sintel Final (train) | 2.71 | |
| KITTI-15 (test) | 5.10% F1 | 이전 최고 대비 16% 개선 |

---

### 1.3 GMA: Global Motion Aggregation

> Jiang, S., Campbell, D., Lu, Y., Li, H., & Hartley, R. (2021). *Learning to Estimate Hidden Motions with Global Motion Aggregation.* ICCV 2021. [[arXiv:2104.02409]](https://arxiv.org/abs/2104.02409)

#### 핵심 문제

RAFT를 포함한 기존 광학 흐름 방법은 **occluded region**(첫 번째 프레임에는 보이지만 두 번째 프레임에서 가려진 픽셀)에서 대응점을 찾지 못해 흐름 추정이 크게 저하된다. 이 문제는 로컬 정보만으로는 해결이 불가능하다.

#### 핵심 아이디어

*"Non-occluded self-similar points의 모션 정보를 occluded point에 propagate할 수 있다."*

같은 프레임 내에서 외관(appearance)이 유사한 픽셀들은 비슷한 모션을 가질 가능성이 높다. Transformer의 self-attention을 활용해 외관 유사성 기반 모션 정보를 전파한다.

#### 아키텍처

```
RAFT 파이프라인 (그대로 유지)
    │
    ├── Correlation features (로컬 모션 정보)
    ├── Context features (외관 정보, I₁)
    │
    ▼
[Global Motion Aggregation Module]  ← RAFT에 추가되는 모듈
  Query/Key: Context features에서 추출 (외관 기반 유사도 계산)
  Value:     Motion encoding (상관 볼륨에서 추출한 모션 정보)

  ŷᵢ = yᵢ + α · Σⱼ f(θ(xᵢ), φ(xⱼ)) · σ(yⱼ)

  → occluded pixel i가 유사 외관 pixel j들의 모션 yⱼ를 가중 평균으로 수신
    │
    ▼
로컬 + 글로벌 모션 features → GRU Update Operator (RAFT와 동일)
```

#### 성능 향상

| 벤치마크 | RAFT | GMA | 개선율 |
|---------|------|-----|------|
| Sintel Clean | 1.61 | 1.39 | 13.7% |
| Sintel Final | 2.86 | 2.47 | 13.6% |
| Occluded 영역 (Clean) | — | — | **20.7%** |
| Out-of-frame occlusion | — | — | **28.2%** |

#### 카메라 모션 감지와의 관련성

컷(cut) 근처 프레임 쌍에서는 화면의 많은 영역이 사실상 "occluded"된 상태와 유사하다. GMA는 이러한 전환 구간에서 흐름 추정의 품질을 높여, 컷 직전/직후 프레임에서도 보다 신뢰할 수 있는 통계값(zoom_score, pan_x 등)을 얻을 수 있다.  
`torchvision`의 `raft_large`는 GMA 기반 개선을 포함한 가중치를 제공한다.

---

### 1.4 Two-Stream + LSTM for Video Understanding

> Wu, Z., Wang, X., Jiang, Y.-G., Ye, H., & Xue, X. (2015). *Modeling Spatial-Temporal Clues in a Hybrid Deep Learning Framework for Video Classification.* ACM MM 2015. [[arXiv:1504.01561]](https://arxiv.org/abs/1504.01561)

#### 핵심 문제

단일 프레임(spatial) 정보만으로는 동영상의 움직임 패턴을 충분히 표현할 수 없다. 광학 흐름을 활용한 모션 스트림과 이미지 스트림을 어떻게 효과적으로 결합하는가.

#### 아키텍처

```
입력 비디오
    │
    ├──[Spatial Stream] VGG-19
    │    단일 RGB 프레임
    │
    └──[Motion Stream] CNN_M
         2L-channel stacked optical flow
         (L 프레임에 걸친 수평·수직 성분 적층)
    │
    ▼
[Feature Fusion Network]  ← regularized 4-layer FC
    │
    ▼
[LSTM ×2]  (1024 + 512 hidden units)
  시퀀스 (x₁, x₂, ..., xₜ) 처리
  마지막 timestep 출력 = 영상 전체 예측
    │
    ▼
분류 결과
```

#### 광학 흐름 활용 방식

- 단일 흐름 이미지가 아닌 **L개 프레임에 걸친 흐름을 채널 방향으로 적층(stacking)**하여 단기 모션을 표현
- 이를 통해 CNN이 다중 프레임에 걸친 모션 패턴을 단일 forward pass로 처리 가능
- LSTM은 이 단기 모션 특징들을 시간 순서로 처리하며 장기 의존성 포착

#### 성능

| 데이터셋 | 정확도 |
|---------|------|
| UCF-101 | 91.3% |
| Columbia Consumer Video (CCV) | 83.5% mAP |

#### 카메라 모션 감지와의 관련성

이 논문은 카메라 모션을 직접 분류하지 않지만, **광학 흐름을 단기 모션의 표현으로 사용**하는 방법론적 기반을 제공한다. Stacked optical flow의 개념은 본 프로젝트의 step 기반 분석과 유사하게, 연속된 프레임 간 흐름의 시계열을 모션 특징으로 활용한다는 공통점이 있다.

---

## 2. 실험 기록

### 개요

광고 영상에서 컷 단위의 카메라 모션을 자동 태깅하기 위해 세 가지 접근법을 순차적으로 실험했다. 모두 `torchvision`의 `raft_large` (GMA 기반) 모델을 기반으로 한다.

---

### 2.1 실험 1: 컷 분할 후 컷별 RAFT 분석

> 모듈: `pikk_tagging/RAFT/`

#### 방법

1. `shot_detect.detect_shots()`로 영상을 컷 단위로 분할
2. 각 컷에서 프레임 쌍 `(start_frame, min(start_frame + step, end_frame))` 하나만 추출
3. 해당 쌍에 RAFT를 실행하여 flow 필드 획득
4. flow → FlowStats (zoom_score, pan_x/y, rotation_score, flow_var, mean_mag) 계산
5. 임계값 기반 단일 레이블 분류

```python
# 컷당 1쌍, step=25 (1초 간격)
motion_type = classify_flow(flow)  # 'static' | 'zoom_in' | 'pan_left' | ...
```

#### FlowStats 계산

```python
pan_x  = mean(u)                         # 수평 평균 흐름
pan_y  = mean(v)                         # 수직 평균 흐름
zoom   = mean(∂u/∂x + ∂v/∂y)            # 발산 (divergence)
rotate = mean(∂v/∂x − ∂u/∂y)            # 회전 (curl)
mean_mag = mean(√(u²+v²))               # 평균 이동량
flow_var = var(√(u²+v²))                # 이동량 분산
```

#### 결과 및 한계

| 항목 | 내용 |
|------|------|
| 출력 | 컷별 단일 레이블 (`motion_summary.json`) |
| 장점 | 연산 효율적 (컷당 1회 RAFT), 컷 경계 명확 |
| 한계 1 | 컷 내부에서 모션이 바뀌어도 1개 레이블만 반환 |
| 한계 2 | step=25(1s)는 짧은 모션 이벤트(< 1s)를 놓침 |
| 한계 3 | `mean_mag` 임계값이 낮으면 과도한 레이블링 (tripod도 pan으로 분류) |

임계값 조정 결과 (`_MIN_MAG_MOTION`: 2.0 → 5.0, pan 임계값 0.5% → 1.2%):  
static 비율이 크게 증가하고 false positive 감소.

---

### 2.2 실험 2: 10프레임 간격 Dense 분석

> 모듈: `pikk_tagging/RAFT_step/` (step=10)

#### 방법

컷 경계와 무관하게 **10프레임(0.4초) 간격**으로 전체 영상을 샘플링하여 RAFT 실행.

```
frame 0→10, 10→20, 20→30, ... (영상 전체)
```

- 컷 경계를 고려하지 않으므로 컷 스파이크가 그대로 데이터에 포함됨
- 레이블 분류 없이 **raw stats 값 자체**를 저장 (분류는 후처리에서 수행)

#### 최적화: 단일 패스 프레임 읽기

```python
# 필요한 프레임 인덱스를 미리 계산 → 한 번의 순차 읽기 패스
needed = {0, 10, 20, 30, ...}
while cap.read():
    if idx in needed:
        frames[idx] = frame
```

`cap.set()` 반복 호출 대신 순차 읽기 → 처리 속도 대폭 향상.

#### 결과 및 한계

| 항목 | 내용 |
|------|------|
| 출력 | 쌍별 raw stats JSON (`step_results.json`) |
| 장점 | 컷 내부 모션 변화 추적 가능 |
| 한계 1 | step=10(0.4s)보다 짧은 모션 이벤트 감지 불가 |
| 한계 2 | 컷 경계에 큰 스파이크 발생 (mean_mag 100~300px) |
| 한계 3 | 15프레임짜리 zoom_out은 1쌍뿐 → 분류 불가 |

실험 케이스 — `KccntjIMKQI` 영상 760~800프레임:
- 760~780: zoom_in (20프레임) → step=10에서 **2쌍** → 임계값 미달로 필터링됨
- 790~800: zoom_out (10프레임) → step=10에서 **1쌍** → 감지 불가

---

### 2.3 실험 3: 5프레임 간격 + 스무싱

> 모듈: `pikk_tagging/RAFT_step/` (step=5) + `smooth.py`

#### 방법

**A. step=5 (0.2초) 밀도 증가**

```
frame 0→5, 5→10, 10→15, ... (영상 전체)
```

단계 수: step=10 대비 2배. `KccntjIMKQI` 기준 174 → 348쌍.

**B. 스파이크 감지 및 보간**

컷 경계는 `mean_mag`이 주변 대비 급격히 증가하는 스파이크로 나타난다.

```python
# 로컬 윈도우(±5 스텝) 중앙값과 비교
if mag[i] > _SPIKE_MIN_MAG(15px) and mag[i] / median(neighbors) >= 3.0:
    → SPIKE로 마킹
    → 좌우 비스파이크 이웃값으로 선형 보간
```

**C. 레이블 분류**

우선순위: **zoom > pan > rotation**

```python
if |zoom_score| > 0.05:            # zoom이 threshold 이상이면 최우선
    return "zoom_in" or "zoom_out"
elif |pan_x| > 5px or |pan_y| > 5px:
    return "pan_right/left/tilt_up/down"
elif |rotation_score| > 0.015:
    return "rotate_cw/ccw"
else:
    return "motion"  # 움직임은 있으나 지배적 성분 없음
```

> **수정 이유**: 초기 구현에서 zoom=0.39임에도 rotation=0.021(경미한 흔들림)이 동시에 존재하면 `rotate_cw`로 오분류되는 버그 수정. zoom 신호가 명확한 경우 rotation 아티팩트를 무시하도록 우선순위 재정립.

**D. Temporal Filter (최소 지속 필터)**

```python
min_steps = ceil(min_frames / step)  # min_frames=10, step=5 → min_steps=2

# 연속 구간이 min_steps 미만이면 이웃 레이블로 교체
# 수렴할 때까지 반복 (while changed)
```

단기 노이즈 레이블(1스텝 = 5프레임)이 zoom/pan 시퀀스를 끊는 현상 제거.

#### 결과

`KccntjIMKQI` 760~800프레임 검증:

| 프레임 구간 | 실제 모션 | step=10 결과 | step=5 + smooth 결과 |
|-----------|---------|------------|-------------------|
| 760~780 | zoom_in (20프레임) | ❌ 감지 불가 (2쌍, 필터링) | ✅ **zoom_in** (4쌍=20프레임) |
| 790~800 | zoom_out (10프레임) | ❌ 감지 불가 (1쌍) | ✅ **zoom_out** (2쌍=10프레임) |

`-5lAx7309cE` 800~850프레임 검증:

| 프레임 구간 | 실제 모션 | step=5 + smooth 결과 |
|-----------|---------|-------------------|
| 800~850 | zoom_in | ✅ **zoom_in** (5/5 쌍) |

#### 최종 파라미터

| 파라미터 | 값 | 의미 |
|---------|---|------|
| `step` | 5 | 프레임 간격 (0.2s @ 25fps) |
| `_MIN_MAG` | 3.0 px | static/motion 경계 |
| `_ZOOM_THRESH` | 0.05 | zoom 분류 임계값 |
| `_PAN_THRESH` | 5.0 px | pan 분류 임계값 |
| `_ROT_THRESH` | 0.015 | rotation 분류 임계값 |
| `_SPIKE_FACTOR` | 3.0× | 스파이크 감지 배율 |
| `_SPIKE_MIN_MAG` | 15.0 px | 스파이크 최소 크기 |
| `min_frames` | 10 | 레이블 최소 지속 프레임 수 |

---

## 3. 방법 비교

| | 실험 1 (컷별) | 실험 2 (step=10) | 실험 3 (step=5 + smooth) |
|---|---|---|---|
| 시간 해상도 | 컷 단위 (가변) | 0.4s | **0.2s** |
| 스파이크 처리 | 컷 경계 = 스파이크 없음 | ❌ 없음 | ✅ 중앙값 기반 보간 |
| 분류 방식 | 임계값 단일 레이블 | 없음 (raw) | 임계값 + temporal filter |
| 단기 이벤트 감지 | ❌ (1s 미만 불가) | △ (0.4s 미만 불가) | ✅ (0.2s = 5프레임) |
| 컷 내부 변화 | ❌ | ✅ | ✅ |
| 연산량 (영상당) | 낮음 | 중간 | **높음** (2× step=10) |

---

## 4. 향후 개선 방향

- **`motion` 레이블 세분화**: `flow_var`가 높은 경우 피사체 로컬 모션, 낮은 경우 약한 카메라 글로벌 모션으로 구분
- **컷 경계 정밀 감지**: 현재 mean_mag 스파이크 기반 → shot_detect와 통합하여 컷 프레임 정확히 마킹
- **GMA 활용**: `raft_small` 대신 `raft_large` (GMA 포함)를 step=5에 적용 → 컷 경계 근처 흐름 품질 향상
- **Sintel/KITTI 임계값 재보정**: 현재 임계값은 광고 영상(25fps) 기준 수동 튜닝 → 더 많은 샘플로 검증 필요
