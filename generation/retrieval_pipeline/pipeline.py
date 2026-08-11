"""retrieval_pipeline 오케스트레이터.

  run_m1(): 제품명/URL/가이드 문서/참조 이미지로 제품·브랜드 인사이트(제품 종류/외관/사용법/
      기능/재료/브랜드 이미지/타겟)를 완성한다(LLM 1회, 크롤링·웹 검색·이미지 분석은 코드가
      먼저 결정적으로 수행, product_insight.py). v5_m0_m3 의 MODULE 1(JTBD 인사이트)과는
      무관한 이 파이프라인 전용 새 설계다 — run_m0_m2() 의 M0~M2 재사용 원칙과 별개.
  run_m0_m2(): generation.v5_m0_m3.pipeline.run_m0_m2() 를 그대로 재노출한다(사용자 요청 —
      "M0~M2는 v5_m0_m3과 동일"). 크롤·M1·M2 로직을 이 파이프라인에 다시 구현하지 않는다.
  run_m3(): M1 인사이트(+선택적으로 M0~M2 legacy 맥락)를 입력받아 search_chromadb 도구를
      자율 호출하며 연출 장치 8개를 완성한다(LLM 1회, 도구 왕복은 다회, device_generation.py).
      module0/m1/m2(legacy) 는 전부 선택이다(사용자 요청 — "M3는 이제 m0_m2 말고 m1을
      토대로 작동") — m1_insight 만으로도 실행할 수 있다. 이전 설계(M3 공백 placeholder →
      M4 device_scout → M5 retrieval → M6 synthesis → M7 render)를 걷어내고 파이프라인을
      처음부터 다시 설계했다(사용자 요청 — "pipeline 개편, 다 지우고 한단계씩 개발").
  run_m4(): M3가 완성한 장치 8개 중 이 제품·광고 길이에 맞는 것을 골라 조합해, 광고 전체
      시나리오(scenario_analysis.json 과 동일한 구조)를 완성한다(LLM 1회, search_chromadb
      호출은 선택적, scenario_generation.py).
  run_m5(): M4 시나리오를 스토리보드 이미지 슬롯 계획(인물/제품/Environment/컷별) + 컷마다
      Seedance 영상 모션 프롬프트로 전환한다(LLM 1회, storyboard_generation.py). 실제 이미지
      소싱/생성은 이 단계가 아니라 별도 실행되는 storyboard_codex.py(Codex CLI)의 몫이다.
      뒷 단계(Codex 실행·Seedance 영상 생성 자체)는 이 파이프라인 코드 밖에서 별도 스크립트로
      수행한다 — 다음 요청에서 이어 붙인다.
"""
from __future__ import annotations

from typing import Any

from generation.retrieval_pipeline import device_generation, product_insight, scenario_generation, storyboard_generation
from generation.retrieval_pipeline.context import build_context
from generation.v5_m0_m3.pipeline import run_m0_m2  # noqa: F401  (재노출 — 사용자 요청)


async def run_m1(product_name: str, url: str, *, guideline_md: str = "",
                 reference_dir: str | None = None, backend: str = "cli",
                 log_prefix: str = "default", log_dir: str | None = None) -> dict[str, Any]:
    """M1 — 제품명/URL/가이드 문서/참조 이미지로 제품·브랜드 인사이트를 완성한다.

    반환에 product_name/url/guideline_md 를 함께 담는다 — 다음 단계(아직 미배선)가 이 dict
    하나만으로 이어받을 수 있도록, 이 파이프라인의 기존 관례(run_m3 등)를 그대로 따른다.
    crawled_images 는 크롤링 중 발견해 log_dir/crawled_images/ 에 저장한 로고·제품 이미지
    목록({"type","url","path"}[]) — 아무것도 못 찾았거나 log_dir 이 없으면 빈 리스트.
    """
    output, prompt, crawled_images = await product_insight.run(
        product_name, url, guideline_md=guideline_md, reference_dir=reference_dir,
        backend=backend, log_prefix=log_prefix, log_dir=log_dir,
    )
    return {
        "product_name": product_name, "url": url, "guideline_md": guideline_md,
        "prompt": prompt, "crawled_images": crawled_images,
        **output.model_dump(),
    }


