"""카테고리 분류 조회 — shortform-pipeline 소스 RDS 의 category 테이블을 READ-ONLY 로 조회한다.

원본(v1_bridge._load_categories/_build_category_prompt/_enrich_category) 과 동일한 쿼리.
이 프로젝트엔 해당 카테고리 트리 테이블이 없어, 사용자 승인 하에 소스 RDS 접속 정보를
env/v5_category_db.env 로 복사해 SELECT 전용으로만 연결한다(쓰기 없음).
"""
from __future__ import annotations

import logging

from utils.env_loader import load_env

logger = logging.getLogger(__name__)

_ENV_PATH = "env/v5_category_db.env"
_CACHE: dict | None = None


def _connect():
    import pymysql
    import pymysql.cursors

    cfg = load_env(_ENV_PATH)
    return pymysql.connect(
        host=cfg["DB_HOST"], port=int(cfg.get("DB_PORT", 3306)),
        user=cfg["DB_USER"], password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def load_categories() -> dict:
    """category 테이블에서 C003 하위 depth=3 전체 로드 (부모 depth=2 정보 포함). 실패 시 빈 결과."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c3.id AS c3id, c3.name AS c3name,
                           c2.id AS c2id, c2.name AS c2name
                    FROM category c3
                    JOIN category c2 ON c2.id = c3.parentid
                    WHERE c3.categorytype = 'CATEGORY3'
                      AND c3.depth = 3
                      AND c3.usefg = 'Y'
                      AND c2.usefg = 'Y'
                      AND c2.id LIKE 'C003_%'
                    ORDER BY c2.sortorder, c3.sortorder
                """)
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[v5_m0_m3 category] load failed: {e}")
        return {"list": [], "c3map": {}}

    c3map = {r["c3id"]: {"c3name": r["c3name"], "c2id": r["c2id"], "c2name": r["c2name"]} for r in rows}
    _CACHE = {"list": rows, "c3map": c3map}
    logger.info(f"[v5_m0_m3 category] loaded {len(rows)} items")
    return _CACHE


def build_category_prompt() -> str:
    """GPT system prompt 에 넣을 카테고리 목록 텍스트."""
    cats = load_categories()
    return "\n".join(f"- {r['c3id']}: {r['c2name']} > {r['c3name']}" for r in cats["list"])


def enrich_category(analysis: dict) -> dict:
    """GPT 응답의 category3id 로 2depth 정보 자동 보강."""
    c3id = analysis.get("category3id")
    if not c3id:
        return analysis
    info = load_categories()["c3map"].get(c3id)
    if not info:
        logger.warning(f"[v5_m0_m3 category] unknown category3id: {c3id}")
        return analysis

    analysis["category3name"] = info["c3name"]
    analysis["category2id"] = info["c2id"]
    analysis["category2name"] = info["c2name"]
    analysis["categorypath"] = f"{info['c2name']} > {info['c3name']}"
    if not analysis.get("industry"):
        analysis["industry"] = info["c2name"]
    if not analysis.get("subcategory"):
        analysis["subcategory"] = info["c3name"]
    return analysis
