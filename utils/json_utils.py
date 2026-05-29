"""LLM 응답에서 JSON을 파싱·복구하는 유틸리티."""
import json
import re


def parse_json(text: str) -> dict:
    """LLM 응답 텍스트에서 JSON 객체를 파싱한다.

    마크다운 펜스 제거 → 완전한 JSON → raw_decode(후행 텍스트 제거) →
    잘린 JSON 복구 순으로 시도한다. 모든 시도 실패 시 error 키를 반환한다.
    """
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    start = text.find("{")
    if start == -1:
        return {"error": "parse_failed", "raw": text[:500]}
    text = text[start:]

    # 1) 완전한 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) JSON 뒤에 설명 텍스트가 붙은 경우 — 첫 완전한 객체만 추출
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 3) 토큰 한도로 잘린 경우 — 괄호 보충해 복구
    repaired = _repair_json(text)
    if repaired is not None:
        return repaired

    return {"error": "parse_failed", "raw": text[:500]}


def _repair_json(text: str) -> dict | None:
    """잘린 JSON에 닫는 괄호를 보충해 복구한다. 복구 불가 시 None 반환."""
    stack: list[str] = []
    in_string = False
    escape = False
    last_safe = 0       # 최상위 객체 완전 종료 위치
    depth1_safe = 0     # depth=1 에서 값이 완전히 닫힌 마지막 위치

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            depth = len(stack)
            if depth == 0:
                last_safe = i + 1
            elif depth == 1 and ch == "}":
                depth1_safe = i + 1

    if not stack and not in_string:
        for pos in (last_safe, depth1_safe):
            if pos > 0:
                try:
                    return json.loads(text[:pos])
                except json.JSONDecodeError:
                    continue
        return None

    candidate = text.rstrip()

    if in_string:
        if escape:
            candidate = candidate[:-1]
        candidate += '"'

    _STR = r'"(?:[^"\\]|\\.)*"'
    _NONSTR = r'[^,}\]"\\]*'
    candidate = re.sub(
        rf',\s*{_STR}(?:\s*:\s*(?:{_STR}|{_NONSTR}))?$',
        "",
        candidate.rstrip(),
        flags=re.DOTALL,
    )
    candidate = candidate.rstrip().rstrip(",")
    closing = "".join("}" if c == "{" else "]" for c in reversed(stack))

    try:
        return json.loads(candidate + closing)
    except json.JSONDecodeError:
        pass

    for pos in (depth1_safe, last_safe):
        if pos > 0:
            try:
                return json.loads(text[:pos])
            except json.JSONDecodeError:
                continue
    return None
