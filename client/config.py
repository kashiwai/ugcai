"""
UGC Engine - Configuration
==========================
APIキーの設定方法:
  1. このファイルと同じ場所に .env ファイルを作成
  2. .env に各キーを記述 (例: ANTHROPIC_API_KEY=sk-ant-...)
  3. または環境変数として export する
"""
import os
from pathlib import Path

# dotenv サポート (.env ファイルがあれば読み込む)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
        print(f"[config] Loaded .env from {_env_path}")
    else:
        # 親ディレクトリの .env も試す
        _root_env = Path(__file__).parent.parent / ".env"
        if _root_env.exists():
            load_dotenv(_root_env)
            print(f"[config] Loaded .env from {_root_env}")
except ImportError:
    pass  # python-dotenv未インストールの場合は環境変数を直接使用

# ---- Railway API Server ----
RAILWAY_API_URL = os.environ.get("RAILWAY_API_URL", "https://your-app.up.railway.app")
API_SECRET = os.environ.get("API_SECRET", "change-me-in-production")

# ---- Claude API (for script generation) ----
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ---- VOICEVOX (local) ----
VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://localhost:50021")

# ---- Cloudflare R2 ----
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "ugc-engine")
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

# ---- Characters ----
# face_image: assets/faces/ 以下のファイルパス（プロジェクトルートからの相対パス）
_ASSETS = Path(__file__).parent.parent / "assets" / "faces"

CHARACTERS = {
    "miku": {
        "name": "みく (22歳OL)",
        "face_image": str(_ASSETS / "miku.jpg"),
        "voicevox_speaker_id": 2,   # ずんだもん
        "tone": "カジュアル共感",
        "persona_prompt": "あなたは22歳のOLのみくです。接客業で歯並びがコンプレックスでしたが、35万円のマウスピース矯正を始めて人生が変わりました。カジュアルで共感を誘うトーンで話してください。",
    },
    "kenta": {
        "name": "けんた (27歳営業)",
        "face_image": str(_ASSETS / "kenta.jpg"),
        "voicevox_speaker_id": 3,
        "tone": "ロジカル比較",
        "persona_prompt": "あなたは27歳の営業マンのけんたです。費用対効果を数字で語ります。120万vs35万の矯正コストを論理的に比較するスタイルです。",
    },
    "ayaka": {
        "name": "あやか (19歳学生)",
        "face_image": str(_ASSETS / "ayaka.jpg"),
        "voicevox_speaker_id": 0,
        "tone": "Z世代",
        "persona_prompt": "あなたは19歳の大学生あやかです。バイト代で矯正を始めました。Z世代のトレンド感のある話し方で、テンション高めに話してください。",
    },
    "dr_tanaka": {
        "name": "Dr.田中 (歯科医師)",
        "face_image": str(_ASSETS / "dr_tanaka.jpg"),
        "voicevox_speaker_id": 13,
        "tone": "専門家",
        "persona_prompt": "あなたは歯科医師のDr.田中です。マウスピース矯正の技術的な優位性を医学的根拠に基づいて解説します。専門的だが分かりやすく。",
    },
    "mariko": {
        "name": "まりこ (32歳ママ)",
        "face_image": str(_ASSETS / "mariko.jpg"),
        "voicevox_speaker_id": 1,
        "tone": "節約主婦",
        "persona_prompt": "あなたは32歳の2児のママまりこです。家計を考えつつ自分への投資として35万の矯正を始めました。穏やかで共感を誘う話し方。",
    },
    "yuki": {
        "name": "ゆうき (25歳フリー)",
        "face_image": str(_ASSETS / "yuki.jpg"),
        "voicevox_speaker_id": 46,
        "tone": "キャリア",
        "persona_prompt": "あなたは25歳のフリーランスゆうきです。Zoom映えのために矯正を始めました。自己投資としてのコスパの良さを語ります。",
    },
    "sakura": {
        "name": "さくら (解説役)",
        "face_image": str(_ASSETS / "sakura.jpg"),
        "voicevox_speaker_id": 8,
        "tone": "情報整理",
        "persona_prompt": "あなたは矯正情報をまとめる解説役のさくらです。比較表やQ&A形式で、分かりやすく整理して情報を伝えます。",
    },
    "reviewer": {
        "name": "辛口レビュアー",
        "face_image": str(_ASSETS / "reviewer.jpg"),
        "voicevox_speaker_id": 11,
        "tone": "懐疑→納得",
        "persona_prompt": "あなたは辛口の矯正レビュアーです。最初は「35万は怪しい」と疑っていましたが、調べた結果ガチだと分かりました。淡々とした口調で事実を語ります。",
    },
}

# ---- Content Types ----
CONTENT_TYPES = [
    "価格衝撃",
    "体験語り",
    "専門家解説",
    "辛口調査",
    "バズネタ",
    "Before/After",
    "比較",
    "Q&A",
]

# ---- Generation Models ----
MODELS = ["musetalk", "sadtalker", "wav2lip"]
DEFAULT_MODEL = "musetalk"
