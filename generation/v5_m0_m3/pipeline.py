"""v5_m0_m3 오케스트레이터 — 두 개의 독립 파이프라인.

  run_m0_m3(): M0(소재 인제스트) → M1(인사이트) → M2(포지셔닝) → M3(컨셉 발산)
  run_m4_m9(): M4(비평·킬/GATE A) → M5(DR 스크립트) → M6(레드팀/GATE B) → M7(저비용 검증/GATE C) → M9(콘티)

사용자 요청에 따라 서로 따로 실행할 수 있도록 분리했다 — run_m4_m9() 는 run_m0_m3() 의 반환값
(module0/m1/m2/m3)을 그대로 입력받는다. 원본 orchestrator.py 의 GATE A/B 자동 반송 루프
(M3 재발산·owner 모듈 재실행)는 이식하지 않았다 — 그 반송 대상(M1~M3)이 이미 끝난 별개의
파이프라인 실행 결과라 이 함수 안에서 되돌릴 수 없다. VoC 마이닝 토글·DB 기록도 제외 — 직선
순차 실행만 한다.

GATE A(M4)는 reject 여도 중단하지 않고 M5 로 계속 진행한다 — 소스의 studio_orchestrator.py
run_full()과 동일한 동작(사용자 요청으로 재현, run_m4_m9() 내부 주석 참고). GATE B(M6) block
은 그 지점에서 중단한다(이 요청 범위 밖이라 기존 동작 유지). GATE C(M7)는 원본처럼 verdict 만
기록하고 항상 M9 로 진행한다(인간 검수 UI 없음).
"""
from __future__ import annotations

import logging

from generation.v5_m0_m3 import module0_ingest, modules_runner

logger = logging.getLogger(__name__)


def module0_is_usable(module0: dict) -> tuple[bool, str]:
    """크롤/추출이 실제 제품 데이터를 얻었는지 — productname 이 실텍스트면 usable."""
    if module0_ingest.hasrealtext(module0.get("productname")):
        return True, ""
    return False, ("MODULE 0 unusable: 크롤이 차단/실패했고 웹 검색으로도 제품을 특정하지 못함 — "
                   "제품 제목을 더 구체적으로 입력하거나 다른 URL 로 다시 시도하세요")


async def run_m0_m3(sourceurl: str, *, producttitle: str = "", label: str = "") -> dict:
    """M0~M3 를 순차 실행하고 각 단계 결과를 dict 로 모아 반환.

    반환: {"module0": {...}, "m1": {...}, "m2": {...}, "m3": {...}}
    M0 가 unusable 이면 "error" 키만 채워 반환하고 M1~M3 는 실행하지 않는다.
    """
    module0 = await module0_ingest.ingest(sourceurl=sourceurl, producttitle=producttitle, label=label)
    usable, reason = module0_is_usable(module0)
    if not usable:
        logger.warning(f"[v5_m0_m3 {label}] {reason}")
        return {"module0": module0, "error": reason}

    handoffs: dict[int, dict] = {}
    for n in (1, 2, 3):
        out = await modules_runner.run_module(n, module0=module0, handoffs=handoffs)
        handoffs[n] = out
        if not out:
            logger.error(f"[v5_m0_m3 {label}] MODULE {n} failed — 이후 단계 중단")
            return {"module0": module0, "handoffs": handoffs,
                    "error": f"MODULE {n} 실행 실패(빈 응답, 재시도 후에도 실패)"}

    return {"module0": module0, "m1": handoffs[1], "m2": handoffs[2], "m3": handoffs[3]}


