# UGC Video Generation Engine
## Mac + Railway + RunPod GPU + MuseTalk

AIアバター動画を月2,000本、約4,000円で生成するエンジン。

---

## アーキテクチャ

```
Mac (あなたのPC)
  ├─ Claude API → 台本バッチ生成
  ├─ VOICEVOX  → 日本語音声生成 (ローカル/無料)
  └─ Python Client → ジョブ投入/ダウンロード
       │
       ▼
Railway Server (API)
  ├─ Express + BullMQ
  ├─ ジョブキュー管理
  └─ RunPod呼び出し
       │
       ▼
RunPod GPU (Serverless)
  ├─ MuseTalk / SadTalker / Wav2Lip
  ├─ 顔画像+音声 → リップシンク動画
  └─ 結果をR2にアップロード
       │
       ▼
Cloudflare R2 (Storage)
  └─ 入力ファイル / 完成動画を保存
```

---

## セットアップ手順

### Step 1: Mac環境準備 (10分)

```bash
# Python環境
brew install python@3.11
pip install anthropic requests boto3 tqdm

# VOICEVOX Engine (Mac版)をダウンロード
# https://voicevox.hiroyuki.cloud/
# ダウンロード後、アプリを起動 → http://localhost:50021 でAPIが利用可能

# プロジェクトをクローン
cd ~/projects
git clone <your-repo> ugc-engine
cd ugc-engine/client
cp config.py config_local.py  # APIキーを設定
```

### Step 2: Cloudflare R2 設定 (5分)

1. https://dash.cloudflare.com/ にログイン
2. R2 → Create Bucket → 名前: `ugc-engine`
3. R2 → Manage R2 API Tokens → Create API Token
4. `config.py` に Account ID / Access Key / Secret Key を設定

### Step 3: Railway デプロイ (10分)

```bash
# Railway CLIインストール
npm install -g @railway/cli

# ログイン
railway login

# プロジェクト作成+デプロイ
cd server
railway init
railway add --name redis  # Redisプラグイン追加

# 環境変数を設定
railway variables set REDIS_URL=<Railway Redisの接続URL>
railway variables set RUNPOD_API_KEY=<RunPod API Key>
railway variables set RUNPOD_ENDPOINT_ID=<RunPod Endpoint ID>
railway variables set R2_ACCOUNT_ID=<Cloudflare Account ID>
railway variables set R2_ACCESS_KEY=<R2 Access Key>
railway variables set R2_SECRET_KEY=<R2 Secret Key>
railway variables set R2_BUCKET=ugc-engine
railway variables set API_SECRET=<ランダムな秘密鍵>

# デプロイ
railway up
```

### Step 4: RunPod セットアップ (15分)

```bash
# RunPodアカウント作成: https://www.runpod.io/
# $10程度をチャージ

# Dockerイメージをビルド+プッシュ
cd worker
docker build -t your-dockerhub/ugc-worker:latest .
docker push your-dockerhub/ugc-worker:latest

# RunPod Dashboard で:
# 1. Serverless → New Endpoint
# 2. Docker Image: your-dockerhub/ugc-worker:latest
# 3. GPU: RTX 3090 or RTX 4090 (24GB VRAM)
# 4. Max Workers: 5 (並列処理数)
# 5. Idle Timeout: 30s (コスト節約)
# 6. Endpoint IDをメモ → config.pyに設定
```

### Step 5: 顔画像を準備

```bash
# assets/faces/ に8キャラ分の顔画像を配置
# 推奨: 512x512 PNG, 正面顔, 中性的な表情
# 生成方法:
#   - Midjourney: "japanese woman, 22 years old, front face, neutral expression, white background"
#   - FLUX: 同様のプロンプト
#   - HeyGen: 無料プランでアバター画像をスクリーンショット
```

---

## 使い方

### テスト実行 (3本)
```bash
cd client
python generate.py --batch test --model musetalk
```

### 10本生成 (特定キャラ)
```bash
python generate.py --count 10 --character miku --model musetalk
```

### 1日分の全量生成 (70本)
```bash
python generate.py --batch daily --model musetalk
```

### モデル比較テスト
```bash
# 同じ台本で3モデルを比較
python generate.py --count 3 --character miku --model musetalk
python generate.py --count 3 --character miku --model sadtalker
python generate.py --count 3 --character miku --model wav2lip
```

---

## コスト試算

| 項目 | 月額 |
|------|------|
| RunPod GPU (RTX 4090, ~33h) | ~$11 (約1,700円) |
| Railway (Starter) | $5 (約750円) |
| Cloudflare R2 (100GB) | ~$1.4 (約200円) |
| Claude API (台本生成) | ~$5-10 (約750-1,500円) |
| VOICEVOX | 無料 |
| **合計** | **約3,400-4,150円/月** |

→ HeyGen Business ($249/月=37,000円) の **1/10 のコスト**
→ 1本あたり約2円 (HeyGenは185円/本)

---

## ファイル構成

```
ugc-engine/
├── server/           # Railway APIサーバー
│   ├── index.js      # Express + BullMQ + RunPod連携
│   └── package.json
├── worker/           # RunPod GPUワーカー
│   ├── handler.py    # MuseTalk/SadTalker/Wav2Lip実行
│   ├── Dockerfile    # CUDA + PyTorch + モデル
│   └── requirements.txt
├── client/           # Mac制御スクリプト
│   ├── generate.py   # メイン実行スクリプト
│   ├── scripts.py    # Claude APIで台本生成
│   ├── voice.py      # VOICEVOXで音声生成
│   ├── upload.py     # R2アップロード/ダウンロード
│   └── config.py     # 設定ファイル
├── assets/
│   └── faces/        # 8キャラの顔画像
├── output/           # 生成結果
│   ├── scripts/      # 台本JSON
│   ├── voices/       # 音声WAV
│   └── videos/       # 完成MP4
└── README.md
```

---

## トラブルシューティング

### VOICEVOXが起動しない
→ VOICEVOX Engineアプリを先に起動してください。http://localhost:50021/speakers にアクセスして応答があればOK。

### RunPodのジョブが失敗する
→ RunPod Dashboardの Logs タブでエラーを確認。VRAM不足の場合はGPUをアップグレード(RTX 4090推奨)。

### R2にアップロードできない
→ R2 API Tokenの権限を確認。"Object Read & Write" が必要です。

### 動画の口パクがズレる
→ MuseTalkの場合、入力画像の解像度を256x256に調整。SadTalkerに切り替えて比較テスト。
