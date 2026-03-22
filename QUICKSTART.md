# UGC Engine - クイックスタート

## 前提条件
- Mac (Apple Silicon or Intel)
- RunPod API Key: `rpa_S6S7ZBU2WJS2R1Z...` (設定済み)
- Claude API Key: 設定済み

---

## Step 1: 初期セットアップ (5分)

```bash
cd ~/Downloads/ugc-engine\ 2
bash setup.sh
```

---

## Step 2: APIキーを設定 (5分)

`.env` ファイルを編集してください（RunPod・Claudeキーは**設定済み**です）:

```bash
# 設定が必要な項目
R2_ACCOUNT_ID=xxx      # Cloudflare ダッシュボードから
R2_ACCESS_KEY=xxx
R2_SECRET_KEY=xxx
RAILWAY_API_URL=xxx    # Railwayデプロイ後に設定
```

---

## Step 3: 顔画像を準備 (10分)

`assets/faces/` に8キャラの PNG を配置:
- `miku.png`, `kenta.png`, `ayaka.png`, `dr_tanaka.png`
- `mariko.png`, `yuki.png`, `sakura.png`, `reviewer.png`

→ 詳細は `assets/faces/README.txt` 参照

---

## Step 4: Railway デプロイ (10分)

```bash
cd server
npm install
railway login
railway init
railway add --name redis

# 環境変数を一括設定
railway variables set \
  RUNPOD_API_KEY=rpa_S6S7ZBU2WJS2R1ZMPPSP1OT59YY1KD17XI2F77451uavjl \
  RUNPOD_ENDPOINT_ID=<RunPod EndpointID> \
  R2_ACCOUNT_ID=<your-account-id> \
  R2_ACCESS_KEY=<your-key> \
  R2_SECRET_KEY=<your-secret> \
  R2_BUCKET=ugc-engine \
  API_SECRET=ugc-engine-secret-change-me

railway up
# → デプロイ後に表示されるURLを .env の RAILWAY_API_URL に設定
```

---

## Step 5: RunPod Endpoint 作成 (15分)

```bash
# Dockerイメージをビルド・プッシュ
cd worker
docker build -t <your-dockerhub>/ugc-worker:latest .
docker push <your-dockerhub>/ugc-worker:latest
```

RunPod Dashboard:
1. Serverless → New Endpoint
2. Docker Image: `<your-dockerhub>/ugc-worker:latest`
3. GPU: RTX 4090 (24GB VRAM)
4. Max Workers: 5
5. Idle Timeout: 30s
6. **Endpoint ID を `.env` の `RUNPOD_ENDPOINT_ID` に設定**

---

## Step 6: テスト実行

```bash
# VOICEVOX Engine を先に起動 → http://localhost:50021 確認

# dry-run (GPU不使用・台本+音声のみ)
cd client
pip install -r requirements.txt
python pipeline.py --count 2 --dry-run

# 本番テスト (3本)
python generate.py --batch test --model musetalk
```

---

## 監視ダッシュボード

`dashboard/index.html` をブラウザで開いてください:
- Railway API URL と API Secret を入力
- 5秒ごとにキュー状況・処理速度を表示

---

## 大量生成 (本番)

```bash
# 1日分 (70本)
python pipeline.py --daily --model musetalk

# モデル比較
python generate.py --count 3 --character miku --model musetalk
python generate.py --count 3 --character miku --model sadtalker
python generate.py --count 3 --character miku --model wav2lip
```