def run_m3(module0: dict | None = None, m1: dict | None = None, m2: dict | None = None, *,
          m1_insight: dict | None = None, concept_line: str = "", ad_length: str = "15초",
          backend: str = "cli", log_prefix: str = "default", log_dir: str | None = None
          ) -> dict[str, Any]:
    """M3 — M1 인사이트(+선택적 M0~M2 legacy 맥락)를 분석하고 도구 호출로 근거를 모아
    연출 장치 8개를 완성한다.

    module0/m1/m2 는 전부 선택이다(사용자 요청 — "M3는 이제 m0_m2 말고 m1을 토대로 작동") —
    cli_m3.py 의 --input(legacy m0_m2.json) 없이 --m1_input 만으로도 실행할 수 있다. 셋 다
    안 주면 빈 dict 로 취급한다(context.build_context() 참고).

    m1_insight: 새 M1(product_insight.py, run_m1() 이 만드는 m1.json)의 산출물 — legacy m1
    (위 인자, JTBD 인사이트, 있다면)과는 별개다. 지정하면 context.build_context() 가
    context.product_insight 로 얹어(module0/m1 이 없으면 product.name/category,
    insight.target_label 의 폴백 소스로도 쓰인다) M3 가 제품 외관/사용법/기능/재료/브랜드
    이미지 같은 구체적 사실 근거를 연출 장치(mechanism/application_draft)에 반영할 수 있게
    한다.

    log_prefix: search_chromadb 호출 로그 파일명(<log_prefix>.jsonl) — cli_m3.py 는
    --title(슬러그, 또는 --m1_input 이 있던 폴더명에서 뽑은 슬러그)을 그대로 넘긴다(사용자
    요청 — 프로젝트 제목별로 로그 분리).
    log_dir: 그 로그 파일을 남길 폴더 — cli_m3.py 는 이 실행의 출력 폴더를 그대로 넘긴다
    (사용자 요청 — 날짜 폴더 하위에 저장). 안 주면 tool_chat.py 기본값(logs/search_chromadb/)
    을 쓴다.

    반환에 module0/m1/m2/m1_insight 원본은 담지 않는다(사용자 요청 — "m3 결과 저장할 때
    module0,m1,m2,m1_insight는 저장 안해도 돼") — 이미 build_context() 가 뽑아낸 압축본이
    "context"에 다 들어있으므로 원본을 다시 통째로 들고 다닐 필요가 없다. concept_line/
    ad_length/context 는 계속 담는다(다음 단계가 이 dict 하나만으로 이어받을 수 있도록).
    cli_m4.py 는 module0/m1/m2 가 없어도(get() 폴백으로 빈 dict) 동작한다.
    """
    module0, m1, m2 = module0 or {}, m1 or {}, m2 or {}
    context = build_context(module0, m1, m2, m1_insight=m1_insight)
    output, prompt = device_generation.run_device_generation(
        context, ad_length=ad_length, concept_line=concept_line, backend=backend,
        log_prefix=log_prefix, log_dir=log_dir,
    )
    return {
        "concept_line": concept_line, "ad_length": ad_length,
        "context": context,
        "prompt": prompt,
        "creative_problem": output.creative_problem,
        "devices": [d.model_dump() for d in output.devices],
    }


def run_m4(module0: dict, m1: dict, m2: dict, context: dict, creative_problem: str,
          devices: list[dict], *, concept_line: str = "", ad_length: str = "15초",
          backend: str = "cli", log_prefix: str = "default", log_dir: str | None = None
          ) -> dict[str, Any]:
    """M4 — M3가 완성한 장치 8개 중 이 제품·광고 길이에 맞는 것을 골라 조합해 광고 전체
    시나리오(cast/scenes/key_messages/production_notes — scenario_analysis.json 과 동일한
    구조)를 완성한다.

    module0/context/creative_problem/devices 는 모두 m3.json 을 그대로 펼친 값이다(cli_m4.py
    가 넘긴다) — module0 을 별도로 받는 이유는 scenario_generation.build_prompt() 가 context의
    기존 버그(product.name/usp_candidates 가 항상 비어 나옴)를 이 프롬프트에 한해 module0
    원본으로 다시 채워 넣어야 하기 때문이다(scenario_generation.py 의 _patch_product_meta 참고).

    log_prefix/log_dir: run_m3()와 동일한 관례 — cli_m4.py 는 m3.json 이 있던 실행 폴더를
    log_dir 로, 그 폴더명에서 뽑은 슬러그에 "_m4"를 붙인 이름을 log_prefix 로 넘겨 M3 검색
    로그와 파일을 분리한다.

    반환에 module0~m2/concept_line/ad_length/context/creative_problem/devices 를 그대로
    이어 담고 시나리오 필드를 최상위에 펼친다 — run_m3()와 같은 이유로, 각 단계 출력 파일이
    독립적으로 다음 단계의 유일한 입력이 될 수 있도록 하기 위해서다.
    """
    output, prompt = scenario_generation.run_scenario_generation(
        context, devices, creative_problem, module0, ad_length=ad_length, concept_line=concept_line,
        backend=backend, log_prefix=log_prefix, log_dir=log_dir,
    )
    return {
        "module0": module0, "m1": m1, "m2": m2,
        "concept_line": concept_line, "ad_length": ad_length,
        "context": context, "creative_problem": creative_problem, "devices": devices,
        "prompt": prompt,
        **output.model_dump(),
    }


def run_m5(module0: dict, m1: dict, m2: dict, context: dict, creative_problem: str,
          devices: list[dict], scenario: dict, *, backend: str = "cli", log_prefix: str = "default",
          log_dir: str | None = None) -> dict[str, Any]:
    """M5 — M4 시나리오를 스토리보드 이미지 슬롯 계획(인물/제품/Environment/컷별) + 컷마다
    Seedance 영상 모션 프롬프트로 전환한다.

    scenario: m4.json에서 title/brand/concept/narrative/cast/scenes/key_messages/
    production_notes 만 뽑은 dict(storyboard_generation.scenario_fields() 로 cli_m5.py가
    만들어 넘긴다) — run_m4()와 같은 이유로 devices_applied 나 M0~M4 체이닝 메타데이터는
    이 단계 프롬프트에 다시 넣지 않는다.

    반환에 module0~m2/context/creative_problem/devices/scenario 를 그대로 이어 담고
    StoryboardShotPlan 필드(characters/product/environment/cuts)를 최상위에 펼친다 — 이
    파이프라인의 기존 관례(run_m3/run_m4)와 같은 이유다.
    """
    output, prompt = storyboard_generation.run_storyboard_generation(
        scenario, module0, backend=backend, log_prefix=log_prefix, log_dir=log_dir,
    )
    return {
        "module0": module0, "m1": m1, "m2": m2,
        "context": context, "creative_problem": creative_problem, "devices": devices,
        "scenario": scenario,
        "prompt": prompt,
        **output.model_dump(),
    }
