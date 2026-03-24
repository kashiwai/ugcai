FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 最低限のシステム依存
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip git wget curl ffmpeg \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    gcc g++ build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# PyTorch (CUDA 11.8) - mmcv cu118 wheel が確認済みで存在する
RUN pip install --no-cache-dir \
    torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118

# mmcv Pre-built binary wheel (cu118/torch2.0 - CDN確認済み、chumpy不要)
RUN pip install --no-cache-dir mmcv==2.0.0 --only-binary=:all: \
    -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html

# mmdet + mmpose via mim (mmcv already installed)
RUN pip install --no-cache-dir -U openmim && \
    mim install mmengine && \
    mim install "mmdet==3.1.0" && \
    mim install "mmpose==1.1.0"

# numpy < 2.0 に強制 (xtcoco 互換性のため)
RUN pip install --no-cache-dir "numpy<2.0" --force-reinstall

# 共通 Python パッケージ
RUN pip install --no-cache-dir \
    runpod boto3 requests opencv-python-headless==4.9.0.80 \
    Pillow pyyaml huggingface_hub gdown \
    diffusers==0.30.2 accelerate transformers==4.39.2 \
    soundfile einops omegaconf ffmpeg-python moviepy librosa \
    imageio[ffmpeg]

# MuseTalk (コードのみ, モデルは初回ジョブ時にDL)
RUN git clone --depth 1 https://github.com/TMElyralab/MuseTalk.git /app/MuseTalk
WORKDIR /app/MuseTalk
RUN pip install --no-cache-dir -r requirements.txt || true

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
