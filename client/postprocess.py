"""
UGC Engine - Post Processing Pipeline
=======================================
Takes raw MuseTalk/SadTalker output and adds:
  - Japanese telop (subtitles/captions)
  - BGM (background music)
  - Before/After image overlay
  - Vertical crop (9:16 for TikTok/Reels/Shorts)
  - Intro hook text animation
  - CTA end card

Requires: FFmpeg installed on Mac (brew install ffmpeg)
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path

# ---- FFmpeg Helpers ----

def run_ffmpeg(cmd, timeout=120):
    """Run FFmpeg command"""
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-500:]}")
    return result

def get_video_duration(path):
    """Get video duration in seconds"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])

# ---- Core Processing Functions ----

def crop_vertical(input_path, output_path, width=1080, height=1920):
    """Crop video to 9:16 vertical format"""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        "-c:a", "copy",
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def add_telop(input_path, output_path, telop_lines, font_path=None):
    """
    Add Japanese telop (captions) to video.

    telop_lines: [
        {"text": "テキスト", "start": 0.0, "end": 3.0, "position": "bottom"},
        {"text": "テキスト2", "start": 3.0, "end": 6.0, "position": "center"},
    ]
    """
    font = font_path or "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
    if not os.path.exists(font):
        font = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

    filter_parts = []
    for i, line in enumerate(telop_lines):
        text = line["text"].replace("'", "\\'").replace(":", "\\:")
        start = line["start"]
        end = line["end"]
        pos = line.get("position", "bottom")

        if pos == "center":
            y_pos = "(h-text_h)/2"
        elif pos == "top":
            y_pos = "h*0.12"
        else:  # bottom
            y_pos = "h*0.82"

        # White text with black outline (standard telop style)
        filter_parts.append(
            f"drawtext=text='{text}'"
            f":fontfile='{font}'"
            f":fontsize=42"
            f":fontcolor=white"
            f":borderw=3"
            f":bordercolor=black"
            f":x=(w-text_w)/2"
            f":y={y_pos}"
            f":enable='between(t,{start},{end})'"
        )

    if not filter_parts:
        # No telops, just copy
        subprocess.run(["cp", input_path, output_path])
        return output_path

    vf = ",".join(filter_parts)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def add_hook_text(input_path, output_path, hook_text, duration=2.0):
    """Add large hook text at the beginning of video"""
    font = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
    if not os.path.exists(font):
        font = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

    text = hook_text.replace("'", "\\'").replace(":", "\\:")

    vf = (
        f"drawtext=text='{text}'"
        f":fontfile='{font}'"
        f":fontsize=64"
        f":fontcolor=white"
        f":borderw=4"
        f":bordercolor=black"
        f":x=(w-text_w)/2"
        f":y=(h-text_h)/2"
        f":enable='between(t,0,{duration})'"
        f":alpha='if(lt(t,0.3),t/0.3,if(gt(t,{duration-0.3}),({duration}-t)/0.3,1))'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def add_bgm(input_path, output_path, bgm_path, volume=0.15):
    """Mix background music with video audio"""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", bgm_path,
        "-filter_complex",
        f"[1:a]volume={volume},aloop=loop=-1:size=2e+09[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]",
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy",
        "-shortest",
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def overlay_image(input_path, output_path, image_path, start, end,
                  x="(W-w)/2", y="(H-h)/2", scale_w=800):
    """Overlay an image (Before/After) on video for specified duration"""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", image_path,
        "-filter_complex",
        f"[1:v]scale={scale_w}:-1[img];"
        f"[0:v][img]overlay={x}:{y}:enable='between(t,{start},{end})'",
        "-c:a", "copy",
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

def add_cta_endcard(input_path, output_path, cta_text="プロフのリンクから",
                    bg_color="FF2D55", duration=3.0):
    """Add CTA end card to video"""
    font = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
    if not os.path.exists(font):
        font = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

    text = cta_text.replace("'", "\\'").replace(":", "\\:")
    vid_duration = get_video_duration(input_path)

    vf = (
        f"drawbox=x=0:y=0:w=iw:h=ih:color=#{bg_color}@0.85:t=fill"
        f":enable='gte(t,{vid_duration})',"
        f"drawtext=text='{text}'"
        f":fontfile='{font}'"
        f":fontsize=56"
        f":fontcolor=white"
        f":x=(w-text_w)/2"
        f":y=(h-text_h)/2"
        f":enable='gte(t,{vid_duration})'"
    )

    # Extend video by adding freeze frame + CTA
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"tpad=stop_mode=clone:stop_duration={duration},{vf}",
        "-c:a", "aac",
        output_path
    ]
    run_ffmpeg(cmd)
    return output_path

# ---- Full Pipeline ----

