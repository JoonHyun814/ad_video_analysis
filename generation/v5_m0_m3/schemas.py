"""v5 ProductInfoCard 스키마 — shortform-pipeline-master_test app/v5/schemas/material.py + synopsis.py(USPResult) 발췌 이식.

원본 그대로(무수정, pydantic 전용·app 의존 없음). MaterialParseResponse/StatusResponse 등
M0~M3 경로에서 쓰이지 않는 라우터 응답 스키마는 이식 대상에서 제외했다.
필드 네이밍: 언더바 금지 — 소문자 연결 (원본 컨벤션 유지).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductType(str, Enum):
    """광고 대상의 형태·범위 6분류."""
    SINGLEPRODUCT = "singleproduct"
    PRODUCTLINE = "productline"
    DIGITALPRODUCT = "digitalproduct"
    INTANGIBLESERVICE = "intangibleservice"
    PLATFORM = "platform"
    BRAND = "brand"


class InvolvementLevel(str, Enum):
    """구매 관여도 3단계."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class USPScores(BaseModel):
    """USP 후보 1개의 5축 가점(각 0~1). usp_score_rules.py 가 clarity/credibility 축만 산출."""
    relevance: float = 0.0
    differentiation: float = 0.0
    demonstrability: float = 0.0
    clarity: float = 0.0
    credibility: float = 0.0
    overall: float = 0.0


class UspSourceItem(BaseModel):
    """상세페이지 섹션 OCR 로 추출한 USP 후보 1개 + 출처 (page_section_ocr 산출)."""
    section: int = 0
    sectionname: str = ""
    number: str = ""
    headline: str = ""
    footnote: str = ""
    sourceimageurl: str = ""
    score: float = 0.0


class USPResult(BaseModel):
    """USP 도출 결과 (usp_extractor 산출)."""
    text: str
    alternatives: list[str] = Field(default_factory=list)
    reasoning: str = ""
    source: str = "llm"
    competitivealternative: str = ""


class ProductInfoCard(BaseModel):
    """소재 자동추출+분류 결과 표준 모델."""
    model_config = ConfigDict(extra="ignore")

    productname: str = ""
    brand: str = ""
    category2id: str = ""
    category2name: str = ""
    category3id: str = ""
    category3name: str = ""
    categorypath: str = ""
    industry: str = ""
    subcategory: str = ""
    adheadline: str = ""
    functionalstrengths: list[str] = Field(default_factory=list)
    productfeatures: str = ""
    targetaudience: str = ""
    tone: str = ""
    keypoints: list[str] = Field(default_factory=list)
    style: str = ""
    productimageurls: list[str] = Field(default_factory=list)
    brandlogourl: str | None = None
    imagedescurlmap: dict[str, str] = Field(default_factory=dict)
    imagetypeurlmap: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0.0

    productappearance: str = ""

    brandpersona: str | None = None
    usp: list[str] = Field(default_factory=list)
    uspvisualcues: list[str] = Field(default_factory=list)
    uspscores: list[USPScores] = Field(default_factory=list)
    uspsections: list[UspSourceItem] = Field(default_factory=list)
    competitiveposition: str | None = None
    competitors: list[dict] = Field(default_factory=list)
    researchconfidence: float | None = None

    personas: list[dict] = Field(default_factory=list)
    primarypersonaid: str | None = None
    heropersonabrief: str | None = None

    producttype: ProductType = ProductType.SINGLEPRODUCT
    involvementlevel: InvolvementLevel = InvolvementLevel.MEDIUM
    visibility: str = ""
    benefittype: str = ""
    producttype7: str = ""
    pricerangeest: str | None = None
    classifierconfidence: float = 0.0

    adpurpose: str | None = None
    promotion: dict | None = None
    usermodelavailable: bool | None = None
    prefnarrative: str | None = None
    intakelog: list[dict] = Field(default_factory=list)

    visualmotifs: list[str] = Field(default_factory=list)
    scenariojtbd: list[str] = Field(default_factory=list)
    negativecues: list[str] = Field(default_factory=list)
    materialspecs: dict | None = None

    missingrequired: list[str] = Field(default_factory=list)

    @field_validator("promotion", mode="before")
    @classmethod
    def _coerce_promotion(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            return {"description": v.strip()}
        return v

    @field_validator("researchconfidence", mode="before")
    @classmethod
    def _coerce_research_confidence(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("high",):
                return 0.9
            if s in ("medium", "med", "mid"):
                return 0.6
            if s in ("low",):
                return 0.3
            try:
                return float(s)
            except ValueError:
                return None
        return None
