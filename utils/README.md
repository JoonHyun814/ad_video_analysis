# utils 모듈

프로젝트 전반에서 재사용하는 헬퍼. **새 파일에서 LLM 호출, JSON 파싱, env 로딩이 필요하면 반드시 아래 모듈을 import 해서 쓴다.** 로컬에 복붙하지 않는다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `env_loader.py` | `KEY=VALUE` 형식의 `.env` 파일 파싱 |
| `json_utils.py` | LLM 응답에서 JSON 안전 파싱 |
| `io_checks.py` | 파이프라인 입력 JSON 의 존재·`parse_failed` 검증 |
| `llm_caller.py` | Claude CLI / Codex CLI 호출 |
| `claude_api_caller.py` | Anthropic Claude API 호출 (텍스트, CLI 세션 불필요) |
| `gemini_caller.py` | Gemini API 호출 (텍스트 / 비전) |
| `openai_caller.py` | OpenAI API 호출 (텍스트 / 비전) |
| `qwen_vl_caller.py` | Qwen2.5-VL 로컬 모델 호출 (단일·다중 이미지) |
| `llm_dispatch.py` | `backend` 인자로 위 넷+로컬을 일괄 디스패치 |

## `env_loader.py`

| 함수 | 설명 |
|------|------|
| `load_env(path) -> dict[str, str]` | `.env` 파일을 파싱해 딕셔너리로 반환 (주석·따옴표 처리) |

```python
from utils.env_loader import load_env
db = load_env("env/db.env")
```

## `json_utils.py`

| 함수 | 설명 |
|------|------|
| `parse_json(text: str) -> dict` | LLM 응답에서 JSON 을 파싱한다. 마크다운 펜스 제거 → `raw_decode`(후행 텍스트) → 괄호 스택 복구 순으로 시도하고, 모두 실패하면 `{"error": "parse_failed"}` 반환 |

```python
from utils.json_utils import parse_json
```

## `io_checks.py`

| 함수 | 설명 |
|------|------|
| `is_parse_failed(data) -> bool` | dict/list 안에 `error == "parse_failed"` 항목이 있는지 검사 |
| `require_exists(path, label) -> None` | 파일 미존재 시 `SystemExit("[오류] {label} 없음: ...")` |
| `require_valid_json(path, label) -> Any` | 존재 + JSON 파싱 + parse_failed 미포함 검증 후 데이터 반환 |
| `load_optional_valid(path, label, default) -> Any` | 선택 입력. 없으면 `default`, 있으면 `require_valid_json` 적용 |

```python
from utils.io_checks import require_valid_json, load_optional_valid
scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")
stt = load_optional_valid(video_dir / "stt.json", "stt", default=[])
```

## `llm_caller.py`

| 함수 | 설명 |
|------|------|
| `call_claude(prompt, timeout=300, allowed_tools=None, mcp_config=None) -> dict` | Claude CLI 호출. stdout 파일 출력(PIPE 버퍼 방지) + 529 과부하 자동 재시도. `allowed_tools=["WebSearch"]` 처럼 지정하지 않으면 헤드리스 `-p` 모드는 WebSearch 등 권한 필요 툴을 기본 거부한다. `mcp_config="<path>/.mcp.json"` 을 주면 `--mcp-config` 로 그 설정의 MCP 서버 도구도 쓸 수 있다(도구명을 `allowed_tools` 에도 넣어야 함) |
| `call_codex(prompt, model=None, timeout=300) -> dict` | Codex CLI 호출. `-o` 파일 출력 방식 |

```python
from utils.llm_caller import call_claude, call_codex
```

> **예외**: `pipeline/cast_analysis.py` 는 `--add-dir` 플래그, `cast_analysis_codex.py` 는 `-i` 이미지 플래그가 필요해 공통 모듈을 사용하지 않는다.

## `claude_api_caller.py`

API 키는 `env/api.env` 의 `ANTHROPIC_API_KEY` 또는 동명 환경변수에서 읽는다. `llm_caller.call_claude`(CLI)와
달리 로그인된 `claude` 세션이 필요 없다 — API 키만 있으면 서버·배치 프로세스에서도 호출할 수 있다
(`generation/v5_m0_m3/llm_adapter.py` 의 `--llm_backend api` 와 같은 방식, 별도 재구현).

| 함수 | 설명 |
|------|------|
| `call_claude_api(prompt, model=DEFAULT_MODEL, timeout=300) -> dict` | Anthropic API 텍스트 호출(스트리밍). 529 과부하 자동 재시도 |
| `DEFAULT_MODEL` | `"claude-sonnet-5"` |

