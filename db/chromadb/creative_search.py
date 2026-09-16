"""벡터 DB 2개(ad_concept_reference/ad_production_reference)에서 참조 광고를 검색한다.

MCP 서버(mcp_server.py)와 generation/v5_m0_m3 의 Anthropic 툴콜 경로(llm_adapter.py) 양쪽이
이 모듈의 순수 함수를 그대로 호출한다 — 전송 계층(MCP stdio vs Anthropic tool_use)만 다르고
검색 로직은 하나다. generation/retrieval_pipeline/retrieval.py 도 결정적 검색 실행 단계(M5)에서
이 모듈을 직접 호출한다.

용도별로 컬렉션과 툴을 분리한다:
- search_concept_reference : ad_concept_reference — M3(컨셉 발산)이 전략적으로 비슷한
  기존 광고의 소구·포지셔닝·타겟을 참고할 때.
- search_production_reference: ad_production_reference — 컨셉 확정 후 M5(스크립트)~M9(콘티)·
  스토리보드 HTML 이 연출·촬영 기법·캐스팅을 참고할 때. 각 결과에 대표 크리에이티브
  요소(notable_elements)를 함께 반환한다.

어느 단계가 어느 툴을 받는지는 generation/v5_m0_m3/llm_adapter.py 가 stage 별로 결정한다
(모든 단계에 두 툴을 다 열어주지 않는다 — M3=concept, M4~M9/STORYBOARD_HTML=production).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import chromadb

from db.chromadb.connection import db_path_for, get_client, get_or_create_collection
from db.chromadb.importers.concept_reference import CONCEPT_COLLECTION
from db.chromadb.importers.production_reference import PRODUCTION_COLLECTION
from evaluation.creative import element_schema as es

_CONCEPT_DB_PATH = db_path_for(CONCEPT_COLLECTION)
_PRODUCTION_DB_PATH = db_path_for(PRODUCTION_COLLECTION)

_MAX_TOP_K = 20

# 호출 로깅(선택) — 환경변수로만 켜진다. 호출측(예: generation/v5_m0_m3)이 REFERENCE_RETRIEVAL_LOG_PATH
# 를 지정하면 도구 호출 1건마다 JSONL 로 append 한다. MCP(stdio 서브프로세스) 경유든 Anthropic
# tool_use(같은 프로세스) 경유든 이 두 환경변수만 셋업하면 동일하게 기록된다 — 로깅 로직을
# 전송 계층(mcp_server.py/llm_adapter.py)에 중복 구현하지 않기 위해 여기 한 곳에 둔다.
# REFERENCE_RETRIEVAL_LOG_STAGE 로 "어느 단계가 호출했는지"(예: "M1") 태그를 남길 수 있다.
_LOG_PATH_ENV = "REFERENCE_RETRIEVAL_LOG_PATH"
_LOG_STAGE_ENV = "REFERENCE_RETRIEVAL_LOG_STAGE"

# self-reference 정책(선택) — 환경변수로만 켜진다(generation/v5_m0_m3/llm_adapter.py 의
# set_self_reference() 가 셋업). "지금 분석 중인 광고 자기 자신"이 검색 결과에 걸렸을 때의
# 처리 방식. 기존 방영 광고를 M3 로 재추출해 M4~M9 를 돌리는 실험(generation/v5_m0_m3/
# existing_ad_adapter.py)에서만 쓰인다 — 일반 URL 소재 파이프라인은 이 값을 설정하지 않으므로
# 동작이 전혀 바뀌지 않는다.
#   REFERENCE_RETRIEVAL_SELF_MODE=restore : 자기 자신 히트에 실제 scenario_analysis/
#     production_analysis 원본(cast/scenes/elements)을 덧붙이고 "그대로 재현하라"는 지시를 준다
#     — retrieval 이 self-hit을 찾았을 때 원본 복원 수준까지 도달할 수 있는지 검증하는 용도.
#   REFERENCE_RETRIEVAL_SELF_MODE=exclude : 자기 자신을 결과에서 아예 제외한다 — self-hit
#     없이 순수 타 광고 레퍼런스만으로 돌렸을 때를 보기 위한 ablation.
_SELF_VIDEO_ID_ENV = "REFERENCE_RETRIEVAL_SELF_VIDEO_ID"
_SELF_MODE_ENV = "REFERENCE_RETRIEVAL_SELF_MODE"
_EXISTING_AD_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "ad_concept_production"


def _beats_text(scene: dict[str, Any], types: tuple[str, ...]) -> str:
    beats = [b for b in (scene.get("beats") or []) if isinstance(b, dict) and b.get("type") in types]
    return " / ".join(str(b.get("description", "")).strip() for b in beats if b.get("description"))


def _build_restore_note(detail: dict[str, Any]) -> str:
    """복원 지시문을 원본의 실제 컷 수·캐스트·엔딩에 맞춰 구체적으로 조립한다.

    [사용자 피드백 반영] 1차 버전(정적 문구)은 self-hit을 찾아도 M9 가 표준 '15초=4~6씬 통합'
    규칙·인물 수 축소·surreal 은유 창작 습관을 그대로 따라가 원본과 씬 수·캐스트·엔딩이 크게
    갈렸다(video 86: 10컷→6씬, 캐스트 5명→사실상 1명, CG 추격 엔딩 소실 / video 25: 캐스트
    9명→3명, 실제 활동 전부 소실, 원본에 없는 '빛 입자' 은유 발명). 아래 4개 지시로 그 구체적
    실패 지점을 정면으로 겨냥한다 — 이 노트는 self-hit 이 있을 때만(즉 restore 모드에서만)
    붙으므로 일반 URL 소재 파이프라인(브랜드 브리프로 새 컨셉을 발산하는 경우)에는 영향 없다."""
    scenes = detail.get("scenes") or []
    cast = detail.get("cast") or []
    cut_count = len(scenes)
    cast_count = len(cast)
    cast_list = "; ".join(
        f"{c.get('id', '')}: {str(c.get('description', ''))[:40]}" for c in cast if isinstance(c, dict)
    )
    ending = scenes[-1] if scenes else {}
    ending_desc = _beats_text(ending, ("background", "action")) or "(엔딩 컷 정보 없음)"
    ending_dialogue = _beats_text(ending, ("dialogue",))

    return (
        "이 결과는 지금 콘티를 쓰고 있는 광고의 원본 그 자체다(self-reference). 아래 "
        "source_cast/source_scenes/source_production_notes/source_elements 는 실제로 제작·방영된 "
        "정확한 기록이다. 다음 네 가지를 반드시 지켜라 — 새로 창작하지 말고 이 원본을 최대한 "
        "그대로 재현하는 것이 최우선이다:\n"
        f"1) 컷 구조 우선: 원본은 정확히 {cut_count}개 컷으로 구성된다. '15초 광고는 4~6개 씬으로 "
        "통합' 같은 일반 규칙보다 이 원본 컷 분할·순서·타이밍을 우선하라 — 컷을 인위적으로 "
        "4~6개로 뭉개 캐릭터나 사건을 통째로 빠뜨리지 말고, scenes 를 원본 컷 수에 최대한 "
        "가깝게 나누거나 shots(마이크로샷)로 원본 컷마다 대응시켜 전체 컷 수·리듬을 보존하라.\n"
        f"2) 인물 구성 고정: 원본 캐스트는 정확히 {cast_count}명이다 — {cast_list}. 이 인원 "
        "구성과 각자의 역할을 그대로 유지하라 — 인물을 합치거나 빼서 단순화하지 마라. 원본에 "
        "여러 인물이 등장하는 장면(리액션, 앙상블 활동 등)을 1인 시점으로 축소하지 마라.\n"
        "3) 새 은유·오브제 창작 금지: 원본에 없는 추상적 시각 은유(예: 빛의 입자, 상징적 오브제, "
        "새로 지어낸 캐릭터)를 만들지 말고, 원본에 실제로 등장한 그래픽·UI·소품·동작·자막만 "
        "그대로 묘사하라.\n"
        f"4) 엔딩 필수 반영: 원본의 마지막 컷은 다음과 같다 — {ending_desc}"
        + (f" (대사/내레이션: {ending_dialogue})" if ending_dialogue else "") + ". 이 엔딩 비주얼을 "
        "마지막 씬에 반드시 그대로 반영하라. 학습된 정형화된 클로징(예: '제품이 중앙에 정면으로 "
        "놓이고 조명 반사만 스치는 락다운 샷')으로 대체하지 마라 — 그것이 이 원본의 실제 엔딩이 "
        "아니라면 쓰지 마라."
    )


def _load_existing_ad_detail(video_id: int) -> dict[str, Any] | None:
    """data/ad_concept_production/<video_id>/ 의 scenario_analysis·production_analysis 원본."""
    root = _EXISTING_AD_DATA_ROOT / str(video_id)
    scenario_path = root / "scenario_analysis.json"
    if not scenario_path.exists():
        return None
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    production_path = root / "production_analysis.json"
    production = json.loads(production_path.read_text(encoding="utf-8")) if production_path.exists() else {}
    return {
        "cast": scenario.get("cast", []),
        "scenes": scenario.get("scenes", []),
        "production_notes": scenario.get("production_notes", ""),
        "elements": production.get("elements", []),
    }


def _apply_self_reference_policy(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """search_production_reference 결과에 self-reference 정책(restore/exclude)을 적용한다.

    환경변수가 없으면(일반 호출) 결과를 그대로 반환 — 기존 동작 무변화.
    """
    self_id_raw = os.environ.get(_SELF_VIDEO_ID_ENV)
    mode = os.environ.get(_SELF_MODE_ENV, "")
    if not self_id_raw or mode not in ("restore", "exclude"):
        return results
    try:
        self_id = int(self_id_raw)
    except ValueError:
        return results

    if mode == "exclude":
        return [r for r in results if r.get("video_id") != self_id]

    out: list[dict[str, Any]] = []
    for r in results:
        if r.get("video_id") == self_id:
            detail = _load_existing_ad_detail(self_id)
            if detail:
                r = {
                    **r,
                    "exact_source_match": True,
                    "restoration_note": _build_restore_note(detail),
                    "source_cast": detail["cast"],
                    "source_scenes": detail["scenes"],
                    "source_production_notes": detail["production_notes"],
                    "source_elements": detail["elements"],
                }
        out.append(r)
    return out


def _log_call(tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
    log_path = os.environ.get(_LOG_PATH_ENV)
    if not log_path:
        return
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stage": os.environ.get(_LOG_STAGE_ENV, ""),
        "tool": tool,
        "arguments": arguments,
        "result_count": result.get("count") if isinstance(result, dict) else None,
        "video_ids": [r.get("video_id") for r in result.get("results", [])] if isinstance(result, dict) else None,
        "segment_filter": result.get("segment_filter") if isinstance(result, dict) else None,
        "error": result.get("error") if isinstance(result, dict) else None,
    }
    try:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 로깅 실패가 검색 자체를 막으면 안 됨

# chromadb.PersistentClient 캐시 — db_path 당 1개만 연다. MCP 서버(장수命 프로세스)에서
# search_production_reference 가 매 호출마다 새 PersistentClient 를 열고(프로필 쿼리) 매칭된
# 영상 수만큼 추가로 또 열던(요소 조회 루프) 구버전이 실측상 claude -p 경유 호출을 30분 넘게
# 멈추게 했다(같은 sqlite 파일에 대한 반복 PersistentClient 오픈이 원인으로 보임 — 직접 파이썬
# 호출/Anthropic API 툴콜 경로는 문제없이 빨랐다는 점과 대조됨). 클라이언트 재사용 + 요소 조회를
# 매칭 건별 N회 대신 단일 $in 쿼리로 합쳐 해결했다.
_clients: dict[str, "chromadb.ClientAPI"] = {}


def _client(db_path: str | Path):
    key = str(db_path)
    if key not in _clients:
        _clients[key] = get_client(db_path)
    return _clients[key]


def _with_kind(where: dict | None, record_kind: str) -> dict:
    cond = {"record_kind": {"$eq": record_kind}}
    return {"$and": [cond, where]} if where else cond


# search_production_reference 의 segment_column 으로 쓸 수 있는 컬럼과 허용 값 — element_schema.py 의
# enum 사전에서 파생해 항상 최신 상태를 유지한다(하드코딩 이중 관리 방지).
PRODUCTION_SEGMENT_COLUMNS: dict[str, tuple[str, ...]] = {
    "industry_category": es.INDUSTRY_CATEGORIES,
    "product_category_norm": tuple(sorted({v for vals in es.PRODUCT_CATEGORY_NORM.values() for v in vals})),
    "product_subtype": tuple(sorted({v for vals in es.PRODUCT_SUBTYPE.values() for v in vals})),
    "target_gender": es.TARGET_GENDER,
    "duration_bucket": es.DURATION_BUCKETS,
    "usp_category": es.USP_CATEGORY,
    "positioning_category": es.POSITIONING_CATEGORY,
    "price_tier": es.PRICE_TIER,
    "execution_style": es.EXECUTION_STYLE,
    # M5(스크립트)가 "이 세그먼트에서 이미 많이 쓰인 엔진·서사형식"을 확인해 반-수렴하는 용도
    # (module5.md L2 recentengines / L2.5 형식 반-수렴). tone_register 는 필터 컬럼에서 제외 —
    # 6종뿐이라 필터보다는 search_production_reference 의 notable_elements 로 자연어 검색이 낫다.
    "persuasion_engine": es.PERSUASION_ENGINE,
    "narrative_form": es.NARRATIVE_FORM,
}

# search_concept_reference 의 segment_column — concept_evaluation.json 어휘(evaluation/concept/
# concept_evaluation.py) 기준. target_gender/duration_bucket/price_tier 는 creative 쪽에서
# 크로스 적재된 값이라 있는 영상만 걸린다(db/chromadb/importers/concept_reference.py 참고).
CONCEPT_SEGMENT_COLUMNS: dict[str, tuple[str, ...]] = {
    "industry_category": es.CONCEPT_INDUSTRY_CATEGORY,
    "target_persona_category": es.TARGET_PERSONA_CATEGORY,
    "usp_category": es.USP_CATEGORY,
    "positioning_category": es.POSITIONING_CATEGORY,
    "appeal_type": es.APPEAL_TYPE,
    "perceived_value_category": es.PERCEIVED_VALUE_CATEGORY,
    "message_strategy_category": es.MESSAGE_STRATEGY_CATEGORY,
    "target_gender": es.TARGET_GENDER,
    "duration_bucket": es.DURATION_BUCKETS,
    "price_tier": es.PRICE_TIER,
    # strategy_analysis.json(m3) 기반 — M3 가 "이 렌즈를 쓴 기존 컨셉"을 직접 찾을 때.
    "lens": es.CONCEPT_LENS,
    "claimtag": es.CONCEPT_CLAIMTAG,
}

_SEGMENT_VALUE_NOTE = (
    "이 값들은 evaluation/creative/element_schema.py 의 enum 사전에서 그대로 가져온 것이며 "
    "정확히 일치해야만 필터링된다(오타·유사어·의역 불가 — 예: 'home_appliance'는 되지만 "
    "'가전제품'·'homeappliance'는 안 된다). 특히 '_norm'/'_category' 가 붙은 컬럼은 표준화된 "
    "고정 enum 이라 반드시 이 목록에 있는 값 그대로만 써야 한다. 하고 싶은 필터링 의도에 정확히 "
    "맞는 값이 이 목록에 없으면 segment_column/segment_value 를 아예 생략하고 query_text(자연어 "
    "의미 검색)만으로 찾아라 — 비슷해 보이는 값을 추측해서 넣지 마라(결과 0건이 나올 수 있다)."
)


def list_concept_segment_columns() -> dict[str, Any]:
    """search_concept_reference 의 segment_column/segment_value 로 쓸 수 있는 컬럼별 허용 값 목록."""
    out = {"columns": {col: list(vals) for col, vals in CONCEPT_SEGMENT_COLUMNS.items()}, "note": _SEGMENT_VALUE_NOTE}
    _log_call("list_concept_segment_columns", {}, {})
    return out


def list_production_segment_columns() -> dict[str, Any]:
    """search_production_reference 의 segment_column/segment_value 로 쓸 수 있는 컬럼별 허용 값 목록."""
    out = {"columns": {col: list(vals) for col, vals in PRODUCTION_SEGMENT_COLUMNS.items()}, "note": _SEGMENT_VALUE_NOTE}
    _log_call("list_production_segment_columns", {}, {})
    return out


def _validate_segment(tool: str, columns: dict[str, tuple[str, ...]], list_tool: str,
                      segment_column: str | None, segment_value: str | None) -> tuple[dict | None, dict | None]:
    """(where, error_out) 쌍을 반환한다 — error_out 이 None 이 아니면 그대로 반환하면 된다."""
    if not (segment_column and segment_value):
        return None, None
    if segment_column not in columns:
        return None, {
            "error": f"알 수 없는 segment_column: {segment_column!r}. "
                     f"{list_tool} 로 유효한 컬럼을 확인하거나, 정확히 맞는 값이 없으면 "
                     f"segment_column/segment_value 를 생략하고 query_text 자연어 검색만 사용하세요.",
            "results": [],
        }
    if segment_value not in columns[segment_column]:
        return None, {
            "error": f"{segment_column!r} 에 허용되지 않는 값: {segment_value!r} — 이 필터는 "
                     f"exact match 라 {list_tool} 가 준 값 그대로만 통합니다. 정확히 맞는 값이 "
                     f"없으면 segment_column/segment_value 를 생략하고 query_text 자연어 검색만 "
                     f"사용하세요(비슷한 값을 추측해서 넣지 마세요).",
            "results": [],
        }
    return {segment_column: {"$eq": segment_value}}, None


def warm_up() -> None:
    """임베딩 모델(bge-m3)을 미리 로드한다 — 첫 검색 호출이 모델 로딩까지 떠안아 느려지는 대신,
    MCP 서버 기동 시점에 그 비용을 미리 치른다(mcp_server.py 가 호출). 두 컬렉션은 서로 다른
    저장소(data/ad_concept_reference/, data/ad_production_reference/)라 각각 예열한다."""
    get_or_create_collection(_client(_CONCEPT_DB_PATH), CONCEPT_COLLECTION)
    get_or_create_collection(_client(_PRODUCTION_DB_PATH), PRODUCTION_COLLECTION)


def search_concept_reference(
    query_text: str,
    segment_column: str | None = None,
    segment_value: str | None = None,
    top_k: int = 5,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """query_text 의미 유사도로 전략적으로 비슷한 참조 광고를 ad_concept_reference 에서 top_k 건 검색한다.
    db_path 를 안 주면(None) `data/ad_concept_reference/` 를 쓴다.

    M3(컨셉 발산)이 "이 브리프와 비슷한 상황에서 어떤 소구·포지셔닝·타겟이 쓰였는지" 참고할 때
    쓴다 — 연출/촬영 디테일은 search_production_reference 몫이다.
    """
    _args = {"query_text": query_text, "segment_column": segment_column,
              "segment_value": segment_value, "top_k": top_k}
    query_text = (query_text or "").strip()
    if not query_text:
        out = {"error": "query_text 는 필수입니다.", "results": []}
        _log_call("search_concept_reference", _args, out)
        return out
    top_k = max(1, min(int(top_k or 5), _MAX_TOP_K))

    where, err = _validate_segment("search_concept_reference", CONCEPT_SEGMENT_COLUMNS,
                                   "list_concept_segment_columns", segment_column, segment_value)
    if err:
        _log_call("search_concept_reference", _args, err)
        return err

    client = _client(db_path or _CONCEPT_DB_PATH)
    col = get_or_create_collection(client, CONCEPT_COLLECTION)
    if col.count() == 0:
        out = {"results": [], "count": 0, "note": "ad_concept_reference 컬렉션이 비어 있습니다."}
        _log_call("search_concept_reference", _args, out)
        return out

    kwargs: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": min(top_k, col.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    res = col.query(**kwargs)

    results = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        results.append({
            "video_id": meta.get("video_id"),
            "similarity_distance": round(dist, 4),
            "industry_category": meta.get("industry_category"),
            "product_category": meta.get("product_category"),
            "target_persona_category": meta.get("target_persona_category"),
            "usp_category": meta.get("usp_category"),
            "positioning_category": meta.get("positioning_category"),
            "appeal_type": meta.get("appeal_type"),
            "perceived_value_category": meta.get("perceived_value_category"),
            "message_strategy_category": meta.get("message_strategy_category"),
            "summary": doc,
        })

    out = {
        "results": results,
        "count": len(results),
        "segment_filter": {"column": segment_column, "value": segment_value} if where else None,
    }
    if where and not results:
        out["note"] = (
            f"{segment_column}={segment_value!r} 값 자체는 유효하지만 이 세그먼트에 적재된 "
            f"광고가 없습니다(enum 값 존재 ≠ 데이터 존재). segment_column/segment_value 를 "
            f"생략하고 query_text 만으로 다시 검색해 보세요."
        )
    _log_call("search_concept_reference", _args, out)
    return out


def search_production_reference(
    query_text: str,
    segment_column: str | None = None,
    segment_value: str | None = None,
    top_k: int = 5,
    elements_per_ad: int = 4,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """query_text 의미 유사도로 연출이 비슷한 참조 광고를 ad_production_reference 에서 top_k 건
    검색하고, 각 광고의 대표 크리에이티브 요소(elements_per_ad 건)를 함께 반환한다.
    db_path 를 안 주면(None) `data/ad_production_reference/` 를 쓴다.

    컨셉이 확정된 뒤 M5(스크립트)~M9(콘티)·스토리보드 HTML 이 훅·카피 장치·구도·카메라워크·
    캐스팅 같은 연출 기법을 참고할 때 쓴다. video_ids 로 특정 영상들만 좁힐 필요는 없다 —
    query_text 에 컨셉의 소구·톤을 직접 서술하면 그 컨셉과 맞는 연출을 새로 재검색한다.
    """
    _args = {"query_text": query_text, "segment_column": segment_column,
              "segment_value": segment_value, "top_k": top_k}
    query_text = (query_text or "").strip()
    if not query_text:
        out = {"error": "query_text 는 필수입니다.", "results": []}
        _log_call("search_production_reference", _args, out)
        return out
    top_k = max(1, min(int(top_k or 5), _MAX_TOP_K))

    seg_where, err = _validate_segment("search_production_reference", PRODUCTION_SEGMENT_COLUMNS,
                                       "list_production_segment_columns", segment_column, segment_value)
    if err:
        _log_call("search_production_reference", _args, err)
        return err

    client = _client(db_path or _PRODUCTION_DB_PATH)
    col = get_or_create_collection(client, PRODUCTION_COLLECTION)
    if col.count() == 0:
        out = {"results": [], "count": 0, "note": "ad_production_reference 컬렉션이 비어 있습니다."}
        _log_call("search_production_reference", _args, out)
        return out

    where = _with_kind(seg_where, "profile")
    kwargs: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": min(top_k, col.count()),
        "include": ["documents", "metadatas", "distances"],
        "where": where,
    }
    res = col.query(**kwargs)

    matched = list(zip(res["documents"][0], res["metadatas"][0], res["distances"][0]))
    video_ids = [meta.get("video_id") for _, meta, _ in matched if meta.get("video_id") is not None]

    # 매칭된 영상 수만큼 반복 조회하지 않고 단일 $in 쿼리로 한 번에 가져온다(성능/안정성 — 위 주석 참고).
    elements_by_video: dict[Any, list[dict[str, Any]]] = {}
    if elements_per_ad > 0 and video_ids:
        elem_where = _with_kind({"video_id": {"$in": video_ids}}, "element")
        elem_res = col.get(where=elem_where, include=["documents", "metadatas"])
        for doc, meta in zip(elem_res["documents"], elem_res["metadatas"]):
            elements_by_video.setdefault(meta.get("video_id"), []).append({
                "type": meta.get("element_type"), "subtype": meta.get("element_subtype"), "description": doc,
            })

    results: list[dict[str, Any]] = []
    for doc, meta, dist in matched:
        video_id = meta.get("video_id")
        entry: dict[str, Any] = {
            "video_id": video_id,
            "similarity_distance": round(dist, 4),
            "industry_category": meta.get("industry_category"),
            "product_category_norm": meta.get("product_category_norm"),
            "product_category_raw": meta.get("product_category_raw"),
            "target_gender": meta.get("target_gender"),
            "usp_category": meta.get("usp_category"),
            "positioning_category": meta.get("positioning_category"),
            "price_tier": meta.get("price_tier"),
            "execution_style": meta.get("execution_style"),
            "narrative_pattern": meta.get("narrative_pattern"),
            "summary": doc,
        }
        if elements_per_ad > 0:
            entry["notable_elements"] = elements_by_video.get(video_id, [])[:elements_per_ad]
        results.append(entry)

    results = _apply_self_reference_policy(results)
    out = {
        "results": results,
        "count": len(results),
        "segment_filter": {"column": segment_column, "value": segment_value} if seg_where else None,
    }
    if seg_where and not results:
        out["note"] = (
            f"{segment_column}={segment_value!r} 값 자체는 유효하지만 이 세그먼트에 적재된 "
            f"광고가 없습니다(enum 값 존재 ≠ 데이터 존재). segment_column/segment_value 를 "
            f"생략하고 query_text 만으로 다시 검색해 보세요."
        )
    _log_call("search_production_reference", _args, out)
    return out


# ── 도구 정의(Anthropic tool_use 스키마) — MCP 서버와 API 백엔드 툴콜 경로가 공유하는 단일 소스 ──
# 용도별로 나눠, 호출측(llm_adapter.py)이 stage 에 맞는 목록만 골라 쓴다.

TOOL_DEFINITIONS_CONCEPT: list[dict[str, Any]] = [
    {
        "name": "list_concept_segment_columns",
        "description": (
            "전략 레퍼런스 광고 벡터 DB(ad_concept_reference)에서 필터링 가능한 세그먼트 컬럼과 "
            "각 컬럼의 허용 값 목록을 반환한다. search_concept_reference 에 segment_column/"
            "segment_value 를 넣기 **전에 반드시 먼저 호출**해서 정확한 값을 확인하라 — 고정 "
            "enum 이라 이 목록에 있는 값 그대로만 통한다(오타·의역·추측 불가). 의도에 정확히 맞는 "
            "값이 없으면 segment_column/segment_value 를 쓰지 말고 search_concept_reference 의 "
            "query_text(자연어 의미 검색)만으로 찾아라."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_concept_reference",
        "description": (
            "이 제품/브리프(타겟·USP·포지셔닝)와 전략적으로 비슷한 기존 광고를 벡터 DB에서 "
            "검색한다 — 그 광고가 어떤 소구·포지셔닝·타겟 정의를 썼는지 참고할 때 쓴다(연출·촬영 "
            "기법은 다루지 않는다). query_text 는 자연어 자유 서술이라 항상 안전하다. 특정 산업/"
            "타겟유형/USP유형/포지셔닝/소구유형으로 먼저 좁히고 싶을 때만 segment_column + "
            "segment_value 를 함께 지정하되, list_concept_segment_columns 가 반환한 값과 정확히 "
            "같아야 한다. **정확히 맞는 enum 값이 없거나 확신이 없으면 segment_column/"
            "segment_value 를 아예 생략하고 query_text 만으로(자연어) 검색하라.**"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text": {"type": "string", "description": "검색할 제품/타깃/USP/포지셔닝 등을 서술한 자연어 텍스트(항상 안전)"},
                "segment_column": {"type": "string", "enum": list(CONCEPT_SEGMENT_COLUMNS.keys()),
                                    "description": "필터링할 세그먼트 컬럼명(선택, exact-match enum — list_concept_segment_columns 로 먼저 값 확인 필수)"},
                "segment_value": {"type": "string",
                                   "description": "segment_column 의 정확한 enum 값(선택, 추측 금지)"},
                "top_k": {"type": "integer", "description": "가져올 참조 광고 개수(기본 5, 최대 20)", "default": 5},
            },
            "required": ["query_text"],
        },
    },
]

TOOL_DEFINITIONS_PRODUCTION: list[dict[str, Any]] = [
    {
        "name": "list_production_segment_columns",
        "description": (
            "연출 레퍼런스 광고 벡터 DB(ad_production_reference)에서 필터링 가능한 세그먼트 컬럼과 "
            "각 컬럼의 허용 값 목록을 반환한다. search_production_reference 에 segment_column/"
            "segment_value 를 넣기 **전에 반드시 먼저 호출**해서 정확한 값을 확인하라 — 특히 "
            "product_category_norm 처럼 '_norm' 이 붙은 컬럼은 표준화된 고정 enum 이라 이 목록에 "
            "있는 값 그대로만 통한다(오타·의역·추측 불가). 의도에 정확히 맞는 값이 없으면 "
            "segment_column/segment_value 를 쓰지 말고 search_production_reference 의 "
            "query_text(자연어 의미 검색)만으로 찾아라."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_production_reference",
        "description": (
            "컨셉·스크립트의 소구·톤·서사와 비슷하게 연출된 기존 광고를 벡터 DB에서 검색하고, "
            "각 광고의 대표 크리에이티브 요소(훅·캐스팅·서사패턴·감각 데모 등)를 함께 반환한다 — "
            "촬영기법·카피장치·구도를 참고할 때 쓴다(전략·포지셔닝은 다루지 않는다). query_text "
            "는 자연어 자유 서술이라 항상 안전하다. 특정 산업/제품군/타겟성별/USP유형/포지셔닝/"
            "가격대/연출스타일로 먼저 좁히고 싶을 때만 segment_column + segment_value 를 함께 "
            "지정하되, list_production_segment_columns 가 반환한 값과 정확히 같아야 한다. "
            "**정확히 맞는 enum 값이 없거나 확신이 없으면 segment_column/segment_value 를 아예 "
            "생략하고 query_text 만으로(자연어) 검색하라.**"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text": {"type": "string", "description": "검색할 연출·톤·서사·기법 등을 서술한 자연어 텍스트(항상 안전)"},
                "segment_column": {"type": "string", "enum": list(PRODUCTION_SEGMENT_COLUMNS.keys()),
                                    "description": "필터링할 세그먼트 컬럼명(선택, exact-match enum — list_production_segment_columns 로 먼저 값 확인 필수)"},
                "segment_value": {"type": "string",
                                   "description": "segment_column 의 정확한 enum 값(선택, 추측 금지)"},
                "top_k": {"type": "integer", "description": "가져올 참조 광고 개수(기본 5, 최대 20)", "default": 5},
            },
            "required": ["query_text"],
        },
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """도구 이름 → 함수 디스패치(Anthropic tool_use 루프 전용, MCP 서버는 FastMCP 가 직접 라우팅)."""
    if name == "list_concept_segment_columns":
        return list_concept_segment_columns()
    if name == "search_concept_reference":
        return search_concept_reference(**arguments)
    if name == "list_production_segment_columns":
        return list_production_segment_columns()
    if name == "search_production_reference":
        return search_production_reference(**arguments)
    return {"error": f"unknown tool: {name}"}
