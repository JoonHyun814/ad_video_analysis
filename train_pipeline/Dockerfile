# train_pipeline 전용 학습 이미지 (Qwen VL LoRA 파인튜닝).
# 대상 GPU 드라이버: CUDA 12.8 지원(예: Driver 572.83).
# 베이스 이미지는 루트 Dockerfile과 동일한 pytorch/pytorch:2.12.0-cuda12.6-cudnn9-devel 을 쓰지만,
# unsloth 설치 과정에서 자체 호환 스택(torch 2.10.0 + nvidia-*-cu12 12.8.x 런타임 wheel)으로
# 교체된다 — 오히려 12.8 드라이버와 더 정확히 맞아떨어지므로 의도적으로 그대로 둔다.
# (실제 빌드 로그로 확인: torch 2.12.0+cu126 제거 → torch-2.10.0 + nvidia-cublas-cu12-12.8.4.1 등 설치)
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
# 35B 모델(약 70GB) 다운로드 가속 — huggingface_hub 1.x부터 hf_transfer 대신 Xet 사용
ENV HF_XET_HIGH_PERFORMANCE=1

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
# unsloth 가 trl/peft/transformers/accelerate/bitsandbytes/torch 를 서로 호환되는 버전으로
# 함께 설치한다 (베이스 이미지의 torch를 자체 버전으로 교체함 — 위 주석 참고).
# 새 패키지가 필요하면 이 블록에 추가한다.
RUN pip install --no-cache-dir --break-system-packages \
    unsloth \
    unsloth_zoo \
    bitsandbytes \
    pyyaml \
    datasets \
    pillow

# torch 설치만 빌드 타임에 검증한다. unsloth는 import 시점에 GPU accelerator를 요구해서
# (unsloth_zoo.device_type.get_device_type() 이 GPU 없으면 NotImplementedError 를 던짐)
# --gpus 없는 build 환경에서는 import 자체가 실패한다 — 정상 동작이며 버그가 아니다.
# unsloth 정상 임포트 여부는 `docker run --gpus all` 로 컨테이너를 띄운 뒤
# `python -c "import unsloth"` 로 별도 확인한다.
RUN python -c "import torch; print('torch', torch.__version__, 'cuda_build', torch.version.cuda)"

WORKDIR /workspace/ad_video_analysis

CMD ["/bin/bash"]