```python
from utils.claude_api_caller import call_claude_api
```

## `gemini_caller.py`

API 키는 `env/api.env` 의 `GEMINI_API_KEY` 또는 동명 환경변수에서 읽는다.

| 함수 | 설명 |
|------|------|
| `call_gemini(prompt, model=DEFAULT_MODEL, timeout=300) -> dict` | Gemini API 텍스트 호출. 429 과부하 자동 재시도 |
| `call_gemini_with_images(prompt, image_paths, model=DEFAULT_MODEL, timeout=300) -> dict` | Gemini Vision API 호출 (이미지 바이트 인라인 전송). JSON dict 반환 |
| `call_gemini_with_images_raw(prompt, image_paths, model=DEFAULT_MODEL, timeout=300) -> str` | Gemini Vision API 호출. 원시 텍스트 반환 (list 파싱 등 직접 처리 시 사용) |
| `DEFAULT_MODEL` | `"gemini-2.5-flash-lite"` |

```python
from utils.gemini_caller import call_gemini, call_gemini_with_images, DEFAULT_MODEL
```

## `openai_caller.py`

API 키는 `env/api.env` 의 `OPENAI_API_KEY` 또는 동명 환경변수에서 읽는다.

| 함수 | 설명 |
|------|------|
| `call_openai(prompt, model=DEFAULT_MODEL, timeout=300) -> dict` | OpenAI API 텍스트 호출. Rate limit 자동 재시도 |
| `call_openai_with_images(prompt, image_paths, model=DEFAULT_MODEL, timeout=300) -> dict` | OpenAI Vision API 호출 (이미지 base64 인라인). JSON dict 반환 |
| `get_token_usage() -> dict` | 누적 토큰 사용량 반환 (`input`/`output`/`thinking`) |
| `reset_token_usage()` | 토큰 카운터 초기화 |
| `DEFAULT_MODEL` | `"gpt-4o-mini"` |

```python
from utils.openai_caller import call_openai, call_openai_with_images, DEFAULT_MODEL
```

## `qwen_vl_caller.py`

모델 경로는 `env/model.env` 의 `MODEL_ROOT`/`Qwen2.5-VL-7B-Instruct` 또는 호출 시 명시적으로 지정한다.
`TRANSFORMERS_OFFLINE=1` 로 강제해 로컬 파일만 사용한다.

| 클래스/함수 | 설명 |
|-------------|------|
| `QwenVLModel(model_path)` | 모델 로더. `infer(image, prompt, max_new_tokens=32)` (단일 이미지), `infer_multi(images, prompt, max_new_tokens=512)` (다중 이미지 또는 텍스트만) |
| `InferenceResult` | `text`, `input_tokens`, `output_tokens`, `latency_ms` |
| `call_qwen_vl(prompt, image_paths, model_path, max_new_tokens)` | 모델을 일회 로드해 추론하고 `{"text": ..., "input_tokens": ..., "output_tokens": ..., "latency_ms": ...}` 반환. 배치에는 `QwenVLModel` 직접 사용 |
| `DEFAULT_MODEL_NAME` | `"Qwen2.5-VL-7B-Instruct"` |

```python
# 단일 이미지 (pikk_tagging 방식)
from utils.qwen_vl_caller import QwenVLModel
model = QwenVLModel("D:/models/Qwen2.5-VL-7B-Instruct")
result = model.infer(pil_image, prompt)

# 다중 이미지 (hook pipeline 방식)
result = model.infer_multi([img1, img2, img3], prompt)

# 일회성 호출
from utils.qwen_vl_caller import call_qwen_vl
out = call_qwen_vl(prompt, image_paths=["a.jpg", "b.jpg"])
```

## `llm_dispatch.py`

| 함수 | 설명 |
|------|------|
| `call_llm(prompt, *, backend="claude", gemini_model="", codex_model=None, claude_api_model="", qwen_model_path=None, timeout=300) -> dict` | `backend` 인자(`claude`/`claude_api`/`codex`/`gemini`/`qwen_vl`)에 따라 위 호출을 일괄 라우팅. `qwen_vl` 은 텍스트 전용; 이미지가 필요하면 `qwen_vl_caller.QwenVLModel` 직접 사용 |

```python
from utils.llm_dispatch import call_llm
result = call_llm(prompt, backend=args.llm_backend, gemini_model=args.gemini_model)
result = call_llm(prompt, backend="qwen_vl", qwen_model_path="D:/models/Qwen2.5-VL-7B-Instruct")
```