def process_video(
    raw_video_path,
    output_path,
    script_data,
    before_image=None,
    after_image=None,
    bgm_path=None,
):
    """
    Full post-processing pipeline for a single video.

    Args:
        raw_video_path: Path to MuseTalk/SadTalker output
        output_path: Final output path
        script_data: Dict with keys: hook, text, telop, character
        before_image: Optional Before image path
        after_image: Optional After image path
        bgm_path: Optional BGM audio path
    """
    temp_dir = tempfile.mkdtemp(prefix="ugc_")
    step = 0

    def next_temp():
        nonlocal step
        step += 1
        return os.path.join(temp_dir, f"step{step}.mp4")

    current = raw_video_path
    duration = get_video_duration(current)

    # Step 1: Crop to vertical 9:16
    print(f"  [1] Cropping to 9:16...")
    out = next_temp()
    crop_vertical(current, out)
    current = out

    # Step 2: Add hook text at beginning
    hook = script_data.get("hook", "")
    if hook:
        print(f"  [2] Adding hook: {hook[:20]}...")
        out = next_temp()
        add_hook_text(current, out, hook, duration=2.0)
        current = out

    # Step 3: Add Before/After images
    if before_image and os.path.exists(before_image):
        print(f"  [3] Overlaying Before image...")
        out = next_temp()
        overlay_image(current, out, before_image,
                      start=3.0, end=6.0, y="H*0.15", scale_w=600)
        current = out

    if after_image and os.path.exists(after_image):
        print(f"  [3b] Overlaying After image...")
        out = next_temp()
        overlay_image(current, out, after_image,
                      start=6.5, end=10.0, y="H*0.15", scale_w=600)
        current = out

    # Step 4: Add telops
    telop_str = script_data.get("telop", "")
    if telop_str:
        telop_parts = [t.strip() for t in telop_str.split("/") if t.strip()]
        telop_lines = []
        segment_duration = max(duration / max(len(telop_parts), 1), 3.0)
        for i, part in enumerate(telop_parts):
            telop_lines.append({
                "text": part,
                "start": i * segment_duration,
                "end": (i + 1) * segment_duration,
                "position": "bottom",
            })

        if telop_lines:
            print(f"  [4] Adding {len(telop_lines)} telops...")
            out = next_temp()
            add_telop(current, out, telop_lines)
            current = out

    # Step 5: Add BGM
    if bgm_path and os.path.exists(bgm_path):
        print(f"  [5] Adding BGM...")
        out = next_temp()
        add_bgm(current, out, bgm_path, volume=0.12)
        current = out

    # Step 6: Add CTA end card
    print(f"  [6] Adding CTA end card...")
    out = next_temp()
    add_cta_endcard(current, out, cta_text="プロフのリンクから", duration=2.5)
    current = out

    # Final: Copy to output
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", current, output_path])

    # Cleanup temp
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"  Done: {output_path}")
    return output_path

def batch_process(raw_videos_dir, output_dir, scripts_json_path,
                  before_image=None, after_image=None, bgm_path=None):
    """
    Process all raw videos in a directory.

    Args:
        raw_videos_dir: Directory containing raw MuseTalk output MP4s
        output_dir: Directory to save final videos
        scripts_json_path: Path to scripts JSON (from generate.py)
        before_image: Optional Before image
        after_image: Optional After image
        bgm_path: Optional BGM file
    """
    with open(scripts_json_path, "r", encoding="utf-8") as f:
        scripts = json.load(f)

    raw_files = sorted(Path(raw_videos_dir).glob("*.mp4"))
    print(f"\nBatch processing {len(raw_files)} videos...")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for i, raw_file in enumerate(raw_files):
        script_data = scripts[i] if i < len(scripts) else {"hook": "", "text": "", "telop": ""}
        output_path = os.path.join(output_dir, f"final_{i:04d}_{script_data.get('character', 'unknown')}.mp4")

        print(f"\n[{i+1}/{len(raw_files)}] Processing {raw_file.name}...")
        try:
            process_video(
                str(raw_file), output_path, script_data,
                before_image=before_image,
                after_image=after_image,
                bgm_path=bgm_path,
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    print(f"\nBatch complete! Output: {output_dir}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python postprocess.py <raw_video> <output> [--hook 'テキスト'] [--bgm bgm.mp3]")
        print("Batch: python postprocess.py --batch <raw_dir> <output_dir> <scripts.json>")
        sys.exit(1)

    if sys.argv[1] == "--batch":
        batch_process(sys.argv[2], sys.argv[3], sys.argv[4],
                      before_image=os.environ.get("BEFORE_IMAGE"),
                      after_image=os.environ.get("AFTER_IMAGE"),
                      bgm_path=os.environ.get("BGM_PATH"))
    else:
        process_video(
            sys.argv[1], sys.argv[2],
            {"hook": "120万→35万", "telop": "矯正力1.5倍 / 100枚のマウスピース / プロフから"},
        )
