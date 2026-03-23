"""
UGC Engine - RunPod Serverless GPU Worker
==========================================
Runs MuseTalk v1.5 / SadTalker / Wav2Lip on RunPod GPU.
Receives job from Railway → Downloads assets from R2 → Generates video → Uploads to R2

MuseTalk v1.5 inference:
  python -m scripts.inference --inference_config <yaml> --result_dir <dir>
      --unet_model_path models/musetalkV15/unet.pth
      --unet_config models/musetalkV15/musetalk.json
      --version v15

Deploy: Build Docker image → Push to Docker Hub → Create RunPod Serverless Endpoint
"""

import os
import time
import uuid
import yaml
import subprocess
import shutil
import requests
import boto3
from botocore.config import Config

# モデルは初回ジョブ実行時にダウンロード（モジュール起動時ではない）
# RunPodのコンテナ起動タイムアウトを回避するため
_models_ready = False


MUSETALK_DIR = "/app/MuseTalk"
SADTALKER_DIR = "/app/SadTalker"
WAV2LIP_DIR = "/app/Wav2Lip"

# ---- R2 Client ----
def get_r2_client(input_data):
    return boto3.client(
        "s3",
        endpoint_url=input_data["r2_endpoint"],
        aws_access_key_id=input_data["r2_access_key"],
        aws_secret_access_key=input_data["r2_secret_key"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

def download_from_r2(r2, bucket, key, local_path):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    r2.download_file(bucket, key, local_path)
    print(f"Downloaded {key} -> {local_path}")

def upload_to_r2(r2, bucket, local_path, key):
    r2.upload_file(local_path, bucket, key, ExtraArgs={"ContentType": "video/mp4"})
    print(f"Uploaded {local_path} -> {key}")

# ---- MuseTalk v1.5 Generation ----
def run_musetalk(face_image_path, audio_path, output_path, work_dir):
    """
    Run MuseTalk v1.5 lip-sync generation.
    Uses YAML config as per official CLI: python -m scripts.inference --inference_config <yaml>
    """
    result_dir = os.path.join(work_dir, "musetalk_result")
    os.makedirs(result_dir, exist_ok=True)

    # Build inference YAML config
    config = {
        "task_0": {
            "video_path": face_image_path,  # Can be image or video
            "audio_path": audio_path,
        }
    }
    config_path = os.path.join(work_dir, "inference_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    cmd = [
        "python", "-m", "scripts.inference",
        "--inference_config", config_path,
        "--result_dir", result_dir,
        "--unet_model_path", f"{MUSETALK_DIR}/models/musetalkV15/unet.pth",
        "--unet_config", f"{MUSETALK_DIR}/models/musetalkV15/musetalk.json",
        "--version", "v15",
    ]
    print(f"Running MuseTalk: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600,
        cwd=MUSETALK_DIR,
        env={**os.environ, "FFMPEG_PATH": "/usr/bin/ffmpeg"},
    )
    if result.returncode != 0:
        print(f"stderr: {result.stderr[-1000:]}")
        raise RuntimeError(f"MuseTalk failed: {result.stderr[-500:]}")

    # Find the output .mp4 in result_dir
    mp4_files = []
    for root, dirs, files in os.walk(result_dir):
        for fn in files:
            if fn.endswith(".mp4"):
                mp4_files.append(os.path.join(root, fn))

    if not mp4_files:
        raise RuntimeError(f"MuseTalk produced no .mp4 output. stdout: {result.stdout[-500:]}")

    # Move the last generated mp4 to output_path
    shutil.move(mp4_files[-1], output_path)
    return output_path

# ---- SadTalker Generation ----
def run_sadtalker(face_image_path, audio_path, output_path, work_dir):
    """Run SadTalker - single image to talking head"""
    result_dir = os.path.join(work_dir, "sadtalker_result")
    os.makedirs(result_dir, exist_ok=True)

    cmd = [
        "python", "inference.py",
        "--driven_audio", audio_path,
        "--source_image", face_image_path,
        "--result_dir", result_dir,
        "--enhancer", "gfpgan",
        "--still",
        "--preprocess", "crop",
    ]
    print(f"Running SadTalker: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600,
        cwd=SADTALKER_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SadTalker failed: {result.stderr[-500:]}")

    result_files = [f for f in os.listdir(result_dir) if f.endswith(".mp4")]
    if not result_files:
        raise RuntimeError("SadTalker produced no output")

    generated = os.path.join(result_dir, sorted(result_files)[-1])
    shutil.move(generated, output_path)
    return output_path

# ---- Wav2Lip Generation ----
def run_wav2lip(face_image_path, audio_path, output_path, work_dir):
    """Run Wav2Lip for precise lip-sync"""
    cmd = [
        "python", "inference.py",
        "--checkpoint_path", "checkpoints/wav2lip_gan.pth",
        "--face", face_image_path,
        "--audio", audio_path,
        "--outfile", output_path,
        "--resize_factor", "1",
        "--nosmooth",
    ]
    print(f"Running Wav2Lip: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600,
        cwd=WAV2LIP_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Wav2Lip failed: {result.stderr[-500:]}")
    return output_path

# ---- Model Router ----
MODEL_RUNNERS = {
    "musetalk": run_musetalk,
    "sadtalker": run_sadtalker,
    "wav2lip": run_wav2lip,
}

# ---- RunPod Handler ----
def handler(event):
    """
    RunPod Serverless handler.
    Input: { job_id, face_image_key, audio_key, model, r2_bucket, r2_endpoint, ... }
    Output: { output_key, duration_seconds }
    """
    global _models_ready
    # 初回ジョブ時のみモデルをダウンロード（起動時ではなく実行時に行う）
    if not _models_ready:
        print("[Worker] First job - downloading models to Network Volume...")
        from download_models import ensure_models
        ensure_models()
        _models_ready = True
        print("[Worker] Models ready!")
    input_data = event["input"]
    job_id = input_data["job_id"]
    model = input_data.get("model", "musetalk")
    callback_url = input_data.get("callback_url")

    print(f"[Worker] Job {job_id} started | model: {model}")

    # GPU info log
    try:
        import subprocess as sp
        gpu_info = sp.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            timeout=5
        ).decode().strip()
        print(f"[Worker] GPU: {gpu_info}")
    except Exception:
        pass

    start_time = time.time()

    try:
        r2 = get_r2_client(input_data)
        bucket = input_data["r2_bucket"]

        # Create work directory
        work_dir = f"/tmp/jobs/{job_id}"
        os.makedirs(work_dir, exist_ok=True)

        # Download inputs from R2
        face_ext = input_data["face_image_key"].split(".")[-1]
        face_path = f"{work_dir}/face.{face_ext}"
        audio_path = f"{work_dir}/audio.wav"
        output_path = f"{work_dir}/output.mp4"

        download_from_r2(r2, bucket, input_data["face_image_key"], face_path)
        download_from_r2(r2, bucket, input_data["audio_key"], audio_path)

        # Run selected model
        runner = MODEL_RUNNERS.get(model)
        if not runner:
            raise ValueError(f"Unknown model: {model}. Available: {list(MODEL_RUNNERS.keys())}")

        # Pass work_dir for models that need intermediate directories
        runner(face_path, audio_path, output_path, work_dir)

        if not os.path.exists(output_path):
            raise RuntimeError(f"Output file not created: {output_path}")

        # Upload result to R2
        output_key = f"outputs/{job_id}.mp4"
        upload_to_r2(r2, bucket, output_path, output_key)

        duration = round(time.time() - start_time, 1)
        result = {
            "jobId": job_id,
            "status": "completed",
            "output_key": output_key,
            "duration_seconds": duration,
            "model": model,
        }

        # Callback to Railway (supplementary - Railway also polls)
        if callback_url:
            try:
                requests.post(callback_url, json=result, timeout=10)
            except Exception as e:
                print(f"Callback failed (non-fatal): {e}")

        print(f"[Worker] Job {job_id} completed in {duration}s → {output_key}")
        return result

    except Exception as e:
        duration = round(time.time() - start_time, 1)
        error_result = {
            "jobId": job_id,
            "status": "failed",
            "error": str(e),
            "duration_seconds": duration,
        }

        if callback_url:
            try:
                requests.post(callback_url, json=error_result, timeout=10)
            except Exception:
                pass

        print(f"[Worker] Job {job_id} FAILED after {duration}s: {e}")
        raise

    finally:
        if os.path.exists(f"/tmp/jobs/{job_id}"):
            shutil.rmtree(f"/tmp/jobs/{job_id}", ignore_errors=True)


# ---- RunPod Entry Point ----
if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
