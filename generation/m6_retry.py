"""M6 GATE B 반송 후 자동 재진입 정책 — verdict·unresolved_criticals 로 재작성/컨셉 swap 결정."""
import argparse

from utils.io_checks import is_parse_failed


def decide_retry_action(m6: dict, m4: dict, attempt: int, max_retries: int) -> str:
    """M6 결과로 다음 행동을 결정한다 — 'retry_m5' | 'swap_concept' | 'stop'.

    우선순위:
    1. attempt 가 max_retries 이상 → stop
    2. unresolved_criticals 가 비어있지 않음 OR verdict == return_to_gate_a
       → swap_concept (M4 selected 에 남은 컨셉이 있어야 함)
    3. verdict == return_to_m5 → retry_m5 (스크립트 레벨 수정)
    4. 그 외 (proceed/kill/return_to_phase1) → stop
    """
    if attempt >= max_retries:
        return "stop"
    verdict = m6.get("verdict")
    criticals = m6.get("unresolved_criticals") or []
    concept_level = bool(criticals) or verdict == "return_to_gate_a"
    if concept_level:
        return "swap_concept" if len(m4.get("selected") or []) > 1 else "stop"
    if verdict == "return_to_m5":
        return "retry_m5"
    return "stop"


def swap_to_next_concept(m4: dict, m6: dict | None = None) -> dict:
    """M4 selected 첫 컨셉을 fallback 처리하고 killed 로 옮긴다 (감사 추적 유지).

    M6 가 있으면 unresolved_criticals 의 첫 항목을 kill 사유로 사용한다.
    """
    selected = list(m4.get("selected") or [])
    dropped = selected[0] if selected else None
    new_selected = selected[1:]
    m4["selected"] = new_selected
    if not dropped:
        return m4
    next_id = new_selected[0] if new_selected else "-"
    prev_reason = m4.get("selected_rationale") or ""
    m4["selected_rationale"] = (
        f"[M6 게이트 반송으로 {dropped} 컨셉 fallback 처리, 다음 후보 {next_id} 로 전환] "
        + prev_reason
    )
    criticals = (m6 or {}).get("unresolved_criticals") or []
    verdict = (m6 or {}).get("verdict") or "?"
    kill_reason = (
        f"M6 게이트 fallback (verdict={verdict}) — "
        + (criticals[0] if criticals else "컨셉 레벨 결함으로 자동 강등")
    )
    killed = list(m4.get("killed") or [])
    existing_ids = {k.get("id") for k in killed if isinstance(k, dict)}
    if dropped not in existing_ids:
        killed.append({"id": dropped, "reason": kill_reason})
        m4["killed"] = killed
    return m4


def auto_retry(
    brief: dict, m3: dict, m4: dict, m5: dict, m6: dict,
    args: argparse.Namespace,
    *,
    run_m5,
    run_m6,
    save_m4,
) -> tuple[dict, dict, dict]:
    """M6 가 proceed 가 아닐 때 verdict 에 따라 M5 재작성 또는 컨셉 swap 후 재실행.

    max 횟수 한도 안에서 반복한다. 통과·한도·복구 불가 시 최종 (m4, m5, m6) 반환.
    GATE B 의 stderr 출력은 루프 종료 후 호출자가 한 번만 수행한다.
    run_m5/run_m6/save_m4 는 호출자가 주입 (scenario_pipeline 에 정의된 실행기).

    재시도 결과는 `_<attempt>.json` 으로 보존 — 첫 시도(attempt=1)는 기본 경로에 저장되고,
    1번째 재시도부터 attempt=2,3,... 으로 분리 저장돼 직전 결과를 덮어쓰지 않는다.
    """
    max_retries = max(0, getattr(args, "m6_auto_retry_max", 0))
    if max_retries <= 0:
        return m4, m5, m6
    retry_count = 0
    while m6.get("verdict") != "proceed":
        action = decide_retry_action(m6, m4, retry_count, max_retries)
        if action == "stop":
            print(f"  [M6 retry] 중단 — verdict={m6.get('verdict')}, retry={retry_count}/{max_retries}")
            break
        retry_count += 1
        attempt = retry_count + 1  # 첫 시도가 attempt=1 이므로 1번째 재시도는 attempt=2
        if action == "swap_concept":
            dropped = (m4.get("selected") or [None])[0]
            print(f"  [M6 retry {retry_count}/{max_retries}] 컨셉 fallback — {dropped} 탈락, 다음 후보로 전환 (attempt={attempt})")
            m4 = swap_to_next_concept(m4, m6)
            save_m4(m4, attempt)
            feedback = None  # 새 컨셉에 이전 컨셉의 실패 피드백을 주입하면 부적절한 mitigation 유도
        else:
            print(f"  [M6 retry {retry_count}/{max_retries}] M5 재작성 — M6 failure_modes 주입 (attempt={attempt})")
            feedback = m6
        m5 = run_m5(brief, m3, m4, args, m6_feedback=feedback, attempt=attempt)
        if is_parse_failed(m5):
            raise SystemExit("[오류] M5 재작성 결과에 parse_failed 항목 있음. 단계를 재실행해 정상 결과를 만든 뒤 다시 시도하세요.")
        m6 = run_m6(brief, m5, args, attempt=attempt)
        if is_parse_failed(m6):
            raise SystemExit("[오류] M6 재실행 결과에 parse_failed 항목 있음. 단계를 재실행해 정상 결과를 만든 뒤 다시 시도하세요.")
    return m4, m5, m6
