"""advanced_metrics.py 프롬프트에 쓰는 지표 설명·JSON 스키마 상수.

T2VScore-A(Wu et al. 2024, arXiv:2401.07781 §3.1)와 VBench-2.0(Zheng et al. 2025,
arXiv:2503.21755 §III-A)의 평가 방법론을 옮긴 것. 두 논문 모두 "엔티티/질문 분해 → VQA
판정"을 별도 LLM 호출로 나누지만, 여기서는 비용 절감을 위해 한 번의 claude -p 호출에서
분해와 판정을 함께 시킨다 — 정답 집계(accuracy)는 advanced_metrics_scoring.py 가 코드로
계산해 LLM 산술 오차를 배제한다(방법론 자체는 원자적 요소 단위 검증이라는 논문 핵심을 그대로
유지).
"""

T2VSCORE_A_INSTRUCTION = (
    "[T2VScore-A: 요소 분해 정합성 — Wu et al. 2024 §3.1 Entity Decomposition + VQA]\n"
    "스토리보드 전체에서 검증 가능한 핵심 요소(주체 entity·속성 attribute·동작 action)를 "
    "6~10개 뽑아라 — 씬마다 최소 1개씩 고르게 배분한다. 스타일·카메라 무브처럼 장면 전체에 "
    "걸리는 요소는 type=global 로 표시한다. 각 요소가 scenario_analysis 에서 실제로 확인되는지"
    "(verified) 개별 판정한다."
)

VBENCH2_DIMENSION_INSTRUCTIONS = {
    "complex_plot": (
        "[VBench-2.0 Complex Plot §III-A(3-e)] 스토리보드의 서사를 순서대로 3~6개 플롯 "
        "비트로 요약하고, scenario_analysis 가 같은 순서로 각 비트를 재현하는지 앞에서부터 "
        "차례로 확인한다(순차 매칭 — 어긋난 지점 이후는 matched=false 로만 표시하고 별도 "
        "설명은 evidence 에 남긴다). 뚜렷한 서사 전개(사건·장소 전개) 없이 한 장면 반복이면 "
        "applicable=false."
    ),
    "complex_landscape": (
        "[VBench-2.0 Complex Landscape §III-A(3-f)] 스토리보드의 배경/장소 전환을 순서대로 "
        "3~6개 비트로 요약하고, scenario_analysis 의 배경 서술이 같은 순서로 그 전환을 "
        "재현하는지 순차 확인한다(complex_plot 과 동일한 순차 매칭, 대상만 장소). 단일 "
        "장소·배경 고정형 스토리보드면 applicable=false."
    ),
    "human_interaction": (
        "[VBench-2.0 Human Interaction §III-A(3-d)] 등장인물 2인 이상의 물리적 상호작용"
        "(건네줌·악수·부딪힘 등)이 스토리보드에 명시돼 있을 때만 applicable=true. 기대 "
        "상호작용과 scenario_analysis 상 실제 상호작용을 'A가 B에게 ~한다' 형식으로 비교해 "
        "일치 여부를 판정한다."
    ),
    "motion_order_understanding": (
        "[VBench-2.0 Motion Order Understanding §III-A(3-c)] 한 씬/샷 안에 순서가 명시된 "
        "동작이 2개 이상 있을 때만 applicable=true(예: '라벨을 확인한 뒤 잔에 따른다'). 두 "
        "동작을 순서대로 나열하고 scenario_analysis 에서 각각 같은 순서로 확인되는지 개별 "
        "판정한다."
    ),
    "dynamic_attribute": (
        "[VBench-2.0 Dynamic Attribute §III-A(3-a)] 시간에 따른 속성 변화(색상·형태·질감 등)"
        "가 스토리보드에 명시돼 있을 때만 applicable=true. '초기 상태', '최종 상태', '변화 "
        "발생 여부' 3개의 예/아니오 질문을 만들어 scenario_analysis 로 각각 expected(스토리"
        "보드 기준 정답)/actual(scenario_analysis 상 실제 답) 을 true/false 로 채운다."
    ),
    "dynamic_spatial_relationship": (
        "[VBench-2.0 Dynamic Spatial Relationship §III-A(3-b)] 물체/인물의 위치 이동(예: "
        "'A 왼쪽에 있다가 앞으로 이동')이 스토리보드에 명시돼 있을 때만 applicable=true. "
        "dynamic_attribute 와 동일하게 초기 위치·최종 위치·이동 발생 여부 3질문을 "
        "expected/actual true/false 로 채운다."
    ),
    "motion_rationality": (
        "[VBench-2.0 Motion Rationality §III-A(5-a)] 먹기/마시기/자르기처럼 '동작이 실제 "
        "결과를 남겨야 한다'는 지시(또는 반대로 '동작은 하되 결과를 남기면 안 된다'는 지시, "
        "예: '입가로 들되 마시지 않고 멈춤')가 스토리보드에 있을 때만 applicable=true. 동작 "
        "발생 여부·실제 결과 발생 여부·스토리보드가 요구한 결과와 일치 여부를 각각 예/아니오 "
        "질문으로 만들어 expected/actual true/false 로 채운다(허위 동작·허위 정지 모두 이 "
        "방식으로 잡아낸다)."
    ),
}

SCHEMA = (
    '{"t2vscore_a": {"elements": ['
    '{"element": "...", "type": "entity|attribute|action|global", "source_scene": 1, '
    '"verified": true, "evidence": "..."}]},'
    ' "vbench2": {'
    '"complex_plot": {"applicable": true, "elements": [{"beat": "...", "matched": true}], "evidence": "..."},'
    ' "complex_landscape": {"applicable": true, "elements": [{"beat": "...", "matched": true}], "evidence": "..."},'
    ' "human_interaction": {"applicable": true, "expected": "...", "actual": "...", "match": true, "evidence": "..."},'
    ' "motion_order_understanding": {"applicable": true, '
    '"actions": [{"action": "...", "order_matched": true}], "evidence": "..."},'
    ' "dynamic_attribute": {"applicable": true, "attribute": "...", '
    '"questions": [{"question": "...", "expected": true, "actual": true}], "evidence": "..."},'
    ' "dynamic_spatial_relationship": {"applicable": true, "relationship": "...", '
    '"questions": [{"question": "...", "expected": true, "actual": true}], "evidence": "..."},'
    ' "motion_rationality": {"applicable": true, "motion": "...", '
    '"questions": [{"question": "...", "expected": true, "actual": true}], "evidence": "..."}'
    '}}'
    ' — 해당 없는 차원은 {"applicable": false, "evidence": "해당 없는 이유"} 로 짧게 끝낸다.'
)
