"""
UGC Engine - Voice Generator (VOICEVOX)
=========================================
Generates Japanese voice audio using local VOICEVOX Engine.

Setup:
  1. Download VOICEVOX from https://voicevox.hiroyuki.cloud/
  2. Launch VOICEVOX Engine (it runs on localhost:50021)
  3. This script calls the REST API to generate WAV files
"""

import requests
import json
from pathlib import Path
from config import VOICEVOX_URL

def get_speakers():
    """List all available VOICEVOX speakers/characters"""
    resp = requests.get(f"{VOICEVOX_URL}/speakers", timeout=10)
    resp.raise_for_status()
    speakers = resp.json()
    result = []
    for speaker in speakers:
        for style in speaker["styles"]:
            result.append({
                "name": speaker["name"],
                "style": style["name"],
                "id": style["id"],
            })
    return result

def generate_voice(text, speaker_id=2, output_path="output.wav", speed=1.0, pitch=0.0):
    """
    Generate voice audio from text using VOICEVOX.

    Args:
        text: Japanese text to speak
        speaker_id: VOICEVOX speaker ID (see get_speakers())
        output_path: Path to save WAV file
        speed: Speech speed (0.5-2.0, default 1.0)
        pitch: Pitch adjustment (-0.15 to 0.15, default 0.0)
    """
    # Step 1: Create audio query (phoneme analysis)
    query_resp = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": speaker_id},
        timeout=30,
    )
    query_resp.raise_for_status()
    query = query_resp.json()

    # Adjust parameters
    query["speedScale"] = speed
    query["pitchScale"] = pitch
    query["volumeScale"] = 1.0
    query["intonationScale"] = 1.2  # Slightly more expressive
    query["prePhonemeLength"] = 0.1
    query["postPhonemeLength"] = 0.3  # Small pause at end

    # Step 2: Synthesize audio
    synth_resp = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": speaker_id},
        json=query,
        timeout=60,
    )
    synth_resp.raise_for_status()

    # Save WAV file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(synth_resp.content)

    return output_path

def generate_voice_batch(items, output_dir="output/voices"):
    """
    Generate multiple voice files.

    Args:
        items: List of {"text": str, "speaker_id": int, "filename": str}
        output_dir: Directory to save WAV files
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []

    for item in items:
        output_path = f"{output_dir}/{item['filename']}"
        try:
            generate_voice(
                text=item["text"],
                speaker_id=item.get("speaker_id", 2),
                output_path=output_path,
                speed=item.get("speed", 1.0),
            )
            results.append({"path": output_path, "success": True})
        except Exception as e:
            print(f"  Voice error [{item.get('filename', '?')}]: {e}")
            results.append({"path": output_path, "success": False, "error": str(e)})

    return results


if __name__ == "__main__":
    # Test: List speakers
    print("Available VOICEVOX speakers:")
    try:
        for s in get_speakers()[:20]:
            print(f"  ID {s['id']:3d}: {s['name']} ({s['style']})")
    except Exception as e:
        print(f"  Error: {e}")
        print("  Make sure VOICEVOX Engine is running on localhost:50021")

    # Test: Generate sample
    try:
        path = generate_voice(
            "120万円の矯正が35万円でできるって知ってた？マジでやばいよ",
            speaker_id=2,
            output_path="test_voice.wav",
        )
        print(f"\nSample saved: {path}")
    except Exception as e:
        print(f"\nVoice test failed: {e}")
