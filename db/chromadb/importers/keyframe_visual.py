"""<data_root>/<video_id>/keyframes/*.jpg 를 스캔해 ad_visual_reference 컬렉션에 적재한다.

pipeline/keyframe.py 가 컷마다 남긴 대표 프레임(cut_XXX_frame_YYYYY.jpg)을 clip-ViT-B-32 로
직접 임베딩해 미리 계산된 벡터로 upsert 한다 — 컬렉션 자체의 embedding_function 은 검색 시
자연어 쿼리(한국어 포함)를 인코딩할 clip-ViT-B-32-multilingual-v1 로 등록해둔다
(db.chromadb.connection 참고, 두 모델은 같은 임베딩 공간을 공유).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from db.chromadb.connection import (
    db_path_for,
    get_client,
    get_clip_image_encoder,
    get_clip_text_embedding_function,
    get_or_create_collection,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_DATA_ROOT = _PROJECT_ROOT / "output" / "total"
_COLLECTION = "ad_visual_reference"
_DEFAULT_DB_PATH = db_path_for(_COLLECTION)
_FRAME_NAME_RE = re.compile(r"cut_(\d+)_frame_(\d+)")


def _collect_frames(data_root: Path) -> list[tuple[int, int, int, Path]]:
    """유효한 키프레임만 (video_id, cut_index, frame_number, path) 목록으로 모은다."""
    frames: list[tuple[int, int, int, Path]] = []
    for path in sorted(data_root.glob("*/keyframes/*.jpg")):
        video_dir = path.parent.parent.name
        try:
            video_id = int(video_dir)
        except ValueError:
            print(f"  skip (non-numeric dir): {video_dir}", file=sys.stderr)
            continue
        m = _FRAME_NAME_RE.match(path.stem)
        if not m:
            print(f"  skip (unexpected filename): {path.name}", file=sys.stderr)
            continue
        frames.append((video_id, int(m.group(1)), int(m.group(2)), path))
    return frames


def upsert_batch(frames: list[tuple[int, int, int, Path]], db_path: Path, collection: str) -> None:
    """키프레임 이미지를 CLIP 으로 임베딩해 한 번에 upsert 한다."""
    from PIL import Image

    client = get_client(db_path)
    col = get_or_create_collection(client, collection, embedding_function=get_clip_text_embedding_function())

    images = [Image.open(path).convert("RGB") for *_, path in frames]
    encoder = get_clip_image_encoder()
    embeddings = encoder.encode(images, convert_to_numpy=True).tolist()

    ids = [f"{vid}:cut_{cut:03d}" for vid, cut, _, _ in frames]
    metadatas: list[dict[str, Any]] = [
        {"video_id": vid, "cut_index": cut, "frame_number": frame, "image_path": str(path)}
        for vid, cut, frame, path in frames
    ]
    col.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)
    print(f"[keyframe_visual] {len(ids)}건 upsert 완료 (collection={collection}, db={db_path})")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="키프레임 이미지 → ChromaDB(ad_visual_reference) 적재")
    p.add_argument("--data_root", type=Path, default=_DEFAULT_DATA_ROOT,
                   help="<data_root>/<video_id>/keyframes/*.jpg 스캔")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB_PATH, help="ChromaDB 저장 경로")
    p.add_argument("--collection", default=_COLLECTION)
    p.add_argument("--rebuild", action="store_true", help="기존 컬렉션 삭제 후 재적재")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if not args.data_root.exists():
        print(f"[오류] data_root 없음: {args.data_root}", file=sys.stderr)
        sys.exit(1)

    frames = _collect_frames(args.data_root)
    if not frames:
        print("[오류] 적재할 키프레임 없음", file=sys.stderr)
        sys.exit(1)
    print(f"[keyframe_visual] 적재 대상: {len(frames)}건  db={args.db_path}")

    if args.rebuild:
        client = get_client(args.db_path)
        try:
            client.delete_collection(args.collection)
            print(f"[keyframe_visual] 기존 컬렉션 삭제: {args.collection}")
        except Exception:
            pass

    upsert_batch(frames, args.db_path, args.collection)


if __name__ == "__main__":
    main()
