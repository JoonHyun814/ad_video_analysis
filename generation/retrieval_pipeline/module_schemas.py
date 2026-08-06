"""retrieval_pipeline M0~M2 산출물 스키마 — v5_m0_m3 를 재사용하지 않는 이 파이프라인 전용
독립 구현이다(사용자 요청 — "m0-m2 를 v5_m0_m3 거를 import 하는게 아니라 독립적으로 코드
새롭게 만들어서 사용"). schemas.py(M3~M7)와 마찬가지로 snake_case 를 쓴다.

M0(module0, LLM 1회) → M1(module1, LLM 1회) → M2(module2, LLM 1회). v5_m0_m3 는 크롤이
1차 소스이고 브랜드 가이드라인은 M1·M2 프롬프트에 끼워 넣는 보조 지시였지만, 이 구현은 반대다
— **브랜드 가이드라인이 1차 소스**이고, 가이드라인에서 확인할 수 없는 정보만 크롤링으로
보완한다(사용자 요청). `product_image_url` 은 LLM이 지어내지 않도록 크롤 결과(og:image 등)에서
코드가 결정적으로 채운다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class USPCandidate(BaseModel):
    """USP 후보 1건 — 어디서 나왔는지(source)와 신뢰도(trust)를 함께 남긴다."""
    text: str = ""
    source: str = ""   # "guideline" | "crawl"
    trust: str = ""     # "evidence" | "claim"


class Module0LLM(BaseModel):
    """M0 LLM 호출이 실제로 채우는 필드만 — product_image_url/source_url 등 코드가 결정적으로
    채우는 필드는 여기 없다(module0.run_module0() 가 별도로 합친다)."""
    product_name: str = ""
    brand: str = ""
    category: str = ""
    usp_candidates: list[USPCandidate] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    target_hints: list[str] = Field(default_factory=list)
    tone: str = ""
    ingest_note: str = ""  # 무엇이 가이드라인에서, 무엇이 크롤로 보완됐는지 1~2문장


class Module1(BaseModel):
    """M1(인사이트) 산출물."""
    core_job: str = ""
    human_truth: str = ""
    human_truth_contradiction: str = ""
    target_label: str = ""


class Module2(BaseModel):
    """M2(포지셔닝) 산출물."""
    positioning_statement: str = ""
    value_proposition: str = ""
    unique_attributes: list[str] = Field(default_factory=list)
