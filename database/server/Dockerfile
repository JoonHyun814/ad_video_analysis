# server 전용 경량 이미지 — ChromaDB MCP 검색 서버(`server/mcp_server.py`) 하나만 돌린다.
# 루트 Dockerfile(PyTorch+CUDA, 28GB, GPU 학습·OCR·STT 등 전체 파이프라인용)과 별도로,
# 검색 서버 하나만 위해 그 스택 전체를 띄울 필요가 없어 CUDA/TensorFlow/학습 의존성을 전부
# 걷어낸다. 임베딩(BAAI/bge-m3)도 검색 1건 처리에는 CPU 로 충분하다.
#
# 코드는 이미지에 COPY 하지 않고 리포를 그대로 bind mount 한다 — 코드가 바뀌어도 재빌드 없이
# 컨테이너만 재시작하면 반영된다. db/chromadb/connection.py 의 DATA_ROOT 가
# `<repo>/data` 상대경로로 고정돼 있으므로, 마운트 시 리포 구조(db/, server/, data/)를 그대로
# 유지해야 한다.
#
# 빌드 (build context = ad_video_analysis/):
#   cd ad_video_analysis
#   docker build -t chromadb-mcp -f server/Dockerfile .
#
# 실행 (내부망 8765 노출, HF 모델 캐시를 호스트에 영구 보관):
#   docker run -d --name chromadb-mcp --restart unless-stopped \
#       -p 8765:8765 \
#       -v "$(pwd)":/app \
#       -v "$(pwd)/../.cache/huggingface:/root/.cache/huggingface" \
#       chromadb-mcp

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/root/.cache/huggingface

# torch 는 CPU 전용 wheel 로 설치 — GPU/CUDA wheel(수 GB)을 받지 않기 위함.
# rank_bm25(hybrid_search) / kuzu(graph_query) 는 search_chromadb_hybrid/search_graph_pattern
# 도구가 import 시점에 필요 — 없으면 서버 기동 자체가 실패한다. pillow 는 keyframe_visual
# 임포터(이 서버가 직접 쓰진 않지만 같은 컨테이너로 적재도 돌릴 수 있게) 용.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install --no-cache-dir \
        chromadb \
        sentence-transformers \
        "mcp[cli]<2.0" \
        rank_bm25 \
        kuzu \
        pillow

WORKDIR /app

CMD ["python", "-m", "server.mcp_server"]
