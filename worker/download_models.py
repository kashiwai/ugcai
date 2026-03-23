"""
UGC Engine - Model Download Script
=====================================
MuseTalkモデルを /app/MuseTalk/models/ に直接ダウンロード。
Network Volumeがある場合は MODEL_DIR にキャッシュ → シンボリックリンクで高速化。

手動実行: python download_models.py
"""
import os
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

MUSETALK_DIR = Path("/app/MuseTalk")
MUSETALK_MODELS = MUSETALK_DIR / "models"   # MuseTalkが期待するパス

# Network Volume が /runpod-volume にある場合はキャッシュとして使う
VOLUME_PATH = Path("/runpod-volume")
HAS_VOLUME = VOLUME_PATH.exists() and os.environ.get("MODEL_DIR", "")


def _is_ready(marker: Path) -> bool:
    return marker.exists() and marker.stat().st_size > 0


def setup_musetalk_models():
    """
    TMElyralab/MuseTalk HuggingFaceリポジトリを /app/MuseTalk/models/ にDL。
    リポジトリのルートに musetalkV15/, sd-vae-ft-mse/, whisper/, dwpose/ がある。
    """
    MUSETALK_MODELS.mkdir(parents=True, exist_ok=True)
    marker = MUSETALK_MODELS / "musetalkV15" / "musetalk.json"

    if _is_ready(marker):
        print(f"  ✓ MuseTalk models already at {MUSETALK_MODELS}")
        return

    if HAS_VOLUME:
        # Network Volume にキャッシュ → /app/MuseTalk/models へシンボリックリンク
        cache = VOLUME_PATH / "musetalk_repo"
        cache_marker = cache / "musetalkV15" / "musetalk.json"

        if not _is_ready(cache_marker):
            print(f"  ↓ Downloading TMElyralab/MuseTalk → {cache}")
            cache.mkdir(parents=True, exist_ok=True)
            snapshot_download(
                repo_id="TMElyralab/MuseTalk",
                local_dir=str(cache),
            )

        # シンボリックリンクを作成
        for name in ["musetalkV15", "sd-vae-ft-mse", "dwpose", "whisper"]:
            src = cache / name
            dst = MUSETALK_MODELS / name
            if src.exists() and not dst.exists():
                dst.symlink_to(src)
                print(f"  Linked: {dst} → {src}")
    else:
        # Network Volumeなし: /app/MuseTalk/models/ に直接ダウンロード
        print(f"  ↓ Downloading TMElyralab/MuseTalk → {MUSETALK_MODELS}")
        snapshot_download(
            repo_id="TMElyralab/MuseTalk",
            local_dir=str(MUSETALK_MODELS),
        )

    if not _is_ready(marker):
        raise RuntimeError(
            f"MuseTalk model download failed: {marker} not found after download. "
            "Check disk space and network connectivity."
        )
    print(f"  ✓ MuseTalk models ready at {MUSETALK_MODELS}")


def setup_wav2lip_models():
    """Wav2Lip モデルをダウンロード (/app/Wav2Lip/checkpoints/)"""
    chk_dir = Path("/app/Wav2Lip/checkpoints")
    chk_dir.mkdir(parents=True, exist_ok=True)
    dst = chk_dir / "wav2lip_gan.pth"

    if dst.exists() and dst.stat().st_size > 0:
        print(f"  ✓ Wav2Lip model: {dst}")
        return

    print("  ↓ Downloading Wav2Lip GAN weights...")
    try:
        hf_hub_download(
            repo_id="numz/wav2lip_studio",
            filename="Wav2Lip/wav2lip_gan.pth",
            local_dir=str(chk_dir),
        )
        dl_path = chk_dir / "Wav2Lip" / "wav2lip_gan.pth"
        if dl_path.exists():
            shutil.move(str(dl_path), str(dst))
        print(f"  ✓ Wav2Lip model: {dst}")
    except Exception as e:
        print(f"  ⚠ Wav2Lip download failed (optional): {e}")


def ensure_models():
    """全モデルの準備 (初回ジョブ時に呼び出す)"""
    print(f"\n=== Model Setup ===")
    print(f"  MUSETALK_MODELS: {MUSETALK_MODELS}")
    print(f"  Network Volume: {'Yes' if HAS_VOLUME else 'No'}")

    setup_musetalk_models()
    setup_wav2lip_models()

    print("=== Model setup complete ===\n")


if __name__ == "__main__":
    ensure_models()
