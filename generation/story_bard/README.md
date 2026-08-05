# generation/story_bard 모듈

`C:\Analysis_workspace\ad_video_analysis\story_board` 프로젝트를 이 프로젝트로 복사·이식한
독립 도구다. 소스 프로젝트는 **import 하지 않으며 수정하지도 않는다** — `story_board/` 폴더가
삭제되어도 이 폴더만으로 동일하게 동작한다.

기존 `generation/`(G1~G6)·`generation/v5_m0_m3`(M0~M9) 파이프라인과는 **별개의 독립 도구**다 —
서로 참조하지 않는다. 스토리보드 자리표시자(placeholder) HTML을 입력받아 Codex CLI로 완성
비주얼(이미지 생성·삽입·렌더링)을 만드는 후처리 단계로, M0~M9 의 `cli_storyboard.py` 산출물
([`../AITIVE_스토리보드_데이터필드.html`](../AITIVE_스토리보드_데이터필드.html) 양식을 채운 결과)이나
그 밖의 어떤 스토리보드 HTML에도 적용할 수 있다.

완성 HTML·PNG 렌더링에 더해, **Seedance 2.0(image-to-video) 핸드오프 산출물**
(`storyboard-grid.png` + `prompt.txt`)도 함께 생성한다 — 아래 "Seedance 핸드오프" 절 참고.
프롬프트 작성 방식은 [`../docs/GPT_Image2_Seedance2_Workflow.md`](../docs/GPT_Image2_Seedance2_Workflow.md)와
`../docs/` 아래 실사용 예시(ASMR 요리 영상, 지브리풍 애니메이션)의 구성(연출 노트형 문단 — 스타일
앵커 → 컷 순서 나열 → 오디오 지시 → 네거티브 프롬프트)을 따른다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run_storyboard_codex.py` | 진입점 — 입력 HTML을 Codex CLI(`codex exec`)에 넘겨 완성 HTML·PNG·에셋·참고자료·ZIP을 생성하고 결과물을 검증 |
| `storyboard_image_layout.py` | Codex가 이미지 삽입 후 호출하는 보조 도구 — 매니페스트 기준으로 이미지를 잘림 없는 비율로 재생성하고 HTML 슬롯에 적응형 aspect-ratio를 적용 |

두 파일 모두 표준 라이브러리만 사용하며(`storyboard_image_layout.py`는 추가로 `ffmpeg`/`ffprobe`가
`PATH`에 필요) 서로 같은 폴더에 있는 것만 가정한다(`run_storyboard_codex.py`가
`Path(__file__).with_name("storyboard_image_layout.py")`로 형제 파일을 참조).

## 요구 사항

- Codex CLI 설치·로그인 (`codex` 명령이 `PATH`에 있거나 `--codex_bin`으로 지정)
- `storyboard_image_layout.py` 실행 시 `ffmpeg` (`PATH`에 필요)

## 사용법

```bash
python generation/story_bard/run_storyboard_codex.py \
    --input_html <스토리보드 HTML 경로> \
    --output_dir <결과 저장 폴더> \
    [--reference_dir <제품 참조 이미지 폴더>] \
    [--model <Codex 모델>] \
    [--codex_bin <codex 실행 파일>] \
    [--extra_instruction "<추가 지시사항>"] \
    [--keep_session] \
    [--dry_run]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--input_html` | (필수) | 입력 HTML 파일 경로 |
| `--output_dir` | (필수) | 완성 결과를 저장할 폴더 |
| `--reference_dir` | — | 제품 참조 이미지 폴더 (오타 호환 별칭: `--refernece_dir`) |
| `--model` | Codex 기본 설정 | Codex 실행에 사용할 모델 |
| `--codex_bin` | 자동 탐색 | Codex 실행 파일 경로/명령 이름 |
| `--extra_instruction` | `""` | 기본 프롬프트 뒤에 추가할 지시사항 |
| `--keep_session` | `False` | Codex 세션 기록 유지 (기본은 `--ephemeral`) |
| `--dry_run` | `False` | 실행하지 않고 명령/프롬프트만 출력 |
| `--unsafe_bypass_sandbox` | `False` | Codex를 `--sandbox workspace-write` 대신 `--dangerously-bypass-approvals-and-sandbox` 로 실행. 호출자 프로세스 자체가 이미 샌드박스 안이라 Codex의 Windows 샌드박스가 중첩되어 `windows sandbox: timed out ... connecting runner pipe-in` 으로 멈출 때만 사용(예: 에이전트 도구 안에서 이 스크립트를 실행하는 경우) — Codex의 파일 쓰기 범위 제한이 사라지므로 일반 실행에서는 켜지 않는다 |

### 산출물 (`--output_dir` 하위)

- `completed.html`, `completed.png` — 완성 스토리보드 문서와 그 전체 페이지 캡처
- `storyboard-grid.png` — Seedance 업로드용. 문서 UI(라벨·기입선·표) 없이 컷 이미지만 촬영
  순서대로 이어붙인 단일 그리드 이미지
- `prompt.txt` — Seedance 2.0에 그대로 붙여넣는 영상 생성 프롬프트 (연출 노트형 문단)
- `assets/` — 생성 이미지
- `references/`, `references/sources.json` — 조사 과정에서 참고한 실제 자료와 메타데이터
- `completed-package.zip` — 위 산출물을 묶은 ZIP
- `image-layout.json`, `image-layout-report.json` — `storyboard_image_layout.py` 매니페스트/리포트 (Codex가 렌더링 전에 생성·실행)
- `codex-last-message.txt` — Codex 마지막 응답

실행이 끝나면 위 필수 산출물의 존재 여부, `prompt.txt`가 비어 있지 않은지,
`sources.json`/ZIP 내용을 자동 검증하며, 실패 시 비정상 종료 코드와 함께 문제 목록을
stderr에 출력한다.

## Seedance 핸드오프

`run_storyboard_codex.py`가 Codex에 전달하는 프롬프트에는 `storyboard-grid.png`·`prompt.txt`를
만들라는 별도 지시(`MANDATORY SEEDANCE 2.0 HAND-OFF PACKAGE`)가 포함돼 있다. Codex는 완성
HTML의 다음 정보를 읽어 `prompt.txt`를 합성한다.

1. **도입부** — 사양(화면비·길이·씬/컷 수)과 메타데이터(장르·브랜드 톤·시대·타깃)를 요약
2. **스타일/일관성 앵커** — 인물·제품 외형, 장소, 키라이트 방향, 조명 세팅·무드 키워드
3. **시퀀스** — 컷을 순서대로 훑어 화면 묘사 + Size/Angle/Cut/렌즈를 시간 흐름이 드러나게 연결
4. **오디오** — 내레이션 또는 "VO 없음"이면 장면 기반 ASMR 사운드 디자인으로 대체
5. **네거티브 프롬프트** — 제품 레퍼런스의 금지 항목 + "문자·자막·로고·워터마크 없음" 원칙

두 파일을 얻은 뒤에는 수동으로 Seedance 2.0(예: Hailuo `Seedance 2.0` 모드)에
`storyboard-grid.png`를 업로드하고 `prompt.txt` 내용을 영상 프롬프트로 붙여넣는다 — 이 도구는
Seedance API를 직접 호출하지 않는다.

## storyboard_image_layout.py 단독 실행

Codex가 이미지 삽입 후 호출하지만, 필요하면 직접 실행할 수도 있다.

```bash
python generation/story_bard/storyboard_image_layout.py \
    --html <output_dir>/completed.html \
    --manifest <output_dir>/image-layout.json \
    --report <output_dir>/image-layout-report.json
```

매니페스트(`--manifest`)는 경로가 매니페스트 파일 기준 상대 경로인 `assets` 배열이다.

```json
{
  "assets": [
    {"output": "assets/character-front.jpg", "source": "assets/master-character-front.png", "category": "character"},
    {"output": "assets/story-01.jpg", "source": "assets/master-story-01.png", "category": "storyboard"},
    {"output": "assets/set-topdown.svg", "category": "environment"}
  ]
}
```

카테고리별 출력 비율:

| 카테고리 | 비율 |
|----------|------|
| `character`, `character-detail` | 4:5 |
| `product`, `product-use`, `environment`, `lighting` | 1:1 |
| `storyboard`, `default` | 6:5 |

`source`가 있는 래스터 이미지는 중립 단색 배경 위 92% 안전 영역 안에 원본 전체를 배치해
재생성한다(확대·블러 복제 없음). `source` 없는 SVG 항목도 HTML 슬롯에는 동일하게 적응형
비율이 적용된다. 매니페스트의 `output`은 `.slot.has-image` 안의 `<img src>`와 정확히 일치해야
하며, 일치하지 않으면 종료 코드 2로 실패해 렌더링 파이프라인이 미처리 슬롯을 그대로 내보내지
않도록 한다.
