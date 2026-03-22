FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip git wget curl ffmpeg \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Python base deps
RUN pip install --no-cache-dir \
    torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118

RUN pip install --no-cache-dir \
    runpod boto3 requests numpy opencv-python-headless \
    Pillow pyyaml huggingface_hub

# ---- MuseTalk v1.5 ----
RUN git clone --depth 1 https://github.com/TMElyralab/MuseTalk.git /app/MuseTalk
WORKDIR /app/MuseTalk

# Install MuseTalk dependencies
RUN pip install --no-cache-dir -r requirements.txt || true
RUN pip install --no-cache-dir -U openmim && \
    mim install mmengine && \
    mim install "mmcv==2.0.1" && \
    mim install "mmdet==3.1.0" && \
    mim install "mmpose==1.1.0" || true

# Download MuseTalk weights via huggingface_hub
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='TMElyralab/MuseTalk', local_dir='/app/MuseTalk/models/musetalk'); \
print('MuseTalk weights downloaded')" 2>/dev/null || \
    echo "WARNING: MuseTalk weights download failed - download manually"

# Download shared model weights
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='stabilityai/sd-vae-ft-mse', local_dir='/app/MuseTalk/models/sd-vae'); \
snapshot_download(repo_id='openai/whisper-tiny', local_dir='/app/MuseTalk/models/whisper'); \
snapshot_download(repo_id='yzd-v/DWPose', local_dir='/app/MuseTalk/models/dwpose'); \
print('Shared weights downloaded')" 2>/dev/null || \
    echo "WARNING: Shared weights download failed"

# ---- SadTalker ----
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /app/SadTalker
WORKDIR /app/SadTalker
RUN pip install --no-cache-dir -r requirements.txt || true
RUN pip install --no-cache-dir gfpgan basicsr facexlib

# Download SadTalker weights
RUN mkdir -p checkpoints && \
    wget -q "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00229-model.pth.tar" \
    -O checkpoints/mapping_00229-model.pth.tar 2>/dev/null || true && \
    wget -q "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors" \
    -O checkpoints/SadTalker_V0.0.2_256.safetensors 2>/dev/null || true

# ---- Wav2Lip ----
RUN git clone --depth 1 https://github.com/Rudrabha/Wav2Lip.git /app/Wav2Lip
WORKDIR /app/Wav2Lip
RUN pip install --no-cache-dir librosa==0.9.2 numba

RUN mkdir -p checkpoints && \
    python -c "\
from huggingface_hub import hf_hub_download; \
hf_hub_download(repo_id='numz/wav2lip_studio', filename='Wav2Lip/wav2lip_gan.pth', local_dir='/tmp/wav2lip'); \
import shutil; shutil.move('/tmp/wav2lip/Wav2Lip/wav2lip_gan.pth', 'checkpoints/wav2lip_gan.pth'); \
print('Wav2Lip weights downloaded')" 2>/dev/null || \
    echo "WARNING: Wav2Lip weights download failed - download manually to checkpoints/wav2lip_gan.pth"

# ---- Worker ----
WORKDIR /app
COPY handler.py /app/handler.py
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt || true

CMD ["python", "/app/handler.py"]
