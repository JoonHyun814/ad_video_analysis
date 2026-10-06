"""ad_graph 그래프의 노드/엣지 테이블 스키마.

노드: Campaign(캠페인) / Sequence(서사 역할 순서) / Element(크리에이티브 요소) / Persona(타겟
페르소나). 엣지: HAS_TARGET_PERSONA / HAS_SEQUENCE / INCLUDES_ELEMENT / TRANSITIONS_TO.
db/README.md 의 "Graph" 절에 관계 정의와 설계 근거가 정리돼 있다.
"""
from __future__ import annotations

import kuzu

_NODE_TABLES = [
    "CREATE NODE TABLE Campaign(video_id INT64, brand_name STRING, industry_category STRING, "
    "product_category STRING, campaign_objective STRING, duration STRING, PRIMARY KEY(video_id))",
    "CREATE NODE TABLE Sequence(id STRING, video_id INT64, position INT64, role STRING, "
    "cut_index INT64, PRIMARY KEY(id))",
    "CREATE NODE TABLE Element(id STRING, video_id INT64, element_type STRING, "
    "element_subtype STRING, description STRING, cut_refs STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Persona(category STRING, PRIMARY KEY(category))",
]

_REL_TABLES = [
    "CREATE REL TABLE HAS_TARGET_PERSONA(FROM Campaign TO Persona)",
    "CREATE REL TABLE HAS_SEQUENCE(FROM Campaign TO Sequence, position INT64)",
    "CREATE REL TABLE INCLUDES_ELEMENT(FROM Sequence TO Element)",
    "CREATE REL TABLE TRANSITIONS_TO(FROM Element TO Element)",
]


def ensure_schema(conn: kuzu.Connection) -> None:
    """테이블이 이미 있으면 조용히 건너뛴다(Kùzu 는 CREATE TABLE IF NOT EXISTS 를 지원하지
    않아 실행 후 예외로 존재 여부를 판단한다 — db.chromadb.creative_search.get_or_create_collection
    과 같은 시도-후-무시 스타일)."""
    for ddl in _NODE_TABLES + _REL_TABLES:
        try:
            conn.execute(ddl)
        except Exception:
            pass
