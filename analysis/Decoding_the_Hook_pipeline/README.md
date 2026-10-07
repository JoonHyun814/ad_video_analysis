# Decoding the Hook — MLLM-VAU 재현 (훅 기법 추출 · 토픽화 단계)

논문 *Decoding the Hook: A Multimodal LLM Framework for Analyzing the Hooking Period of Video Ads* (Zhang et al., 2026) 의
프레임워크 중 **CPI 예측(GBDT/PDP) 이전 단계**까지 재현한다.

- 훅(첫 3초)에 어떤 기법이 쓰였는가 → MLLM `methodology` / `rationale` → BERTopic 토픽(기법 카테고리)
- 각 기법의 대표값 → 토픽별 상위 10개 키워드(c-TF-IDF), 대표 문서, 영상별 토픽 분포 + 음향 피처 10종

논문과 다른 점은 아래 두 가지뿐이다 (요청 사항).

| 항목 | 논문 | 본 구현 |
|------|------|---------|
| 영상 입력 | Meta 내부 광고 데이터 | 기존 프로젝트 `pipeline/video_loader.get_video_info` 로 `video_uploads.id` 조회 |
| MLLM | Llama Multimodal (버전 미기재) | `claude -p` / `codex exec` / Qwen2.5-VL 로컬 모델 (`--llm_backend qwen_vl`) |

## 실행

워크스페이스 `.venv` 사용, 이 폴더에서 실행한다.

```powershell
cd C:\Analysis_workspace\ad_video_analysis\ad_video_analysis\Decoding_the_Hook_pipeline
$py = "..\..\.venv\Scripts\python.exe"

# 1) 영상별 추출 (video_id / 범위 / 파일 경로)
& $py -m hook_pipeline.cli extract --video_id 1
& $py -m hook_pipeline.cli extract --video_ids 1-30 --llm_backend codex --sampling random
& $py -m hook_pipeline.cli extract --video_path D:\ads\sample.mp4

# 로컬 Qwen2.5-VL 사용 (GPU 필요, API 키 불필요)
& $py -m hook_pipeline.cli extract --video_id 1 --llm_backend qwen_vl
& $py -m hook_pipeline.cli extract --video_ids 1-30 --llm_backend qwen_vl --qwen_model_path D:\models\Qwen2.5-VL-7B-Instruct

# 2) 코퍼스 토픽화 (output/ 아래 모든 영상, 또는 --video_ids 로 한정) — 최소 10개 문서 필요
& $py -m hook_pipeline.cli topics
& $py -m hook_pipeline.cli topics --video_ids 1-30 --nr_topics 5,8,10 --min_cluster_size 3
```

### extract 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` / `--video_ids` / `--video_path` | — | 셋 중 하나 (기존 `pipeline/cli.py` 와 동일 문법) |
| `--out_dir` | `output/` | 결과 루트, 하위에 `<video_id>/` 생성 |
| `--llm_backend` | `claude` | `claude` (`claude -p`) / `codex` (`codex exec`) / `qwen_vl` (로컬 Qwen2.5-VL) |
| `--llm_model` | CLI 기본값 | `claude --model` / `codex -m` 에 전달 (`qwen_vl` 에는 무시됨) |
| `--qwen_model_path` | `MODEL_ROOT/Qwen2.5-VL-7B-Instruct` | `[qwen_vl]` 로컬 모델 디렉토리 (`env/model.env` 의 `MODEL_ROOT` 기본값) |
| `--sampling` | `keyframe` | `keyframe` (SSIM) / `random` |
| `--num_frames` | 8 | [random] m (논문 baseline 의 8프레임과 동일) |
| `--alpha` | 0.5 | [keyframe] τ = α·max(D) |
| `--min_interval` | 8 | [keyframe] 키프레임 간 최소 간격 Δt (프레임 수, 논문 미기재 → 30fps 기준 약 0.27초) |
| `--hook_sec` | 3.0 | 훅 구간 길이 |
| `--asr_model` / `--asr_language` | `medium` / `ko` | faster-whisper, `auto` 면 언어 자동 감지 |

### topics 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--nr_topics` | `10,13,15,17,20` | perplexity 로 비교할 토픽 수 후보 (논문 각주 6: "a few choices" 중 최적 → 17) |
| `--min_cluster_size` | 10 | HDBSCAN (BERTopic 기본값). 영상 수가 적으면 낮춘다 |
| `--embedding_model` | `all-MiniLM-L6-v2` | BERTopic 기본 임베딩 |

## 논문 대응

