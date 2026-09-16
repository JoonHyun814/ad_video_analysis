"""ad_graph(Kùzu)에서 여러 캠페인에 걸친 패턴을 조회한다.

원시 Cypher 를 그대로 노출하지 않는다 — search_chromadb 가 db_path 를 LLM에게 맡기지 않는
것과 같은 이유로, 안전한 함수(role_element_frequency)만 도구로 올린다(db/chromadb/
tool_definitions.py 참고). campaign_graph()는 이 모듈의 CLI 전용이다.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from db.graph.connection import get_connection


def _rows(result, columns: list[str]) -> list[dict[str, Any]]:
    out = []
    while result.has_next():
        row = result.get_next()
        out.append(dict(zip(columns, row)))
    return out


def role_element_frequency(role: str, persona_category: str | None = None,
                            top_k: int = 10) -> list[dict[str, Any]]:
    """role(서사 역할)에 포함된 Element 를 element_type/element_subtype 별로 집계한다.

    persona_category 를 주면 그 페르소나를 타겟한 캠페인으로만 좁힌다.
    """
    conn = get_connection()
    top_k = max(1, int(top_k))
    if persona_category:
        query = (
            "MATCH (c:Campaign)-[:HAS_TARGET_PERSONA]->(:Persona {category: $persona}) "
            "MATCH (c)-[:HAS_SEQUENCE]->(:Sequence {role: $role})-[:INCLUDES_ELEMENT]->(e:Element) "
            f"RETURN e.element_type AS element_type, e.element_subtype AS element_subtype, count(*) AS cnt "
            f"ORDER BY cnt DESC LIMIT {top_k}"
        )
        params = {"role": role, "persona": persona_category}
    else:
        query = (
            "MATCH (:Sequence {role: $role})-[:INCLUDES_ELEMENT]->(e:Element) "
            f"RETURN e.element_type AS element_type, e.element_subtype AS element_subtype, count(*) AS cnt "
            f"ORDER BY cnt DESC LIMIT {top_k}"
        )
        params = {"role": role}
    result = conn.execute(query, parameters=params)
    return _rows(result, ["element_type", "element_subtype", "count"])


def campaign_graph(video_id: int) -> dict[str, Any]:
    """특정 캠페인의 Sequence/Element/Persona 를 한 번에 조회한다(그래프판 fetch_by_video_id)."""
    conn = get_connection()

    campaign_result = conn.execute(
        "MATCH (c:Campaign {video_id: $vid}) RETURN c.video_id, c.brand_name, "
        "c.industry_category, c.product_category, c.campaign_objective, c.duration",
        parameters={"vid": video_id},
    )
    campaign_rows = _rows(campaign_result, ["video_id", "brand_name", "industry_category",
                                             "product_category", "campaign_objective", "duration"])
    if not campaign_rows:
        return {"video_id": video_id, "found": False}

    persona_result = conn.execute(
        "MATCH (:Campaign {video_id: $vid})-[:HAS_TARGET_PERSONA]->(p:Persona) RETURN p.category",
        parameters={"vid": video_id},
    )
    persona_rows = _rows(persona_result, ["category"])

    sequence_result = conn.execute(
        "MATCH (:Campaign {video_id: $vid})-[:HAS_SEQUENCE]->(s:Sequence) "
        "OPTIONAL MATCH (s)-[:INCLUDES_ELEMENT]->(e:Element) "
        "RETURN s.position, s.role, s.cut_index, e.element_type, e.element_subtype, e.description "
        "ORDER BY s.position",
        parameters={"vid": video_id},
    )
    sequence_rows = _rows(sequence_result, ["position", "role", "cut_index",
                                             "element_type", "element_subtype", "description"])

    return {
        "video_id": video_id, "found": True, "campaign": campaign_rows[0],
        "personas": [r["category"] for r in persona_rows], "sequence": sequence_rows,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ad_graph(Kùzu) 패턴 조회")
    p.add_argument("--role", help="role_element_frequency 조회 — 서사 역할(예: HOOK)")
    p.add_argument("--persona", default=None, help="--role 과 함께 페르소나로 좁힐 때")
    p.add_argument("--top_k", type=int, default=10)
    p.add_argument("--video_id", type=int, help="campaign_graph 조회 — 특정 캠페인 전체")
    p.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON으로 출력")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.video_id is not None:
        result = campaign_graph(args.video_id)
    elif args.role:
        result = role_element_frequency(args.role, args.persona, args.top_k)
    else:
        raise SystemExit("--role 또는 --video_id 중 하나는 필요합니다.")

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
