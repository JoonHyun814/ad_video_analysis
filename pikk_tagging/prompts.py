"""컷 단위 기법 태깅·검증 프롬프트. 기존 태그·제목·설명은 넣지 않는다 (앵커링 방지)."""
from pikk_tagging.frame_select import FrameList
from pikk_tagging.vocab import Technique

_TAG_PROMPT = """역할: 광고 영상의 한 컷에서 [{axis_label}] 관련 촬영·연출 기법을 분류한다.

입력: 이 컷의 시간순 프레임 {n}장 (첨부 이미지 순서 = 아래 번호). 구간 {start:.2f}~{end:.2f}초.
{frame_lines}
{ocr_block}
[규칙]
1. 아래 [어휘]의 id 만 tags 에 쓴다. 어휘에 없지만 화면에 분명히 있는 기법은 proposals 에 적는다.
2. 화면에서 직접 보이는 것만 근거로 한다. 추측, 광고 맥락, 영상 밖 지식은 쓰지 않는다.
3. 확신이 없으면 생략한다. tags 가 빈 배열이어도 정상이다. 정의의 '제외' 조건에 해당하면 붙이지 않는다.
4. 각 태그마다 근거 프레임 번호(frames)와 그 프레임에서 관찰한 내용 한 줄(evidence), confidence(high|medium)를 쓴다. 확신이 낮으면 태그를 생략한다.
5. 실존 인물을 식별하거나 이름을 쓰지 않는다. 성별·나이·외모 평가는 근거에 쓰지 않는다.
6. tags 는 최대 {max_tags}개.

[어휘] (나열 순서에 의미 없음)
{vocab_block}

마크다운 없이 순수 JSON만 출력. 키 순서를 지킨다 (observation 먼저).
{{"observation": "프레임에서 보이는 촬영·조명·화면 구성을 객관적으로 2문장 이내",
  "tags": [{{"id": "<어휘 id>", "frames": [<프레임 번호>], "evidence": "<관찰 한 줄>", "confidence": "high|medium"}}],
  "proposals": [{{"term": "<어휘에 없는 기법명>", "frames": [<프레임 번호>], "evidence": "<관찰 한 줄>"}}]}}"""

_VERIFY_PROMPT = """역할: 광고 영상 한 컷의 프레임을 보고 특정 기법이 실제로 나타나는지 엄격하게 판정한다.

입력: 시간순 프레임 {n}장 (첨부 이미지 순서 = 아래 번호). 구간 {start:.2f}~{end:.2f}초.
{frame_lines}

[판정 대상] {tech_id}
{tech_block}

[규칙]
- 화면에서 직접 보이는 것만 근거로 한다. 정의의 '제외' 조건에 해당하거나 확신이 없으면 present=false.
- present=true 이면 근거 프레임 번호(frames)를 반드시 쓴다.
- 실존 인물을 식별하거나 이름을 쓰지 않는다.

마크다운 없이 순수 JSON만 출력.
{{"present": true|false, "frames": [<프레임 번호>], "reason": "<관찰 한 줄>"}}"""


def _frame_lines(frames: FrameList) -> str:
    return "\n".join(f"[{i}] {t:.2f}초" for i, (t, _) in enumerate(frames, 1))


def _tech_block(tech: Technique) -> str:
    lines = [f"정의: {tech.definition}"]
    lines.append("포함 예: " + " / ".join(tech.include))
    lines.append("제외: " + " / ".join(tech.exclude))
    for other, hint in tech.confusable.items():
        lines.append(f"구분 (vs {other}): {hint}")
    return "\n".join(lines)


def _vocab_block(techniques: list[Technique]) -> str:
    parts = [f"- {t.id}\n  " + _tech_block(t).replace("\n", "\n  ") for t in techniques]
    return "\n".join(parts)


def _ocr_block(frames: FrameList, ocr_data: dict[str, list[str]] | None) -> str:
    if ocr_data is None:
        return ""
    lines = []
    for i, (_, path) in enumerate(frames, 1):
        texts = ocr_data.get(path.name, [])
        shown = ", ".join(f'"{x}"' for x in texts) if texts else "없음"
        lines.append(f"[{i}] {shown}")
    return "\n프레임별 OCR 힌트 (오인식 가능, 텍스트 유무 참고용):\n" + "\n".join(lines) + "\n"


def build_tag_prompt(
    axis_label: str,
    techniques: list[Technique],
    frames: FrameList,
    span: tuple[float, float],
    max_tags: int,
    ocr_data: dict[str, list[str]] | None = None,
) -> str:
    """축 하나에 대한 태깅 프롬프트를 만든다. techniques 는 호출자가 섞은 순서 그대로 나열한다."""
    return _TAG_PROMPT.format(
        axis_label=axis_label,
        n=len(frames),
        start=span[0],
        end=span[1],
        frame_lines=_frame_lines(frames),
        ocr_block=_ocr_block(frames, ocr_data),
        vocab_block=_vocab_block(techniques),
        max_tags=max_tags,
    )


def build_verify_prompt(tech: Technique, frames: FrameList, span: tuple[float, float]) -> str:
    """후보 태그 1개에 대한 yes/no 검증 프롬프트를 만든다. 생성 단계의 근거는 보여주지 않는다."""
    return _VERIFY_PROMPT.format(
        n=len(frames),
        start=span[0],
        end=span[1],
        frame_lines=_frame_lines(frames),
        tech_id=tech.id,
        tech_block=_tech_block(tech),
    )
