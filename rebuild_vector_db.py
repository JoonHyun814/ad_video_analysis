"""output/vector_db 를 evaluation/ad_concept_production 통합 파이프라인으로 재구축한다.

video_id 별로 output/total/<id>/(레포 바깥 원본, 읽기 전용 — 절대 쓰지 않는다)에서
scenario_analysis.json·category_analysis.json 을 data/ad_concept_production/<id>/ 로 복사한
뒤, `python -m evaluation.cli --mode ad_concept_production` 한 번으로 concept+production 을
함께 추출(LLM 호출 2건: concept 1회 + production 1회)하고 ad_concept_reference/
ad_production_reference 양쪽에 적재한다. 이미 두 컬렉션에 다 적재된 video_id 는 건너뛴다
(재실행 안전 — 중단 후 이어서 돌려도 된다. concept_analysis.json/production_analysis.json
이 이미 있는 video_id 는 파이프라인 자체가 LLM 재호출 없이 파일만 다시 적재한다).

추출(LLM 호출)이 실제로 일어난 video_id 뒤에만 --interval 초 대기한다 — 이미 분석 파일이
있어 즉시 적재만 한 video_id 는 대기 없이 바로 다음으로 진행한다.

사용법 (레포 루트에서):
    python rebuild_vector_db.py --video_ids 1,7,8,9,10
    python rebuild_vector_db.py --video_ids 1-503 --interval 1800   # 전체 재구축(수일 소요)

로그는 --log(기본 rebuild_vector_db.log)에 append 된다 — 세션과 무관한 독립 프로세스로
띄웠을 때 진행 상황을 확인하는 유일한 창구다.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).parent
_SOURCE_ROOT = Path(r"C:\Analysis_workspace\ad_video_analysis\output\total")  # 읽기 전용, 절대 쓰지 않음
_DATA_DIR = _REPO_ROOT / "data" / "ad_concept_production"
_DB_PATH = _REPO_ROOT / "output" / "vector_db"

_CONCEPT_OUT = "concept_analysis.json"
_PRODUCTION_OUT = "production_analysis.json"


def _parse_ids(spec: str) -> list[int]:
    ids: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ids.update(range(int(start), int(end) + 1))
        else:
            ids.add(int(part))
    return sorted(ids)


def _log(log_path: Path, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _already_loaded(video_id: int) -> bool:
    """ad_concept_reference/ad_production_reference 양쪽에 이미 적재돼 있으면 True(재실행 스킵용)."""
    from db.chromadb.connection import get_client

    client = get_client(_DB_PATH)
    try:
        concept_col = client.get_collection("ad_concept_reference")
        has_concept = len(concept_col.get(ids=[f"ad:{video_id}:concept"])["ids"]) > 0
    except Exception:
        has_concept = False
    try:
        prod_col = client.get_collection("ad_production_reference")
        has_prod = len(prod_col.get(ids=[f"ad:{video_id}:profile"])["ids"]) > 0
    except Exception:
        has_prod = False
    return has_concept and has_prod


def _copy_if_exists(src_dir: Path, dst_dir: Path, filename: str) -> None:
    src = src_dir / filename
    if not src.exists():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / filename)


def _process_one(video_id: int, backend: str, log_path: Path) -> tuple[bool, bool]:
    """(성공 여부, LLM 추출이 실제로 일어났는지) 를 반환한다."""
    src = _SOURCE_ROOT / str(video_id)
    if not (src / "scenario_analysis.json").exists():
        _log(log_path, f"[{video_id}] 스킵 — {src} 에 scenario_analysis.json 없음")
        return False, False

    video_dir = _DATA_DIR / str(video_id)
    _copy_if_exists(src, video_dir, "scenario_analysis.json")
    _copy_if_exists(src, video_dir, "category_analysis.json")

    extracted = not ((video_dir / _CONCEPT_OUT).exists() and (video_dir / _PRODUCTION_OUT).exists())
    _log(log_path, f"[{video_id}] {'추출+적재 실행' if extracted else '분석 파일 이미 있음 -> 추출 스킵, 바로 적재'}")

    cmd = [sys.executable, "-m", "evaluation.cli", "--mode", "ad_concept_production",
           "--video_id", str(video_id), "--data_dir", str(_DATA_DIR),
           "--db_path", str(_DB_PATH), "--llm_backend", backend]
    _log(log_path, f"  $ {' '.join(cmd[2:])}")
    result = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.stdout:
        _log(log_path, f"    stdout: {result.stdout.strip()[-800:]}")
    if result.returncode != 0:
        _log(log_path, f"    [실패] returncode={result.returncode} stderr={result.stderr.strip()[-500:]}")
        return False, extracted
    return True, extracted


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video_ids", required=True, metavar="RANGE",
                   help="처리할 video_id 범위/목록. 예: 1-10 / 1,3,5 / 1-503")
    p.add_argument("--interval", type=int, default=1800, help="추출이 실제로 일어난 뒤 대기 시간(초, 기본 1800=30분)")
    p.add_argument("--llm_backend", default="claude", choices=("claude", "codex", "gemini", "claude_api"),
                   help="ad_concept_production 추출 백엔드 — claude: claude -p CLI(로그인 세션 필요) | "
                        "claude_api: Anthropic API 직접 호출(env/api.env ANTHROPIC_API_KEY 필요) | "
                        "codex: codex CLI | gemini: Gemini API(env/api.env GEMINI_API_KEY 필요)")
    p.add_argument("--log", type=Path, default=_REPO_ROOT / "rebuild_vector_db.log")
    args = p.parse_args()

    ids = _parse_ids(args.video_ids)
    log_path = args.log
    _log(log_path, f"=== 시작: {len(ids)}건 {ids} (interval={args.interval}s, backend={args.llm_backend}) ===")

    done, failed, skipped = [], [], []
    for i, video_id in enumerate(ids):
        if _already_loaded(video_id):
            _log(log_path, f"[{video_id}] 이미 두 컬렉션에 적재됨 -> 스킵")
            skipped.append(video_id)
            continue

        ok, extracted = _process_one(video_id, args.llm_backend, log_path)
        (done if ok else failed).append(video_id)
        _log(log_path, f"[{video_id}] {'완료' if ok else '실패'} (추출 발생={extracted})")

        if extracted and i < len(ids) - 1:
            _log(log_path, f"  추출 발생 -> {args.interval}초 대기 후 다음(video_id={ids[i + 1]})")
            time.sleep(args.interval)

    _log(log_path, f"=== 종료: 완료 {len(done)} / 실패 {len(failed)} / 스킵 {len(skipped)} ===")
    if failed:
        _log(log_path, f"  실패 목록: {failed}")


if __name__ == "__main__":
    main()
