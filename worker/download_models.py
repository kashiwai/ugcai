"""
UGC Engine - Model Download Script
=====================================
MuseTalk v1.5 に必要な全モデルを /app/MuseTalk/models/ にダウンロード。
初回ジョブ時のみ実行。2回目以降は既存ファイルをスキップ。

MuseTalkが期待する構造:
  /app/MuseTalk/models/musetalkV15/musetalk.json  (config)
  /app/MuseTalk/models/musetalkV15/unet.pth       (3.2GB)
  /app/MuseTalk/models/sd-vae-ft-mse/             (~334MB)
  /app/MuseTalk/models/whisper/tiny.pt            (~75MB)
  /app/MuseTalk/models/dwpose/                    (pose estimator)

手動実行: python download_models.py
"""
import os
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

MUSETALK_DIR = Path("/app/MuseTalk")
MUSETALK_MODELS = MUSETALK_DIR / "models"   # MuseTalkが期待するベースパス


def _is_nonempty_dir(path: Path) -> bool:
    """ディレクトリが存在して空でないか確認"""
    return path.is_dir() and any(path.iterdir())


def _file_exists(path: Path) -> bool:
    """ファイルが存在してサイズ > 0 か確認"""
    return path.is_file() and path.stat().st_size > 0


def setup_musetalk_v15():
    """
    TMElyralab/MuseTalk リポジトリを /app/MuseTalk/models/ にダウンロード。
    リポジトリ構造:
      musetalkV15/musetalk.json
      musetalkV15/unet.pth (3.2GB)
    """
    MUSETALK_MODELS.mkdir(parents=True, exist_ok=True)
    marker = MUSETALK_MODELS / "musetalkV15" / "musetalk.json"

    if _file_exists(marker):
        print(f"  ✓ MuseTalk V1.5 models: {marker.parent}")
        return

    print(f"  ↓ Downloading TMElyralab/MuseTalk → {MUSETALK_MODELS}")
    print(f"    (musetalkV15/unet.pth is ~3.2GB, 予想時間: 2-10分)")
    snapshot_download(
        repo_id="TMElyralab/MuseTalk",
        local_dir=str(MUSETALK_MODELS),
        ignore_patterns=["*.git*", ".gitattributes"],
    )

    if not _file_exists(marker):
        raise RuntimeError(
            f"MuseTalkV15のダウンロード失敗: {marker} が見つかりません。"
            "ディスク容量(50GB必要)とネットワークを確認してください。"
        )
    print(f"  ✓ MuseTalk V1.5 models ready")


def setup_sd_vae():
    """
    Stable Diffusion VAE を /app/MuseTalk/models/sd-vae/ にDL。
    MuseTalkが内部で vae.encode/decode に使用 (models/sd-vae を参照)。
    """
    dst = MUSETALK_MODELS / "sd-vae"

    if _is_nonempty_dir(dst):
        print(f"  ✓ SD VAE: {dst}")
        return

    print(f"  ↓ Downloading stabilityai/sd-vae-ft-mse → {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="stabilityai/sd-vae-ft-mse",
        local_dir=str(dst),
        ignore_patterns=["*.git*"],
    )
    print(f"  ✓ SD VAE ready")


def setup_whisper():
    """
    Whisper tiny モデルを /app/MuseTalk/models/whisper/ にDL。
    MuseTalkが音声特徴量抽出に使用。
    """
    dst = MUSETALK_MODELS / "whisper"
    marker = dst / "config.json"

    if _file_exists(marker):
        print(f"  ✓ Whisper tiny: {dst}")
        return

    print(f"  ↓ Downloading openai/whisper-tiny → {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="openai/whisper-tiny",
        local_dir=str(dst),
        ignore_patterns=["*.git*"],
    )
    print(f"  ✓ Whisper tiny ready")


