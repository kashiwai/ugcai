"""
UGC Engine - Model Download Script
=====================================
RunPod Network Volume (/runpod-volume/models) にモデルを保存。
初回起動時のみダウンロード、2回目以降はキャッシュを使用。

手動実行: python download_models.py
"""
import os
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/runpod-volume/models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MUSETALK_DIR = Path("/app/MuseTalk")

def download_if_missing(dest: Path, download_fn):
    """ファイルが存在しない場合のみダウンロード"""
    if dest.exists() and any(dest.iterdir()):
        print(f"  ✓ Already exists: {dest}")
        return
    print(f"  ↓ Downloading to: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    download_fn(dest)

def setup_musetalk_models():
    """MuseTalk v1.5 モデルをダウンロード & シンボリックリンク"""
    models_base = MODEL_DIR / "musetalk_models"
    
    print("[1/5] MuseTalk v1.5 weights...")
    download_if_missing(models_base / "musetalkV15", lambda d:
        snapshot_download(repo_id="TMElyralab/MuseTalk", local_dir=str(d))
    )

    print("[2/5] SD VAE (sd-vae-ft-mse)...")
    download_if_missing(models_base / "sd-vae", lambda d:
        snapshot_download(repo_id="stabilityai/sd-vae-ft-mse", local_dir=str(d))
    )

    print("[3/5] Whisper tiny...")
    download_if_missing(models_base / "whisper", lambda d:
        snapshot_download(repo_id="openai/whisper-tiny", local_dir=str(d))
    )

    print("[4/5] DWPose...")
    download_if_missing(models_base / "dwpose", lambda d:
        snapshot_download(repo_id="yzd-v/DWPose", local_dir=str(d))
    )

    # MuseTalkの models/ ディレクトリにシンボリックリンクを作成
    musetalk_models = MUSETALK_DIR / "models"
    musetalk_models.mkdir(exist_ok=True)
    
    for name in ["musetalkV15", "sd-vae", "whisper", "dwpose"]:
        src = models_base / name
        dst = musetalk_models / name
        if not dst.exists() and src.exists():
            dst.symlink_to(src)
            print(f"  Linked: {dst} -> {src}")

def setup_wav2lip_models():
    """Wav2Lip モデルをダウンロード"""
    print("[5/5] Wav2Lip GAN weights...")
    dst = MODEL_DIR / "wav2lip" / "wav2lip_gan.pth"
    
    if dst.exists():
        print(f"  ✓ Already exists: {dst}")
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            hf_hub_download(
                repo_id="numz/wav2lip_studio",
                filename="Wav2Lip/wav2lip_gan.pth",
                local_dir=str(dst.parent),
            )
            # hf_hub_download saves under repo structure; move to expected path
            dl_path = dst.parent / "Wav2Lip" / "wav2lip_gan.pth"
            if dl_path.exists():
                shutil.move(str(dl_path), str(dst))
            print(f"  ✓ Downloaded: {dst}")
        except Exception as e:
            print(f"  ⚠ Wav2Lip download failed: {e}")

    # Wav2Lip checkpoints にシンボリックリンク
    wav2lip_chk = Path("/app/Wav2Lip/checkpoints")
    wav2lip_chk.mkdir(exist_ok=True)
    link = wav2lip_chk / "wav2lip_gan.pth"
    if not link.exists() and dst.exists():
        link.symlink_to(dst)

def ensure_models():
    """全モデルが揃っているか確認、なければダウンロード"""
    print(f"\n=== Model Setup (MODEL_DIR={MODEL_DIR}) ===")
    setup_musetalk_models()
    setup_wav2lip_models()
    print("=== Model setup complete ===\n")

if __name__ == "__main__":
    ensure_models()
