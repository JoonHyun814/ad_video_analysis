"""파이프라인 게이트 판정 — GATE A (M4) / B (M6) / C (M7)."""
import sys


def check_gate_a(m4: dict) -> bool:
    """M4 verdict 가 return_to_phase1 이면 False 를 반환해 파이프라인을 중단한다."""
    if m4.get("verdict") == "return_to_phase1":
        print(f"\n  [GATE A] 반송 — PHASE 1으로 돌아가야 합니다.", file=sys.stderr)
        print(f"  이유: {m4.get('return_reason', '')}", file=sys.stderr)
        return False
    return True


def check_gate_b(m6: dict) -> bool:
    """M6 verdict 가 proceed 가 아니면 False 를 반환해 파이프라인을 중단한다."""
    verdict = m6.get("verdict", "proceed")
    if verdict == "proceed":
        return True
    print(f"\n  [GATE B] 판정: {verdict}", file=sys.stderr)
    criticals = m6.get("unresolved_criticals", [])
    if criticals:
        print(f"  미해결 Critical: {criticals}", file=sys.stderr)
    print(f"  이유: {m6.get('verdict_rationale', '')}", file=sys.stderr)
    return False


def check_gate_c(m7: dict) -> bool:
    """M7 결과가 No-Go 이면 False 를 반환해 파이프라인을 중단한다."""
    gate = m7.get("stage2_human_gate", {})
    if gate.get("result") == "No-Go":
        print(f"\n  [GATE C] No-Go — redirect: {gate.get('redirect', '')}", file=sys.stderr)
        print(f"  이유: {gate.get('redirect_reason', '')}", file=sys.stderr)
        return False
    return True
