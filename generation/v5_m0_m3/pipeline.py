"""v5_m0_m3 오케스트레이터 — 두 개의 독립 파이프라인.

  run_m0_m3(): M0(소재 인제스트) → M1(인사이트) → M2(포지셔닝) → M3(컨셉 발산)
  run_m4_m9(): M4(비평·킬/GATE A) → M5(DR 스크립트) → M6(레드팀/GATE B) → M7(저비용 검증/GATE C) → M9(콘티)

사용자 요청에 따라 서로 따로 실행할 수 있도록 분리했다 — run_m4_m9() 는 run_m0_m3() 의 반환값
(module0/m1/m2/m3)을 그대로 입력받는다. 원본 orchestrator.py 의 GATE A/B 자동 반송 루프
(M3 재발산·owner 모듈 재실행)는 이식하지 않았다 — 그 반송 대상(M1~M3)이 이미 끝난 별개의
파이프라인 실행 결과라 이 함수 안에서 되돌릴 수 없다. VoC 마이닝 토글·DB 기록도 제외 — 직선
순차 실행만 한다.

GATE A(M4) reject·GATE B(M6) block 모두 중단하지 않고 계속 진행한다 — 소스의
studio_orchestrator.py run_full()과 동일한 동작(사용자 요청으로 재현, run_m4_m9() 내부
주석 참고. 소스 조사 결과 run_full()·orchestrator.py start_run() 둘 다 GATE B bounce 루프가
끝난 뒤 block 값을 검사해 멈추는 코드가 없다 — 의도된 설계라기보단 가드 누락으로 보인다).
GATE C(M7)는 원본처럼 verdict 만 기록하고 항상 M9 로 진행한다(인간 검수 UI 없음).

run_m4_m9() 의 `forced_concept` 인자(사용자 요청)로 M4 LLM 비평을 생략하고 M3 concepts[]
중 하나를 이름으로 직접 GATE A 통과시킬 수 있다 — M3 발산 결과를 사람이 다 보고 나서 어떤
컨셉으로 스크립트·콘티까지 만들지 직접 고르고 싶을 때, 또는 M3 컨셉 전체를 한 번씩 M5~M9 로
돌려 비교하고 싶을 때 쓴다.
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


def _forced_m4(m3: dict, forced_concept: str) -> dict:
    """사용자가 M3 concepts[] 중 하나를 이름으로 직접 골라 GATE A 를 통과시킨다(M4 LLM 비평
    생략) — M4 의 나머지 필드(scores/killed)는 비워 "사용자가 직접 지정했다"는 사실을
    `reason` 에 남긴다. 이름 매칭은 `modules_runner.annotate_concepts_with_verdict()` 와 같은
    정규화(`_norm_concept`)를 써서 공백·따옴표·대소문자 차이를 흡수한다."""
    concepts = [c for c in ((m3 or {}).get("concepts") or []) if isinstance(c, dict)]
    target = modules_runner._norm_concept(forced_concept)
    match = next((c for c in concepts if modules_runner._norm_concept(c.get("name")) == target), None)
    if not match:
        names = [c.get("name") for c in concepts]
        raise ValueError(f"forced_concept {forced_concept!r} 를 M3 concepts 에서 찾을 수 없음. "
                         f"후보: {names}")
    entry = {
        "concept": match.get("name"), "onesentence": match.get("provingwhy") or match.get("bigidea") or "",
        "assumptions": [], "traps": [match["risk"]] if match.get("risk") else [], "recommended": True,
    }
    return {"verdict": "go", "scores": [], "killed": [], "shortlist": [entry], "selected": [entry],
            "reason": f"사용자가 GATE A 를 직접 지정(forced_concept={match.get('name')!r}) — M4 LLM 비평 생략"}


async def run_m4_m9(module0: dict, m1: dict, m2: dict, m3: dict, *,
                    style: str | None = None, label: str = "",
                    forced_concept: str | None = None) -> dict:
    """M4~M9 를 순차 실행. module0/m1/m2/m3 는 run_m0_m3() 의 출력을 그대로 넣는다.

    style: M9 콘티 촬영 포맷(video_style.VALID 중 하나). 미지정 시 cinematic 기본값
    (원본의 DB 기반 LLM 자동선택은 이식하지 않았다 — video_style.py 참고).
    forced_concept: 지정하면 M4 LLM 비평을 생략하고 이 이름과 일치하는 M3 concepts[] 항목을
    바로 GATE A 통과("selected")로 만든다(사용자 요청 — M3 리스트 중 어떤 컨셉을 통과시킬지
    사용자가 직접 결정). 이름이 M3 concepts[] 에 없으면 ValueError. 미지정 시 기존처럼 M4 가
    자율적으로 선택한다.

    GATE A(M4) reject·GATE B(M6) block 모두 중단하지 않고 경고만 남긴 뒤 계속 진행한다(아래
    본문 주석 참고 — 소스 studio_orchestrator.run_full() 과 동일한 동작을 사용자 요청으로
    재현). GATE C(M7) verdict 는 기록만 하고(인간 검수 UI 없음) 항상 M9 로 진행한다. 반환에는
    항상 "gates": {"a": "go"|"reject", "b": "pass"|"conditional"|"block", "c": "go"|"nogo"} 가
    채워진 만큼만 담긴다.
    """
    if style:
        module0 = dict(module0)
        module0["videostyle"] = style

    handoffs: dict[int, dict] = {1: m1, 2: m2, 3: m3}
    gates: dict[str, str] = {}

    if forced_concept:
        m4 = _forced_m4(m3, forced_concept)
    else:
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
    # 만들어질 수 있다(원본과 동일한 결과). GATE B(M6)도 동일한 패턴이라 아래에서 같은 방식으로
    # 처리한다(계속 진행) — GATE C(M7)는 원래도 기록만 하고 진행하는 정책이라 변경 없음.
    if gates["a"] == "reject":
        logger.warning(f"[v5_m0_m3 {label}] GATE A reject — 살아남은 컨셉 없음(원본 run_full 과 동일하게 M5 로 계속 진행)")

    m5 = await modules_runner.run_module(5, module0=module0, handoffs=handoffs)
    handoffs[5] = m5
    if not m5:
        return {"m3": annotated_m3, "m4": m4, "gates": gates, "error": "MODULE 5 실행 실패(빈 응답, 재시도 후에도 실패)"}

    m6 = await modules_runner.run_module(6, module0=module0, handoffs=handoffs)
    handoffs[6] = m6
    gates["b"] = modules_runner.gate_b(m6)
    # [사용자 요청 — 소스의 studio_orchestrator.run_full() 동작을 그대로 재현, GATE A 와 동일 패턴]
    # 소스에도 M3 반송을 위한 bounce 루프(MAX_B_BOUNCES)가 있지만, 루프가 다 끝난 뒤에도
    # run_full()·start_run() 둘 다 `gb == "block"` 을 검사해 멈추는 코드가 없다(studio_orchestrator.py
    # L229-255 / orchestrator.py L198-227) — bounce 를 다 써도 block 이면 경고만 남기고(start_run 만
    # warnings.append, run_full 은 그마저도 없음) 그대로 M7 로 진행한다. 이 프로젝트는 M3/M5 재생성
    # bounce 루프 자체를 이식하지 않았으므로(GATE A 주석 참고), 여기서도 동일하게 block 이어도
    # 경고만 남기고 계속 진행한다 — "레드팀이 완화 불가 결함을 지적해도 일단 통과"하는 소스의
    # 동작을 그대로 재현한 것이며, 의도된 설계라기보단 가드 누락으로 보인다(소스 조사 결과).
    if gates["b"] == "block":
        logger.warning(f"[v5_m0_m3 {label}] GATE B block — unresolvedcritical={m6.get('unresolvedcritical')}"
                       f"(원본 run_full 과 동일하게 M7 로 계속 진행)")

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