| 논문 | 파일 | 구현 |
|------|------|------|
| 3.2 Random sampling | `frame_sampling.py` | K=round(fps·3) 프레임 중 m 개 무작위 비복원 추출 |
| 3.2 Key frame selection | `frame_sampling.py` | D_i = 1−SSIM(I_i, I_{i+1}), τ = α·max(D), {I_i \| D_i > τ}, 최소 간격 Δt. SSIM 은 360p 그레이스케일로 계산, 저장은 원본 해상도 |
| 3.2 ASR | `hook_audio.py` | 첫 3초 오디오를 faster-whisper 로 전사 → 프롬프트의 `{ad body text}` |
| 3.3 Vision Design Methodology Extractor | `mllm.py` | 논문 프롬프트 원문 그대로 + 프레임 전달 안내문만 앞에 추가. 제목 = `original_filename` |
| 3.3 BERTopic | `topics.py` | 문서 = `"methodology: rationale"`. UMAP(5d, cosine) → HDBSCAN → CountVectorizer(english) → c-TF-IDF, top 10 words |
| 각주 6 perplexity 선택 | `topics.py` | 후보 nr_topics 별 학습 → p(w\|d)=Σθ·φ (θ: approximate_distribution, φ: 정규화 c-TF-IDF) 로 perplexity 계산 → 최소 선택 |
| 3.4 Audio Attributes (librosa) | `acoustic.py` | dB, jitter, tempo, DDP, pitch max/min/mean, power, peak, shimmer (10종) |
| 3.5 Predictor (GBDT), PDP | — | **미구현** (CPI 데이터 없음). `hook_features.csv` 가 GBDT 입력 직전 형태 |

### 해석상 선택한 부분 (논문에 명시 없음)

- **토픽 이름**: 논문 Table 3 의 "Interactive content" 같은 이름의 산출 방법이 없어, 토픽 소속 문서의 `methodology` 최빈값을 라벨로 쓴다. 키워드(`top_words`)는 BERTopic 출력 그대로.
- **jitter / shimmer / DDP**: librosa 에는 없는 지표라 Praat 정의(연속 주기·진폭 차이의 평균 / 평균)를 pyin f0 프레임과 RMS 프레임에 적용한 근사값이다.
- **키프레임이 하나도 없을 때**(정지 화면, max D = 0): 첫 프레임 1장 사용.
- 논문 Table 3 의 토픽 번호가 산업군마다 다른 것으로 보아 산업군별로 BERTopic 을 따로 돌린 것으로 보인다. 같은 효과를 내려면 `topics --video_ids` 로 산업군별 영상만 지정해 실행한다.

## 출력 구조

```
output/
  <video_id>/
    frames/frame_032_1.07s.jpg   선택된 훅 프레임 (원본 해상도)
    frames.json                  샘플링 전략·K·fps·τ·SSIM 차이 D
    hook_audio.wav               첫 3초 오디오 (22.05kHz mono)
    asr.json                     훅 구간 전사
    acoustic_features.json       음향 피처 10종 (오디오 없음/무음 → null)
    hook_analysis.json           title, body, methodology, rationale (실패 시 error)
  _topics/
    topic_info.json              토픽별 label · count · top_words(가중치) · representative_docs · methodology 분포
    perplexity_scores.json       후보별 실제 토픽 수 · perplexity, 선택값
    hook_features.csv            영상별 대표 기법(topic, topic_label) + 토픽 분포(topic_k) + 음향 피처 10종
    bertopic_model/              BERTopic.load() 로 재사용 가능
```

## 파일 구성

| 파일 | 역할 |
|------|------|
| `hook_pipeline/cli.py` | argparse 진입점 (`extract`, `topics`) |
| `hook_pipeline/cli_runners.py` | 서브커맨드 실행, video_id 목록 처리 |
| `hook_pipeline/config.py` | 출력 경로, 상위 프로젝트 경로(기본: 이 폴더의 상위 = `ad_video_analysis/`, `LEGACY_PROJECT_ROOT` 환경변수로 변경 가능), 상수 |
| `hook_pipeline/video_source.py` | video_id → 경로·제목 (기존 `video_loader` 재사용) |
| `hook_pipeline/frame_sampling.py` | random / SSIM keyframe 샘플링, 프레임 저장 |
| `hook_pipeline/hook_audio.py` | 훅 오디오 추출, Whisper ASR |
| `hook_pipeline/acoustic.py` | librosa 음향 피처 |
| `hook_pipeline/mllm.py` | 논문 프롬프트, `claude -p` / `codex exec` / Qwen2.5-VL 로컬 모델 호출 |
| `hook_pipeline/extract.py` | 영상 1개 처리 흐름 |
| `hook_pipeline/topics.py` | BERTopic 학습, perplexity 계산·선택 |
| `hook_pipeline/topics_report.py` | 코퍼스 로드, 토픽 대표값·피처 테이블 저장 |

## 주의

- 기존 프로젝트의 `env/db.env`, `env/dir.env` 를 그대로 읽는다 (자격증명 복사 없음).
- BERTopic 은 문서 수가 적으면 토픽이 거의 안 나뉜다. 논문은 산업군당 1만~15만 개 영상을 썼다. 수십 개 수준이면 `--min_cluster_size` 를 3~5 로 낮추고 결과는 참고용으로 본다.
- `codex exec` 는 `--sandbox read-only --skip-git-repo-check` 로 실행하고 프롬프트는 stdin 으로 넘긴다 (Windows `.cmd` 래퍼에서 인자 깨짐 방지).
