FROM pytorch/pytorch:2.12.0-cuda12.6-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive
ENV NODE_VERSION=22.11.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    gnupg \
    build-essential \
    xz-utils \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Node.js 설치: NodeSource 대신 공식 바이너리 사용
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && node --version \
    && npm --version

# Claude Code 설치
RUN curl -fsSL https://claude.ai/install.sh | bash

# Codex CLI 설치
RUN npm install -g @openai/codex

ENV PATH="/root/.local/bin:${PATH}"

RUN claude --version || true \
    && codex --version || true

# Python 패키지 설치
# 새 패키지가 필요할 때마다 이 블록에 추가한다
RUN pip install --no-cache-dir --break-system-packages \
    mysql-connector-python \
    pymysql \
    opencv-python-headless \
    scenedetect \
    easyocr \
    "tensorflow[and-cuda]" \
    ffmpeg-python \
    git+https://github.com/soCzech/TransNetV2 \
    faster-whisper \
    nltk \
    "nemo_toolkit[asr]" \
    git+https://github.com/MahmoudAshraf97/ctc-forced-aligner.git \
    git+https://github.com/oliverguhr/deepmultilingualpunctuation.git \
    git+https://github.com/MahmoudAshraf97/demucs.git \
    librosa \
    pyloudnorm \
    soundfile \
    chromadb \
    sentence-transformers \
    tf-keras \
    duckduckgo-search \
    beautifulsoup4 \
    curl_cffi \
    anthropic \
    "mcp[cli]"

# whisper-diarization: diarize.py + helpers.py + diarization 서브패키지 설치
RUN git clone --depth 1 https://github.com/MahmoudAshraf97/whisper-diarization.git \
        /workspace/ad_video_analysis/tools/whisper_diarization \
    && pip install --no-cache-dir --break-system-packages /workspace/ad_video_analysis/tools/whisper_diarization

# TransNetV2 모델 가중치 다운로드 (pip 설치 시 placeholder만 들어있어 별도 취득 필요)
RUN set -e; \
    WEIGHTS_DIR=$(python3 -c "import os,transnetv2; print(os.path.join(os.path.dirname(transnetv2.__file__), 'transnetv2-weights'))") && \
    BASE="https://github.com/soCzech/TransNetV2/raw/master/inference/transnetv2-weights" && \
    curl -fsSL "$BASE/saved_model.pb" -o "$WEIGHTS_DIR/saved_model.pb" && \
    curl -fsSL "$BASE/variables/variables.index" -o "$WEIGHTS_DIR/variables/variables.index" && \
    curl -fsSL "$BASE/variables/variables.data-00000-of-00001" -o "$WEIGHTS_DIR/variables/variables.data-00000-of-00001"

WORKDIR /workspace

CMD ["/bin/bash"]