async def run_m4_m9(module0: dict, m1: dict, m2: dict, m3: dict, *,
                    style: str | None = None, label: str = "") -> dict:
    """M4~M9 를 순차 실행. module0/m1/m2/m3 는 run_m0_m3() 의 출력을 그대로 넣는다.

    style: M9 콘티 촬영 포맷(video_style.VALID 중 하나). 미지정 시 cinematic 기본값
    (원본의 DB 기반 LLM 자동선택은 이식하지 않았다 — video_style.py 참고).

    GATE A(M4) reject 는 중단하지 않고 경고만 남긴 뒤 M5 로 계속 진행한다(아래 본문 주석 참고 —
    소스 studio_orchestrator.run_full() 과 동일한 동작을 사용자 요청으로 재현). GATE B(M6)
    block 은 그 지점에서 중단한다. GATE C(M7) verdict 는 기록만 하고(인간 검수 UI 없음) 항상
    M9 로 진행한다. 반환에는 항상 "gates": {"a": "go"|"reject", "b": "pass"|"conditional"|"block",
    "c": "go"|"nogo"} 가 채워진 만큼만 담긴다.
    """
    if style:
        module0 = dict(module0)
        module0["videostyle"] = style

    handoffs: dict[int, dict] = {1: m1, 2: m2, 3: m3}
    gates: dict[str, str] = {}

    m4 = await modules_runner.run_module(4, module0=module0, handoffs=handoffs)
    handoffs[4] = m4
    gates["a"] = modules_runner.gate_a(m4)
    annotated_m3 = modules_runner.annotate_concepts_with_verdict(m3, m4) or m3
    handoffs[3] = annotated_m3
    # [사용자 요청 — 소스의 studio_orchestrator.run_full() 동작을 그대로 재현]
    # 원본에는 두 실행 경로가 있다: orchestrator.start_run()(classic)은 GATE A 반송을 다 써도
    # reject 면 `if ga == "reject": return`으로 멈추고 status=awaitingreview 로 정지한다.
    # 반면 studio_orchestrator.run_full()("풀런")은 반송 루프가 끝난 뒤 ga 값을 전혀 검사하지
    # 않고 곧장 M5 를 실행한다(orchestrator.py L172-196 vs studio_orchestrator.py L205-227 비교 —
    # 후자엔 reject 시 return 하는 가드 자체가 없다). 즉 M3 컨셉이 전부 킬돼도(shortlist·selected
    # 둘 다 0개) "일단 통과"해 M5 로 넘어간다 — 의도된 설계라기보단 가드 누락으로 보이지만,
    # 사용자가 이 동작을 그대로 재현해 달라고 요청해 여기서도 gate_a == "reject" 여도 중단하지
    # 않고 계속 진행한다. 이때 M5 의 _build_user(n=5)는 원본과 동일하게
    # `((h.get(4,{}) or {}).get("selected") or [{}])[0]` 로 selectedconcept 를 뽑는데, selected 가
    # 정말 비어 있으면 빈 dict `{}` 가 그대로 M5 입력이 된다 — 즉 "선정된 컨셉 없이" 스크립트가
    # 만들어질 수 있다(원본과 동일한 결과). GATE B(M6)/GATE C(M7)는 이 요청 범위 밖이라 기존
    # 그대로 유지했다(GATE B block 은 계속 중단, GATE C 는 원래도 기록만 하고 진행).
    if gates["a"] == "reject":
        logger.warning(f"[v5_m0_m3 {label}] GATE A reject — 살아남은 컨셉 없음(원본 run_full 과 동일하게 M5 로 계속 진행)")

    m5 = await modules_runner.run_module(5, module0=module0, handoffs=handoffs)
    handoffs[5] = m5
    if not m5:
        return {"m3": annotated_m3, "m4": m4, "gates": gates, "error": "MODULE 5 실행 실패(빈 응답, 재시도 후에도 실패)"}

    m6 = await modules_runner.run_module(6, module0=module0, handoffs=handoffs)
    handoffs[6] = m6
    gates["b"] = modules_runner.gate_b(m6)
    if gates["b"] == "block":
        logger.warning(f"[v5_m0_m3 {label}] GATE B block — unresolvedcritical={m6.get('unresolvedcritical')}")
        return {"m3": annotated_m3, "m4": m4, "m5": m5, "m6": m6, "gates": gates,
                "error": "GATE B block: 레드팀이 완화 불가한 결함을 지적했다(unresolvedcritical 참고). "
                         "결함의 근원 단계부터(M0~M3 재실행 또는 이 파이프라인 재실행으로 M5 재작성) 다시 시도하세요."}

    m7 = await modules_runner.run_module(7, module0=module0, handoffs=handoffs)
    handoffs[7] = m7
    if not m7:
        return {"m3": annotated_m3, "m4": m4, "m5": m5, "m6": m6, "gates": gates,
                "error": "MODULE 7 실행 실패(빈 응답, 재시도 후에도 실패)"}
    gates["c"] = modules_runner.gate_c(m7)
    if gates["c"] == "nogo":
        logger.warning(f"[v5_m0_m3 {label}] GATE C verdict=nogo — 인간 검수 UI 가 없어 기록만 하고 M9 계속 진행")

    m9 = await modules_runner.run_module(9, module0=module0, handoffs=handoffs)
    handoffs[9] = m9
    if not m9:
        return {"m3": annotated_m3, "m4": m4, "m5": m5, "m6": m6, "m7": m7, "gates": gates,
                "error": "MODULE 9 실행 실패(빈 응답, 재시도 후에도 실패)"}

    return {"m3": annotated_m3, "m4": m4, "m5": m5, "m6": m6, "m7": m7, "m9": m9, "gates": gates}
