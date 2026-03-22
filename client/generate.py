"""
UGC Engine - Main Generation Script
=====================================
Usage:
  python generate.py --count 50 --model musetalk
  python generate.py --count 10 --character miku --type 価格衝撃
  python generate.py --batch daily   # Generate full day's content (70 videos)

Run on Mac. Requires:
  - VOICEVOX Engine running locally (download from https://voicevox.hiroyuki.cloud/)
  - Python 3.11+ with: pip install anthropic requests boto3 tqdm
"""

import os
import sys
import json
import time
import argparse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

# Import sibling modules
sys.path.insert(0, os.path.dirname(__file__))
from config import *
from scripts import generate_scripts
from voice import generate_voice
from upload import upload_file_to_r2, get_r2_client

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---- API Helpers ----
def api_headers():
    return {"Content-Type": "application/json", "x-api-key": API_SECRET}

def submit_job(face_key, audio_key, character, script_text, model):
    """Submit single video generation job to Railway API"""
    resp = requests.post(
        f"{RAILWAY_API_URL}/api/job",
        headers=api_headers(),
        json={
            "face_image_key": face_key,
            "audio_key": audio_key,
            "character": character,
            "script": script_text,
            "model": model,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def submit_batch(jobs):
    """Submit batch of jobs to Railway API"""
    resp = requests.post(
        f"{RAILWAY_API_URL}/api/batch",
        headers=api_headers(),
        json={"jobs": jobs},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()

def check_job(job_id):
    """Check status of a job"""
    resp = requests.get(
        f"{RAILWAY_API_URL}/api/job/{job_id}",
        headers=api_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

def get_download_url(key):
    """Get presigned download URL for completed video"""
    resp = requests.post(
        f"{RAILWAY_API_URL}/api/download-url",
        headers=api_headers(),
        json={"key": key},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["url"]

def download_video(url, local_path):
    """Download video from R2"""
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(resp.content)

# ---- Main Pipeline ----
def generate_videos(count, character_filter=None, content_type=None, model=DEFAULT_MODEL):
    """
    Main pipeline: Script → Voice → Upload → GPU → Download
    """
    print(f"\n{'='*60}")
    print(f"  UGC Engine - Generating {count} videos")
    print(f"  Model: {model} | Character: {character_filter or 'ALL'}")
    print(f"{'='*60}\n")

    # ---- Step 1: Generate Scripts ----
    print("[1/6] Generating scripts with Claude API...")
    chars = list(CHARACTERS.keys())
    if character_filter:
        chars = [character_filter]

    all_scripts = generate_scripts(
        count=count,
        characters=chars,
        content_type=content_type,
    )
    print(f"  Generated {len(all_scripts)} scripts")

    # Save scripts
    scripts_file = OUTPUT_DIR / f"scripts_{int(time.time())}.json"
    with open(scripts_file, "w", encoding="utf-8") as f:
        json.dump(all_scripts, f, ensure_ascii=False, indent=2)
    print(f"  Saved to {scripts_file}")

    # ---- Step 2: Generate Voice ----
    print(f"\n[2/6] Generating voice with VOICEVOX...")
    voice_files = []
    for i, script in enumerate(tqdm(all_scripts, desc="Voice")):
        char_key = script["character"]
        speaker_id = CHARACTERS[char_key]["voicevox_speaker_id"]
        voice_path = OUTPUT_DIR / "voices" / f"{i:04d}_{char_key}.wav"
        voice_path.parent.mkdir(exist_ok=True)

        try:
            generate_voice(script["text"], speaker_id, str(voice_path))
            voice_files.append({"index": i, "path": str(voice_path), "script": script})
        except Exception as e:
            print(f"  Warning: Voice generation failed for {i}: {e}")
            continue

    print(f"  Generated {len(voice_files)} voice files")

    # ---- Step 3: Upload to R2 ----
    print(f"\n[3/6] Uploading assets to R2...")
    r2 = get_r2_client()
    upload_jobs = []

    for vf in tqdm(voice_files, desc="Upload"):
        char_key = vf["script"]["character"]
        face_image = CHARACTERS[char_key]["face_image"]

        # Upload face image (check if already uploaded)
        face_key = f"faces/{char_key}.png"
        if os.path.exists(face_image):
            upload_file_to_r2(r2, face_image, face_key)

        # Upload audio
        audio_key = f"audio/{int(time.time())}_{vf['index']:04d}.wav"
        upload_file_to_r2(r2, vf["path"], audio_key)

        upload_jobs.append({
            "face_image_key": face_key,
            "audio_key": audio_key,
            "character": char_key,
            "script": vf["script"]["text"],
            "model": model,
            "index": vf["index"],
        })

    print(f"  Uploaded {len(upload_jobs)} files")

    # ---- Step 4: Submit to GPU ----
    print(f"\n[4/6] Submitting {len(upload_jobs)} jobs to RunPod GPU...")
    batch_result = submit_batch(upload_jobs)
    job_ids = [j["jobId"] for j in batch_result["jobs"]]
    print(f"  Submitted {batch_result['count']} jobs")

    # ---- Step 5: Wait for completion ----
    print(f"\n[5/6] Waiting for GPU processing...")
    completed = {}
    failed = []
    max_wait = 1800  # 30 minutes
    start_wait = time.time()

    with tqdm(total=len(job_ids), desc="GPU Processing") as pbar:
        while len(completed) + len(failed) < len(job_ids):
            if time.time() - start_wait > max_wait:
                print(f"\n  Timeout! {len(job_ids) - len(completed) - len(failed)} jobs still pending")
                break

            for jid in job_ids:
                if jid in completed or jid in failed:
                    continue
                try:
                    status = check_job(jid)
                    if status["status"] == "completed":
                        completed[jid] = status.get("result", {})
                        pbar.update(1)
                    elif status["status"] == "failed":
                        failed.append(jid)
                        pbar.update(1)
                except Exception:
                    pass

            if len(completed) + len(failed) < len(job_ids):
                time.sleep(5)  # Poll every 5 seconds

    print(f"\n  Completed: {len(completed)} | Failed: {len(failed)}")

    # ---- Step 6: Download results ----
    print(f"\n[6/6] Downloading completed videos...")
    downloaded = []
    for jid, result in tqdm(completed.items(), desc="Download"):
        output_key = result.get("output_key")
        if not output_key:
            continue
        try:
            url = get_download_url(output_key)
            local_path = OUTPUT_DIR / "videos" / f"{jid}.mp4"
            local_path.parent.mkdir(exist_ok=True)
            download_video(url, str(local_path))
            downloaded.append(str(local_path))
        except Exception as e:
            print(f"  Warning: Download failed for {jid}: {e}")

    # ---- Summary ----
    print(f"\n{'='*60}")
    print(f"  Generation Complete!")
    print(f"  Scripts:    {len(all_scripts)}")
    print(f"  Voices:     {len(voice_files)}")
    print(f"  GPU Jobs:   {len(job_ids)}")
    print(f"  Completed:  {len(completed)}")
    print(f"  Downloaded: {len(downloaded)}")
    print(f"  Failed:     {len(failed)}")
    print(f"  Output:     {OUTPUT_DIR / 'videos'}")
    print(f"{'='*60}\n")

    return downloaded


# ---- CLI ----
def main():
    parser = argparse.ArgumentParser(description="UGC Video Generation Engine")
    parser.add_argument("--count", type=int, default=10, help="Number of videos to generate")
    parser.add_argument("--character", type=str, default=None, help="Character filter (e.g. miku, kenta)")
    parser.add_argument("--type", type=str, default=None, help="Content type filter")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, choices=MODELS, help="AI model to use")
    parser.add_argument("--batch", type=str, default=None, choices=["daily", "test"], help="Preset batch sizes")

    args = parser.parse_args()

    if args.batch == "daily":
        args.count = 70
    elif args.batch == "test":
        args.count = 3

    generate_videos(
        count=args.count,
        character_filter=args.character,
        content_type=args.type,
        model=args.model,
    )


if __name__ == "__main__":
    main()
