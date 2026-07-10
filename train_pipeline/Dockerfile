# train_pipeline 전용 학습 이미지 (Qwen VL LoRA 파인튜닝).
# 대상 GPU 드라이버: CUDA 12.8 지원(예: Driver 572.83) — 이 이미지는 cuda12.6 런타임을 쓰며,
# NVIDIA 드라이버는 자신의 지원 버전 이하의 CUDA 런타임과 하위 호환되므로 12.8 드라이버에서 문제없이 동작한다.
# 베이스는 루트 Dockerfile과 통일: pytorch/pytorch:2.12.0-cuda12.6-cudnn9-devel
#
# 빌드 (build context = ad_video_analysis/):
#   cd ad_video_analysis
#   docker build -t ad-video-train -f train_pipeline/Dockerfile .
#
# 실행 (80gb-3-6-VL-35B-A3B.yaml 기준 — /data 아래 데이터셋·출력 마운트):
#   docker run --rm -it --gpus all \
#       -v "$(pwd)":/workspace/ad_video_analysis \
#       -v /path/to/data_20260710:/data/data_20260710 \
#       -v /path/to/outputs:/data/outputs \
#       -v /path/to/hf_cache:/data/.cache/huggingface \
#       -w /workspace/ad_video_analysis \
#       ad-video-train
#
#   # 컨테이너 안에서
#   claude   # 로그인/설정 (최초 1회 ANTHROPIC 인증 필요)
#   python -m train_pipeline.cli --config train_pipeline/configs/80gb-3-6-VL-35B-A3B \
#       --out_dir /data/outputs/20260710

FROM pytorch/pytorch:2.12.0-cuda12.6-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive
ENV NODE_VERSION=22.11.0
# 35B 모델(약 70GB) 다운로드 가속
ENV HF_HUB_ENABLE_HF_TRANSFER=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    gnupg \
    build-essential \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Node.js 설치 (Claude Code CLI 요구사항) — 루트 Dockerfile과 동일 방식
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && node --version \
    && npm --version

# Claude Code 설치
RUN curl -fsSL https://claude.ai/install.sh | bash

ENV PATH="/root/.local/bin:${PATH}"
RUN claude --version || true

# train_pipeline 학습 의존성.
# unsloth 가 trl/peft/transformers/accelerate/bitsandbytes 를 베이스 이미지의 torch(2.12.0+cu126)와
# 호환되는 버전으로 함께 설치한다. 새 패키지가 필요하면 이 블록에 추가한다.
RUN pip install --no-cache-dir --break-system-packages \
    unsloth \
    unsloth_zoo \
    bitsandbytes \
    pyyaml \
    datasets \
    pillow \
    hf_transfer

# 설치 직후 torch·unsloth 임포트 가능 여부 확인 (GPU 없는 빌드 환경이라 CUDA 가용성 자체는 검사하지 않음).
# 여기서 실패하면 unsloth 설치 과정에서 torch 버전이 어긋난 것 — pip install 블록을 다시 점검해야 한다.
RUN python -c "import torch, unsloth; print('torch', torch.__version__, 'cuda_build', torch.version.cuda)"

WORKDIR /workspace/ad_video_analysis

CMD ["/bin/bash"]
