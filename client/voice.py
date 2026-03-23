"""
UGC Engine - Voice Generator
============================
Fish Audio R2 (推奨) または VOICEVOX をサポート。

設定:
  .env に FISH_AUDIO_API_KEY を設定すると Fish Audio を使用
  未設定の場合は VOICEVOX にフォールバック

Fish Audio R2:
  - クラウドAPI、Macローカル起動不要
  - 日本語高品質
  - https://fish.audio
"""

import os
import requests
from pathlib import Path
from config import VOICEVOX_URL

FISH_AUDIO_API_KEY = os.environ.get("FISH_AUDIO_API_KEY", "")
FISH_AUDIO_API_URL = "https://api.fish.audio/v1/tts"

# Fish Audio R2 - 日本語向けデフォルト声モデル
# キャラクターごとに異なるモデルを指定できる
# モデルID一覧: https://fish.audio/zh-CN/discover/
FISH_AUDIO_DEFAULT_MODEL = "speech-1.6"  # Fish Audio R2 相当

# キャラクター別 Fish Audio 声の参照ID (空の場合はデフォルト音声)
FISH_AUDIO_VOICE_MAP = {
    # "character_name": "reference_id"  ← fish.audio でクローンした声のID
    # 空のままでもデフォルト日本語音声で動作する
}


def generate_voice_fish_audio(
    text: str,
    voice_id: str = "",
    output_path: str = "output.wav",
    speed: float = 1.0,
    character: str = "",
) -> str:
    """
    Fish Audio R2 APIで音声生成。

    Args:
        text: 読み上げテキスト
        voice_id: Fish Audio の参照音声ID（空でベース音声）
        output_path: 保存先WAVパス
        speed: 速度 (0.5-2.0)
        character: キャラクター名（FISH_AUDIO_VOICE_MAPを参照）
    """
    # キャラクター別の声IDを取得
    ref_id = voice_id or FISH_AUDIO_VOICE_MAP.get(character, "")

    payload = {
        "text": text,
        "format": "wav",
        "mp3_bitrate": 128,
        "opus_bitrate": -1000,
        "streaming": False,
        "latency": "normal",
    }

    # モデル指定
    if ref_id:
        payload["reference_id"] = ref_id
    else:
        # デフォルト: Fish Audio の標準日本語女声
        payload["model_id"] = "fish-speech-1-6"

    # 速度調整
    if speed != 1.0:
        payload["prosody"] = {"speed": speed}

    headers = {
        "Authorization": f"Bearer {FISH_AUDIO_API_KEY}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        FISH_AUDIO_API_URL,
        json=payload,
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(resp.content)

    return output_path


def generate_voice_voicevox(
    text: str,
    speaker_id: int = 2,
    output_path: str = "output.wav",
    speed: float = 1.0,
    pitch: float = 0.0,
) -> str:
    """VOICEVOX Engine で音声生成 (ローカル起動が必要)"""
    query_resp = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": speaker_id},
        timeout=30,
    )
    query_resp.raise_for_status()
    query = query_resp.json()

    query["speedScale"] = speed
    query["pitchScale"] = pitch
    query["volumeScale"] = 1.0
    query["intonationScale"] = 1.2
    query["prePhonemeLength"] = 0.1
    query["postPhonemeLength"] = 0.3

    synth_resp = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": speaker_id},
        json=query,
        timeout=60,
    )
    synth_resp.raise_for_status()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(synth_resp.content)

    return output_path


def generate_voice(
    text: str,
    speaker_id: int = 2,
    output_path: str = "output.wav",
    speed: float = 1.0,
    pitch: float = 0.0,
    character: str = "",
    fish_voice_id: str = "",
) -> str:
    """
    音声生成 (Fish Audio R2 優先 / VOICEVOX フォールバック)

    Fish Audio APIキーが設定されていれば Fish Audio R2 を使用。
    未設定の場合は VOICEVOX にフォールバック。
    """
    if FISH_AUDIO_API_KEY:
        return generate_voice_fish_audio(
            text=text,
            voice_id=fish_voice_id,
            output_path=output_path,
            speed=speed,
            character=character,
        )
    else:
        return generate_voice_voicevox(
            text=text,
            speaker_id=speaker_id,
            output_path=output_path,
            speed=speed,
            pitch=pitch,
        )


def generate_voice_batch(items, output_dir="output/voices"):
    """
    複数音声を一括生成。

    Args:
        items: List of {
            "text": str,
            "speaker_id": int,        # VOICEVOX用
            "fish_voice_id": str,     # Fish Audio用（省略可）
            "character": str,         # キャラクター名
            "filename": str,
            "speed": float (optional)
        }
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []

    engine = "Fish Audio R2" if FISH_AUDIO_API_KEY else "VOICEVOX"
    print(f"  Voice engine: {engine}")

    for item in items:
        output_path = f"{output_dir}/{item['filename']}"
        try:
            generate_voice(
                text=item["text"],
                speaker_id=item.get("speaker_id", 2),
                output_path=output_path,
                speed=item.get("speed", 1.0),
                character=item.get("character", ""),
                fish_voice_id=item.get("fish_voice_id", ""),
            )
            results.append({"path": output_path, "success": True})
        except Exception as e:
            print(f"  Voice error [{item.get('filename', '?')}]: {e}")
            results.append({"path": output_path, "success": False, "error": str(e)})

    return results


if __name__ == "__main__":
    engine = "Fish Audio R2" if FISH_AUDIO_API_KEY else "VOICEVOX"
    print(f"Voice engine: {engine}")

    path = generate_voice(
        text="120万円の矯正が35万円でできるって知ってた？マジでやばいよ。",
        output_path="/tmp/test_voice.wav",
        character="ayaka",
    )
    print(f"Saved: {path}")
