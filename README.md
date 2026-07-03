# ad_video_analysis

광고 영상 분석·평가·재생성 파이프라인 모음.

영상 → 컷·STT·OCR·BGM → 시나리오 → 카테고리 벡터 DB → 평가 → 학습 데이터셋 → 신규 시나리오 생성까지 전체 흐름을 단일 저장소에서 다룬다.

## 환경 설정

두 가지 방법 중 하나를 선택한다.
- **A. Docker** — PyTorch + CUDA + 모든 시스템 패키지가 한 번에 갖춰져 재현이 쉽다. GPU 자원이 있는 서버 권장.
- **B. venv** — 로컬 Windows 개발용. `setup_venv.ps1` 한 번으로 가상환경을 만든다.

공통 사전 작업: `env/` 디렉토리에 자격증명·경로 파일 배치 (`db.env`, `dir.env`, `api.env`, `python.env`).

모든 CLI 는 `ad_video_analysis/` 디렉토리에서 실행한다 (`python -m <package>.cli ...`).

### A. Docker 사용법

`Dockerfile` 은 `ad_video_analysis/` 안에 있다. 베이스: `pytorch/pytorch:2.12.0-cuda12.6-cudnn9-devel`. Claude Code CLI, Codex CLI, 프로젝트 Python 의존성, TransNetV2 가중치까지 한 이미지에 들어간다.

```bash
# 1) 이미지 빌드 (build context = ad_video_analysis/)
cd ad_video_analysis
docker build -t ad-video-analysis .

# 2) 컨테이너 실행 — 코드·env·출력 디렉토리 마운트, GPU 전달
docker run --rm -it --gpus all \
    -v "$(pwd)":/workspace/ad_video_analysis \
    -v "$(pwd)/../output":/workspace/output \
    -w /workspace/ad_video_analysis \
    ad-video-analysis

# 컨테이너 안에서
python -m pipeline.cli --video_id 349
```

**패키지를 추가/변경할 때**:
1. 컨테이너에서 `pip install <패키지>` 로 동작 확인
2. `Dockerfile` 의 `pip install` 블록에 패키지명 추가
3. 루트 `CLAUDE.md` 의 패키지 표에 행 추가 (패키지명·용도)

### B. venv 사용법 (Windows)

```powershell
# 1) env/python.env 의 PYTHON_PATH / VENV_PATH 확인
#    (예: PYTHON_PATH="C:\Python311\python.exe", VENV_PATH="C:\Analysis_workspace\ad_video_analysis\.venv")

# 2) 가상환경 생성 + 핵심 패키지 설치
.\setup_venv.ps1

# 3) 활성화
. C:\Analysis_workspace\ad_video_analysis\.venv\Scripts\Activate.ps1

# 4) 실행
python -m pipeline.cli --video_id 349
```

`setup_venv.ps1` 은 최소 의존성(mysql/opencv/scenedetect/easyocr + chromadb/sentence-transformers/tf-keras)만 설치한다. TensorFlow·whisper-diarization·NeMo 등 무거운 패키지는 `setup_venv_full.ps1`(프로젝트 루트) 을 참고해 추가로 설치한다.

**패키지를 추가/변경할 때**: `setup_venv.ps1` 의 `pip install` 라인에도 같은 패키지를 반영해야 다음번 환경 재구성 시 누락되지 않는다.

## 모듈 인덱스

| 모듈 | 역할 | 문서 |
|------|------|------|
| `pipeline/` | 영상 → 컷·OCR·STT·BGM·시나리오 12단계 분석 | [pipeline/README.md](pipeline/README.md) |
| `evaluation/` | 시나리오 평가 + 카테고리 메타데이터 추출 + 벡터 DB 적재 | [evaluation/README.md](evaluation/README.md) |
| `train_pipeline/` | Qwen VL 학습 데이터셋 빌드 + 학습 | [train_pipeline/README.md](train_pipeline/README.md) |
| `mapping_pipeline/` | 외부 영상 + 시나리오 텍스트의 cut-scene 매핑 (CLI / FastAPI / Gradio) | [mapping_pipeline/README.md](mapping_pipeline/README.md) |
| `generation/` | 브리프·시나리오 생성 (단일 단계 / M1~M7 풀 파이프라인) | [generation/README.md](generation/README.md) |
| `db/` | MySQL 조회 + ChromaDB 벡터 검색·재임베딩 | [db/README.md](db/README.md) |
| `utils/` | 공용 헬퍼 (LLM 호출·JSON 파싱·환경변수 로딩) | [utils/README.md](utils/README.md) |
| `tools/` | 서드파티 통합 (whisper-diarization 등) | — |

## 배치 실행 — `run_batch.py`

여러 영상에 대해 동일 CLI 를 반복 실행한다. `--` 뒤의 인자는 그대로 대상 CLI 로 전달된다.

```bash
# pipeline 1~10번
python run_batch.py --video_ids 1-10 --module pipeline

# evaluation: 1·3·5번 시나리오 평가
python run_batch.py --video_ids 1,3,5 --module evaluation -- --scenario_evaluation

# category: 디렉토리 스캔으로 89·100~105번 적재
python run_batch.py --video_ids 89,100-105 --module category --data_dir output/product_plan/claude \
    -- --category_analysis --load_vector

# concept: 컨셉 추출 + 설득력 1~5점 채점, 디렉토리 스캔으로 89~105번
python run_batch.py --start_id 89 --module concept --data_dir output/product_plan/claude
```

옵션: `--interval N` (영상 사이 대기 초), `--start_id N` (이후 모든 ID 자동 수집).

## 분석 결과 점검 — `check_analysis.py`

`video_id` 별 분석 결과의 누락·파싱 실패를 그룹화한다.

```bash
python check_analysis.py --base_dir output/codex --mode scenario   # 기본
python check_analysis.py --base_dir output/codex --mode brief
```

## 입력 파일 검증 — `utils/io_checks.py`

각 파이프라인 단계는 이전 단계의 산출 JSON 을 입력으로 받는다. 파일이 없거나, JSON 파싱이 깨졌거나, `parse_failed` 항목이 섞여 있으면 하류 단계가 조용히 깨진 데이터를 소비하므로 CLI 진입점에서 미리 막는다.

**새 기능·CLI 진입점을 추가할 때는 다음 규칙을 지킨다.**

- 필수 입력은 `utils.io_checks.require_valid_json(path, label)` 으로 로드한다. 미존재·JSON 파싱 실패·`parse_failed` 시 `SystemExit("[오류] {label} ...")` 로 즉시 중단된다.
- 선택 입력은 `load_optional_valid(path, label, default)` 으로 로드한다. 없으면 `default`, 있으면 동일 검증이 적용된다.
- 외부 파일 경로(예: `--video_path`)는 `require_exists(path, label)` 로 존재만 확인한다.
- 직접 `Path.read_text(...)` + `json.loads(...)` 패턴을 새로 추가하지 않는다. 이미 검증된 파일을 다시 읽는 경우에도 헬퍼를 거치는 것이 일관적이다.

자세한 함수 시그니처와 사용 예시는 [`utils/README.md`](utils/README.md) 참고.
