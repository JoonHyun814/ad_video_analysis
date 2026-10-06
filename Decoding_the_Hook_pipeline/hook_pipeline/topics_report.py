"""토픽 단계 입출력: extract 결과 수집 → 토픽별 대표 키워드·대표 문서 → 영상별 피처 테이블."""
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from hook_pipeline.acoustic import FEATURE_NAMES
from hook_pipeline.extract import ACOUSTIC_FILE, ANALYSIS_FILE
from hook_pipeline.topics import TopicFit


def load_corpus(out_root: Path, keys: set[str] | None) -> list[dict]:
    """<out_root>/*/hook_analysis.json 중 기법 추출에 성공한 영상만 모은다."""
    records = []
    for path in sorted(out_root.glob(f"*/{ANALYSIS_FILE}")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if keys is not None and rec["key"] not in keys:
            continue
        if "methodology" not in rec:
            print(f"      [skip] {rec['key']}: 기법 추출 실패 결과")
            continue
        acoustic_path = path.parent / ACOUSTIC_FILE
        rec["acoustic"] = json.loads(acoustic_path.read_text(encoding="utf-8")) if acoustic_path.exists() else {}
        records.append(rec)
    return records


def to_document(rec: dict) -> str:
    """논문: 토픽은 design methodology 와 그 rationale 을 함께 사용해 도출한다."""
    return f"{rec['methodology']}: {rec['rationale']}"


def build_topic_info(fit: TopicFit, records: list[dict], docs: list[str]) -> list[dict]:
    """토픽별 라벨·크기·상위 10개 키워드(c-TF-IDF 가중치)·대표 문서."""
    info = []
    for topic_id in sorted(set(fit.topics)):
        members = [r for r, t in zip(records, fit.topics) if t == topic_id]
        info.append({
            "topic": topic_id,
            "label": "Outlier (noise)" if topic_id == -1 else _majority_methodology(members),
            "count": len(members),
            "top_words": [{"word": w, "weight": round(float(s), 4)} for w, s in fit.model.get_topic(topic_id) or []],
            "representative_docs": _representative(fit, topic_id, records, docs),
            "methodologies": Counter(r["methodology"] for r in members).most_common(),
        })
    return info


def _majority_methodology(members: list[dict]) -> str:
    """토픽 이름: 소속 문서들의 MLLM methodology 중 최빈값 (대소문자 무시)."""
    counts = Counter(r["methodology"].strip().lower() for r in members)
    top = counts.most_common(1)[0][0]
    return next(r["methodology"].strip() for r in members if r["methodology"].strip().lower() == top)


def _representative(fit: TopicFit, topic_id: int, records: list[dict], docs: list[str]) -> list[dict]:
    rep_docs = fit.model.get_representative_docs(topic_id) or []
    out = []
    for d in rep_docs:
        rec = records[docs.index(d)]
        out.append({"key": rec["key"], "methodology": rec["methodology"], "rationale": rec["rationale"]})
    return out


def build_feature_table(fit: TopicFit, records: list[dict], topic_info: list[dict]) -> pd.DataFrame:
    """영상별 대표 기법(할당 토픽) + 토픽 분포(기법 강도) + 음향 피처 10종. 논문의 GBDT 입력 직전 단계."""
    labels = {t["topic"]: t["label"] for t in topic_info}
    topic_ids = [t for t in sorted(set(fit.topics)) if t != -1]
    rows = []
    for i, rec in enumerate(records):
        row = {"key": rec["key"], "video_id": rec.get("video_id"), "title": rec["title"],
               "methodology": rec["methodology"], "topic": fit.topics[i], "topic_label": labels[fit.topics[i]]}
        row.update({f"topic_{t}": round(float(fit.distribution[i, j]), 4) for j, t in enumerate(topic_ids)})
        row.update({name: rec["acoustic"].get(name) for name in FEATURE_NAMES})
        rows.append(row)
    return pd.DataFrame(rows)


def save_outputs(
    out_dir: Path, fit: TopicFit, scores: list[dict], topic_info: list[dict], table: pd.DataFrame, embedding_model: str,
) -> None:
    """topic_info.json · perplexity_scores.json · hook_features.csv · bertopic_model/ 저장."""
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "topic_info.json", topic_info)
    _write_json(out_dir / "perplexity_scores.json", {"selected_candidate": fit.candidate, "scores": scores})
    table.to_csv(out_dir / "hook_features.csv", index=False, encoding="utf-8-sig")
    fit.model.save(str(out_dir / "bertopic_model"), serialization="safetensors",
                   save_ctfidf=True, save_embedding_model=embedding_model)


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
