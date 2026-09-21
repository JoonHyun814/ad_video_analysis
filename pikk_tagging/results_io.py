"""태깅 결과 폴더(<root>/<video>/tags.json) 로딩."""
import json
from pathlib import Path


def save_json(path: Path, data: object) -> None:
    """부모 폴더를 만들고 UTF-8 JSON 으로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_tag_documents(pred_dir: Path) -> dict[str, dict]:
    """pred_dir 하위 폴더마다 tags.json 을 읽어 {video_key: 문서} 로 반환한다."""
    docs: dict[str, dict] = {}
    for path in sorted(pred_dir.glob("*/tags.json")):
        docs[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
    if not docs:
        raise SystemExit(f"[오류] tags.json 없음: {pred_dir}/*/tags.json")
    return docs
