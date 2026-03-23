FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 最低限のシステム依存
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip git wget curl ffmpeg \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# PyTorch (CUDA 11.8)
RUN pip install --no-cache-dir \
    torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118

# 共通 Python パッケージ
RUN pip install --no-cache-dir \
    runpod boto3 requests numpy opencv-python-headless \
    Pillow pyyaml huggingface_hub

# MuseTalk (コードのみ)
RUN git clone --depth 1 https://github.com/TMElyralab/MuseTalk.git /app/MuseTalk
WORKDIR /app/MuseTalk
RUN pip install --no-cache-dir -r requirements.txt || true
RUN pip install --no-cache-dir -U openmim && \
    mim install mmengine && \
    mim install "mmcv==2.0.1" && \
    mim install "mmdet==3.1.0" && \
    mim install "mmpose==1.1.0" || true

# MuseTalk モデルをビルド時にベイク（起動時ダウンロード不要・即座に動作）
RUN mkdir -p /app/MuseTalk/models && python3 -c "\
from huggingface_hub import snapshot_download; \
print('[1/3] TMElyralab/MuseTalk (~3.2GB)...'); \
snapshot_download(repo_id='TMElyralab/MuseTalk', local_dir='/app/MuseTalk/models/', ignore_patterns=['*.git*', '.gitattributes']); \
print('[2/3] sd-vae-ft-mse -> models/sd-vae/ (~335MB)...'); \
snapshot_download(repo_id='stabilityai/sd-vae-ft-mse', local_dir='/app/MuseTalk/models/sd-vae/', ignore_patterns=['*.git*', '.gitattributes']); \
print('[3/3] whisper-tiny -> models/whisper/ (~75MB)...'); \
snapshot_download(repo_id='openai/whisper-tiny', local_dir='/app/MuseTalk/models/whisper/', ignore_patterns=['*.git*', '.gitattributes']); \
print('All models ready!')"

# SadTalker (コードのみ)
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /app/SadTalker
WORKDIR /app/SadTalker
RUN pip install --no-cache-dir -r requirements.txt || true
RUN pip install --no-cache-dir gfpgan basicsr facexlib

# Wav2Lip (コードのみ)
RUN git clone --depth 1 https://github.com/Rudrabha/Wav2Lip.git /app/Wav2Lip
WORKDIR /app/Wav2Lip
RUN pip install --no-cache-dir librosa==0.9.2 numba

# ---- Worker ----
WORKDIR /app
COPY worker/handler.py /app/handler.py
COPY worker/download_models.py /app/download_models.py
COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt || true

CMD ["python", "/app/handler.py"]
