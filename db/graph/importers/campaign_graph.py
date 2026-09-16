"""category_analysis / ad_production_reference / ad_concept_reference ChromaDB 컬렉션을 읽어
ad_graph(Kùzu) 그래프(Campaign/Sequence/Element/Persona)를 구성한다.

원본 JSON을 다시 스캔하지 않는다 — category.py/production_reference.py/concept_reference.py
가 이미 정규화해 적재해둔 ChromaDB 메타데이터를 그대로 재사용한다(원본이 `output/total/`와
`data/ad_concept_production/`로 소스가 갈리는 문제를 신경 쓸 필요가 없어진다).

`role_sequence`(category_analysis.json, 쉼표 구분 문자열)는 scenario_analysis.json의
cut_index와 형식적으로 연결돼 있지 않다 — 이 임포터는 "i번째 역할 ↔ 그 비디오 Element 들의
cut_refs 합집합에서 i번째로 작은 cut_index" 라는 위치 대응을 **best-effort 가정**으로 쓴다
(LLM이 "씬 순서별로" 역할을 나열하라는 프롬프트 지시를 실제로 따랐다는 전제 — 강제되지 않으므로
어긋날 수 있다).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from typing import Any

from db.chromadb.connection import db_path_for, get_client
from db.graph.connection import DB_PATH, get_connection
from db.graph.schema import ensure_schema

_CATEGORY_COLLECTION = "category_analysis"
_PRODUCTION_COLLECTION = "ad_production_reference"
_CONCEPT_COLLECTION = "ad_concept_reference"


def _parse_cut_refs(value: str) -> list[int]:
    """콤마로 join된 cut_refs 문자열(예: "1,4,5")을 정수 리스트로 되돌린다."""
    if not value:
        return []
    out = []
    for part in str(value).split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def _load_categories(client_factory) -> list[dict[str, Any]]:
    client = client_factory(db_path_for(_CATEGORY_COLLECTION))
    col = client.get_collection(_CATEGORY_COLLECTION)
    if col.count() == 0:
        return []
    raw = col.get(include=["metadatas"])
    return raw["metadatas"]


def _load_elements(client_factory) -> list[dict[str, Any]]:
    client = client_factory(db_path_for(_PRODUCTION_COLLECTION))
    col = client.get_collection(_PRODUCTION_COLLECTION)
    if col.count() == 0:
        return []
    raw = col.get(where={"record_kind": "element"}, include=["metadatas", "documents"])
    elements = []
    for eid, meta, doc in zip(raw["ids"], raw["metadatas"], raw["documents"]):
        elements.append({
            "id": eid,
            "video_id": meta.get("video_id"),
            "element_type": meta.get("element_type", "other"),
            "element_subtype": meta.get("element_subtype", "other"),
            "description": doc or "",
            "cut_refs": _parse_cut_refs(meta.get("cut_refs", "")),
        })
    return elements


def _load_personas(client_factory) -> dict[int, str]:
    client = client_factory(db_path_for(_CONCEPT_COLLECTION))
    col = client.get_collection(_CONCEPT_COLLECTION)
    if col.count() == 0:
        return {}
    raw = col.get(include=["metadatas"])
    personas: dict[int, str] = {}
    for meta in raw["metadatas"]:
        vid = meta.get("video_id")
        category = meta.get("target_persona_category")
        if vid is not None and category:
            personas[vid] = category
    return personas


def _upsert_node(conn, label: str, pk_field: str, pk_value: Any, props: dict[str, Any]) -> None:
    params = {"pk": pk_value, **props}
    if props:
        set_clause = ", ".join(f"n.{k} = ${k}" for k in props)
        query = f"MERGE (n:{label} {{{pk_field}: $pk}}) SET {set_clause}"
    else:
        query = f"MERGE (n:{label} {{{pk_field}: $pk}})"
    conn.execute(query, parameters=params)


def _merge_edge(conn, rel: str, from_label: str, from_pk_field: str, from_pk_value: Any,
                 to_label: str, to_pk_field: str, to_pk_value: Any, props: dict[str, Any] | None = None) -> None:
    props = props or {}
    params = {"from_pk": from_pk_value, "to_pk": to_pk_value, **props}
    prop_clause = ""
    if props:
        prop_clause = " {" + ", ".join(f"{k}: ${k}" for k in props) + "}"
    query = (f"MATCH (a:{from_label} {{{from_pk_field}: $from_pk}}), (b:{to_label} {{{to_pk_field}: $to_pk}}) "
             f"MERGE (a)-[:{rel}{prop_clause}]->(b)")
    conn.execute(query, parameters=params)


def build_graph(conn) -> dict[str, int]:
    """세 ChromaDB 컬렉션을 읽어 그래프를 채운다. 건수 요약을 반환한다."""
    categories = _load_categories(get_client)
    elements = _load_elements(get_client)
    personas = _load_personas(get_client)

    elements_by_video: dict[int, list[dict[str, Any]]] = {}
    for e in elements:
        elements_by_video.setdefault(e["video_id"], []).append(e)

    # 1) Element 노드 — 모든 캠페인 처리 전에 먼저 넣어야 이후 INCLUDES_ELEMENT/TRANSITIONS_TO
    #    엣지가 MATCH 할 수 있다.
    for e in elements:
        _upsert_node(conn, "Element", "id", e["id"], {
            "video_id": e["video_id"], "element_type": e["element_type"],
            "element_subtype": e["element_subtype"], "description": e["description"],
            "cut_refs": ",".join(str(c) for c in e["cut_refs"]),
        })

    # 2) Persona 노드(dedup)
    for category in set(personas.values()):
        _upsert_node(conn, "Persona", "category", category, {})

    # 3) Campaign + Sequence + 해당 엣지
    seq_count = 0
    for meta in categories:
        video_id = meta.get("video_id")
        if video_id is None:
            continue
        _upsert_node(conn, "Campaign", "video_id", video_id, {
            "brand_name": meta.get("brand_name", "") or "",
            "industry_category": str(meta.get("industry_category", "") or ""),
            "product_category": str(meta.get("product_category", "") or ""),
            "campaign_objective": meta.get("campaign_objective", "") or "",
            "duration": str(meta.get("duration", "") or ""),
        })

        persona_category = personas.get(video_id)
        if persona_category:
            _merge_edge(conn, "HAS_TARGET_PERSONA", "Campaign", "video_id", video_id,
                        "Persona", "category", persona_category)

        roles = [r.strip() for r in str(meta.get("role_sequence", "") or "").split(",") if r.strip()]
        video_elements = elements_by_video.get(video_id, [])
        cut_universe = sorted({c for e in video_elements for c in e["cut_refs"]})

        for position, role in enumerate(roles, start=1):
            cut_index = cut_universe[position - 1] if position - 1 < len(cut_universe) else -1
            seq_id = f"{video_id}:seq:{position}"
            _upsert_node(conn, "Sequence", "id", seq_id, {
                "video_id": video_id, "position": position, "role": role, "cut_index": cut_index,
            })
            _merge_edge(conn, "HAS_SEQUENCE", "Campaign", "video_id", video_id,
                        "Sequence", "id", seq_id, {"position": position})
            seq_count += 1

            if cut_index == -1:
                continue
            for e in video_elements:
                if cut_index in e["cut_refs"]:
                    _merge_edge(conn, "INCLUDES_ELEMENT", "Sequence", "id", seq_id,
                                "Element", "id", e["id"])

    # 4) TRANSITIONS_TO — 같은 video_id + element_type 안에서 cut_refs 최솟값 기준 연속 연결
    transitions = 0
    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for e in elements:
        if not e["cut_refs"]:
            continue
        groups.setdefault((e["video_id"], e["element_type"]), []).append(e)
    for group in groups.values():
        ordered = sorted(group, key=lambda e: min(e["cut_refs"]))
        for a, b in zip(ordered, ordered[1:]):
            _merge_edge(conn, "TRANSITIONS_TO", "Element", "id", a["id"], "Element", "id", b["id"])
            transitions += 1

    return {
        "campaigns": len(categories), "elements": len(elements), "personas": len(set(personas.values())),
        "sequences": seq_count, "transitions": transitions,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션 → ad_graph(Kùzu) 그래프 구성")
    p.add_argument("--rebuild", action="store_true", help="기존 그래프 DB 삭제 후 재구성")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.rebuild and DB_PATH.exists():
        shutil.rmtree(DB_PATH)
        print(f"[campaign_graph] 기존 그래프 삭제: {DB_PATH}")

    conn = get_connection()
    ensure_schema(conn)
    summary = build_graph(conn)
    print(f"[campaign_graph] 적재 완료: {summary}  db={DB_PATH}", file=sys.stdout)


if __name__ == "__main__":
    main()