def setup_dwpose():
    """
    DWPose (専用ファイル) を /app/MuseTalk/models/dwpose/ にDL。
    MuseTalkが顔検出・ランドマーク検出に使用。
    """
    dst = MUSETALK_MODELS / "dwpose"
    marker = dst / "dw-ll_ucoco_384.pth"

    if _file_exists(marker):
        print(f"  ✓ DWPose: {dst}")
        return

    print(f"  ↓ Downloading yzd-v/DWPose dw-ll_ucoco_384.pth → {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    try:
        hf_hub_download(
            repo_id="yzd-v/DWPose",
            filename="dw-ll_ucoco_384.pth",
            local_dir=str(dst),
        )
        print(f"  ✓ DWPose ready")
    except Exception as e:
        print(f"  ⚠ DWPose download failed: {e}")


def setup_face_parse_bisent():
    """
    face-parse-bisent (顔パース) モデルをDL。
    MuseTalkが顔領域アウトペイント/インペイントのマスト、フェイスブレンドに使用。
    """
    dst = MUSETALK_MODELS / "face-parse-bisent"
    marker79 = dst / "79999_iter.pth"
    marker_res = dst / "resnet18-5c106cde.pth"

    if _file_exists(marker79) and _file_exists(marker_res):
        print(f"  ✓ face-parse-bisent: {dst}")
        return

    print(f"  ↓ Downloading face-parse-bisent → {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    import urllib.request
    try:
        if not _file_exists(marker_res):
            print("    Downloading resnet18-5c106cde.pth...")
            urllib.request.urlretrieve(
                "https://download.pytorch.org/models/resnet18-5c106cde.pth",
                str(marker_res)
            )
        if not _file_exists(marker79):
            print("    Downloading 79999_iter.pth via gdown...")
            try:
                import gdown
                gdown.download(
                    id="154JgKpzCPW82qINcVieuPH3fZ2e0P812",
                    output=str(marker79),
                    quiet=False,
                )
            except Exception as e:
                print(f"  ⚠ gdown failed: {e} - skip face-parse-bisent")
        print(f"  ✓ face-parse-bisent ready")
    except Exception as e:
        print(f"  ⚠ face-parse-bisent download failed (non-fatal): {e}")


def setup_wav2lip():
    """Wav2Lip GAN weights を /app/Wav2Lip/checkpoints/wav2lip_gan.pth にDL"""
    chk_dir = Path("/app/Wav2Lip/checkpoints")
    chk_dir.mkdir(parents=True, exist_ok=True)
    dst = chk_dir / "wav2lip_gan.pth"

    if _file_exists(dst):
        print(f"  ✓ Wav2Lip: {dst}")
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
        print(f"  ✓ Wav2Lip ready")
    except Exception as e:
        print(f"  ⚠ Wav2Lip download failed (optional): {e}")


def setup_sadtalker():
    """
    SadTalkerとGFPGANの推論に必要な重みをダウンロード。
    """
    st_dir = Path("/app/SadTalker")
    st_chk = st_dir / "checkpoints"
    st_gfp = st_dir / "gfpgan" / "weights"

    marker_st = st_chk / "mapping_00109-model.pth.tar"
    marker_gfp = st_gfp / "GFPGANv1.4.pth"

    if _file_exists(marker_st) and _file_exists(marker_gfp):
        print(f"  ✓ SadTalker models: {st_dir}")
        return

    print("  ↓ Downloading SadTalker & GFPGAN weights...")
    st_chk.mkdir(parents=True, exist_ok=True)
    st_gfp.mkdir(parents=True, exist_ok=True)

    import urllib.request
    try:
        urls = {
            "mapping_00109-model.pth.tar": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00109-model.pth.tar",
            "mapping_00229-model.pth.tar": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00229-model.pth.tar",
            "SadTalker_V0.0.2_256.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors",
            "SadTalker_V0.0.2_512.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors",
        }
        for filename, url in urls.items():
            if not _file_exists(st_chk / filename):
                print(f"    Downloading {filename}...")
                urllib.request.urlretrieve(url, str(st_chk / filename))
        
        gfp_urls = {
            "alignment_WFLW_4HG.pth": "https://github.com/xinntao/facexlib/releases/download/v0.1.0/alignment_WFLW_4HG.pth",
            "detection_Resnet50_Final.pth": "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth",
            "GFPGANv1.4.pth": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
            "parsing_parsenet.pth": "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth",
        }
        for filename, url in gfp_urls.items():
            if not _file_exists(st_gfp / filename):
                print(f"    Downloading {filename}...")
                urllib.request.urlretrieve(url, str(st_gfp / filename))
                
        print("  ✓ SadTalker & GFPGAN ready")
    except Exception as e:
        print(f"  ⚠ SadTalker models download failed (optional): {e}")


def ensure_models():
    """全モデルの準備 (初回ジョブ時またはファイル未存在時に呼び出す)"""
    print(f"\n=== Model Setup ===")
    print(f"  TARGET: {MUSETALK_MODELS}")

    # MuseTalk V1.5 (必須 - 3.2GB)
    setup_musetalk_v15()

    # SD VAE (必須 - ~334MB)
    setup_sd_vae()

    # Whisper (必須 - ~75MB)
    setup_whisper()

    # DWPose (必須 - 顔検出用)
    setup_dwpose()

    # face-parse-bisent (顔パース用)
    setup_face_parse_bisent()

    # Wav2Lip (musetalk以外のモデル用)
    setup_wav2lip()

    # SadTalker (musetalk以外のモデル用)
    setup_sadtalker()

    print("=== Model setup complete ===\n")


if __name__ == "__main__":
    ensure_models()
