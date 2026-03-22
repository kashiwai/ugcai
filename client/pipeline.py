"""
UGC Engine - Full Pipeline Orchestrator
=========================================
One command to run the entire pipeline:
  台本生成 → 音声生成 → GPU動画生成 → 後処理 → 自動投稿

Usage:
  python pipeline.py --daily              # Full day (70 videos)
  python pipeline.py --count 10           # Custom count
  python pipeline.py --count 5 --dry-run  # Test without GPU/posting
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from config import *
from scripts import generate_scripts
from voice import generate_voice
from upload import get_r2_client, upload_file_to_r2
from postprocess import process_video, batch_process
from generate import submit_batch, check_job, get_download_url, download_video

OUTPUT_BASE = Path(__file__).parent.parent / "output"

def run_pipeline(count=70, model="musetalk", dry_run=False,
                 before_image=None, after_image=None, bgm_path=None):
    """
    Full end-to-end pipeline.
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_BASE / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    log = {"run_id": run_id, "count": count, "model": model, "steps": {}}
    print(f"\n{'='*60}")
    print(f"  UGC Engine - Full Pipeline")
    print(f"  Run ID:  {run_id}")
    print(f"  Count:   {count} videos")
    print(f"  Model:   {model}")
    print(f"  Dry Run: {dry_run}")
    print(f"  Output:  {run_dir}")
    print(f"{'='*60}\n")

    # ==============================
    # PHASE 1: Script Generation
    # ==============================
    t0 = time.time()
    print("[PHASE 1] Claude API → Script Generation")
    scripts = generate_scripts(count=count)
    scripts_path = run_dir / "scripts.json"
    with open(scripts_path, "w", encoding="utf-8") as f:
        json.dump(scripts, f, ensure_ascii=False, indent=2)
    log["steps"]["scripts"] = {"count": len(scripts), "time": round(time.time() - t0, 1)}
    print(f"  {len(scripts)} scripts in {log['steps']['scripts']['time']}s\n")

    # ==============================
    # PHASE 2: Voice Generation
    # ==============================
    t0 = time.time()
    print("[PHASE 2] VOICEVOX → Voice Generation")
    voices_dir = run_dir / "voices"
    voices_dir.mkdir(exist_ok=True)
    voice_results = []

    for i, script in enumerate(scripts):
        char_key = script.get("character", "miku")
        speaker_id = CHARACTERS.get(char_key, {}).get("voicevox_speaker_id", 2)
        voice_path = voices_dir / f"{i:04d}_{char_key}.wav"

        try:
            generate_voice(script["text"], speaker_id, str(voice_path))
            voice_results.append({"index": i, "path": str(voice_path), "ok": True})
        except Exception as e:
            print(f"  Warning: Voice #{i} failed: {e}")
            voice_results.append({"index": i, "path": None, "ok": False})

    ok_voices = [v for v in voice_results if v["ok"]]
    log["steps"]["voices"] = {"count": len(ok_voices), "time": round(time.time() - t0, 1)}
    print(f"  {len(ok_voices)} voices in {log['steps']['voices']['time']}s\n")

    if dry_run:
        print("[DRY RUN] Stopping before GPU processing")
        log["steps"]["gpu"] = "skipped (dry run)"
        save_log(log, run_dir)
        return log

    # ==============================
    # PHASE 3: Upload to R2 + GPU
    # ==============================
    t0 = time.time()
    print("[PHASE 3] Upload → R2 → RunPod GPU")
    r2 = get_r2_client()

    # Upload face images (once)
    for char_key, char_info in CHARACTERS.items():
        face_path = char_info["face_image"]
        if os.path.exists(face_path):
            face_key = f"faces/{char_key}.png"
            try:
                upload_file_to_r2(r2, face_path, face_key)
            except Exception:
                pass

    # Upload voices + submit jobs
    batch_jobs = []
    for vr in ok_voices:
        idx = vr["index"]
        script = scripts[idx]
        char_key = script.get("character", "miku")
        audio_key = f"audio/{run_id}/{idx:04d}.wav"

        try:
            upload_file_to_r2(r2, vr["path"], audio_key)
            batch_jobs.append({
                "face_image_key": f"faces/{char_key}.png",
                "audio_key": audio_key,
                "character": char_key,
                "script": script.get("text", ""),
                "model": model,
            })
        except Exception as e:
            print(f"  Warning: Upload #{idx} failed: {e}")

    # Submit batch to Railway → RunPod
    print(f"  Submitting {len(batch_jobs)} jobs to GPU...")
    result = submit_batch(batch_jobs)
    job_ids = [j["jobId"] for j in result["jobs"]]
    print(f"  {len(job_ids)} jobs submitted")

    # Wait for completion
    print(f"  Waiting for GPU processing...")
    completed = {}
    failed = []
    max_wait = 3600

    while len(completed) + len(failed) < len(job_ids):
        if time.time() - t0 > max_wait:
            print(f"  Timeout after {max_wait}s")
            break

        for jid in job_ids:
            if jid in completed or jid in failed:
                continue
            try:
                status = check_job(jid)
                if status["status"] == "completed":
                    completed[jid] = status.get("result", {})
                elif status["status"] == "failed":
                    failed.append(jid)
            except Exception:
                pass

        remaining = len(job_ids) - len(completed) - len(failed)
        if remaining > 0:
            print(f"  Progress: {len(completed)}/{len(job_ids)} done, {remaining} pending", end="\r")
            time.sleep(10)

    log["steps"]["gpu"] = {
        "completed": len(completed),
        "failed": len(failed),
        "time": round(time.time() - t0, 1),
    }
    print(f"\n  GPU: {len(completed)} done, {len(failed)} failed in {log['steps']['gpu']['time']}s\n")

    # ==============================
    # PHASE 4: Download raw videos
    # ==============================
    t0 = time.time()
    print("[PHASE 4] Download raw videos from R2")
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    downloaded = []
    for jid, res in completed.items():
        output_key = res.get("output_key")
        if not output_key:
            continue
        try:
            url = get_download_url(output_key)
            local_path = raw_dir / f"{jid}.mp4"
            download_video(url, str(local_path))
            downloaded.append(str(local_path))
        except Exception as e:
            print(f"  Warning: Download {jid} failed: {e}")

    log["steps"]["download"] = {"count": len(downloaded), "time": round(time.time() - t0, 1)}
    print(f"  {len(downloaded)} videos downloaded in {log['steps']['download']['time']}s\n")

    # ==============================
    # PHASE 5: Post-processing
    # ==============================
    t0 = time.time()
    print("[PHASE 5] Post-processing (telop/BGM/CTA)")
    final_dir = run_dir / "final"
    final_dir.mkdir(exist_ok=True)

    final_videos = []
    for i, raw_path in enumerate(downloaded):
        script_data = scripts[i] if i < len(scripts) else {}
        output_path = final_dir / f"final_{i:04d}_{script_data.get('character', 'unknown')}.mp4"

        try:
            process_video(
                raw_path, str(output_path), script_data,
                before_image=before_image,
                after_image=after_image,
                bgm_path=bgm_path,
            )
            final_videos.append(str(output_path))
        except Exception as e:
            print(f"  Warning: Post-process #{i} failed: {e}")

    log["steps"]["postprocess"] = {"count": len(final_videos), "time": round(time.time() - t0, 1)}
    print(f"  {len(final_videos)} videos processed in {log['steps']['postprocess']['time']}s\n")

    # ==============================
    # Summary
    # ==============================
    total_time = sum(s.get("time", 0) for s in log["steps"].values() if isinstance(s, dict))
    log["total_time"] = round(total_time, 1)
    save_log(log, run_dir)

    print(f"{'='*60}")
    print(f"  Pipeline Complete!")
    print(f"  Total Time:  {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"  Scripts:     {log['steps']['scripts']['count']}")
    print(f"  Voices:      {log['steps']['voices']['count']}")
    print(f"  GPU Done:    {log['steps']['gpu'].get('completed', 0)}")
    print(f"  Final:       {len(final_videos)}")
    print(f"  Output:      {final_dir}")
    print(f"{'='*60}\n")

    return log

def save_log(log, run_dir):
    log_path = run_dir / "pipeline_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

# ---- CLI ----
def main():
    parser = argparse.ArgumentParser(description="UGC Full Pipeline")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--daily", action="store_true", help="Generate 70 videos (1 day)")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=MODELS)
    parser.add_argument("--dry-run", action="store_true", help="Stop before GPU")
    parser.add_argument("--before", type=str, default=None, help="Before image path")
    parser.add_argument("--after", type=str, default=None, help="After image path")
    parser.add_argument("--bgm", type=str, default=None, help="BGM audio path")
    args = parser.parse_args()

    if args.daily:
        args.count = 70

    run_pipeline(
        count=args.count,
        model=args.model,
        dry_run=args.dry_run,
        before_image=args.before,
        after_image=args.after,
        bgm_path=args.bgm,
    )

if __name__ == "__main__":
    main()
