#!/usr/bin/env bash
# ============================================================
# UGC Engine - Mac 初期セットアップスクリプト
# Usage: bash setup.sh
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "=================================================="
echo "  UGC Engine - Setup"
echo "=================================================="
echo ""

# ---- 1. Homebrew ----
echo "▶ Checking Homebrew..."
if ! command -v brew &>/dev/null; then
  echo -e "${YELLOW}  Installing Homebrew...${NC}"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  echo -e "${GREEN}  ✓ Homebrew found${NC}"
fi

# ---- 2. Python 3.11 ----
echo "▶ Checking Python 3.11..."
if ! command -v python3.11 &>/dev/null; then
  echo -e "${YELLOW}  Installing Python 3.11...${NC}"
  brew install python@3.11
else
  echo -e "${GREEN}  ✓ Python 3.11 found${NC}"
fi

# ---- 3. FFmpeg ----
echo "▶ Checking FFmpeg..."
if ! command -v ffmpeg &>/dev/null; then
  echo -e "${YELLOW}  Installing FFmpeg...${NC}"
  brew install ffmpeg
else
  echo -e "${GREEN}  ✓ FFmpeg found: $(ffmpeg -version 2>&1 | head -1)${NC}"
fi

# ---- 4. Python dependencies ----
echo "▶ Installing Python dependencies..."
pip3.11 install --quiet anthropic requests boto3 tqdm python-dotenv 2>&1 | tail -3
echo -e "${GREEN}  ✓ Python packages installed${NC}"

# ---- 5. .env ----
echo "▶ Checking .env file..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo -e "${YELLOW}  .env created from template. Please fill in your API keys.${NC}"
else
  echo -e "${GREEN}  ✓ .env exists${NC}"
fi

# ---- 6. Directory structure ----
echo "▶ Creating directory structure..."
mkdir -p "$SCRIPT_DIR/assets/faces"
mkdir -p "$SCRIPT_DIR/output/scripts"
mkdir -p "$SCRIPT_DIR/output/voices"
mkdir -p "$SCRIPT_DIR/output/videos"
echo -e "${GREEN}  ✓ Directories created${NC}"

# ---- 7. VOICEVOX ----
echo "▶ Checking VOICEVOX Engine..."
if curl -s --max-time 3 http://localhost:50021/speakers &>/dev/null; then
  echo -e "${GREEN}  ✓ VOICEVOX running on localhost:50021${NC}"
else
  echo -e "${YELLOW}  ⚠ VOICEVOX not detected${NC}"
  echo "    → Download: https://voicevox.hiroyuki.cloud/"
  echo "    → Launch the app, then verify: curl http://localhost:50021/speakers"
fi

# ---- 8. Node.js (for Railway server) ----
echo "▶ Checking Node.js..."
if ! command -v node &>/dev/null; then
  echo -e "${YELLOW}  Installing Node.js...${NC}"
  brew install node
else
  echo -e "${GREEN}  ✓ Node.js $(node -v)${NC}"
fi

# ---- 9. Railway CLI ----
echo "▶ Checking Railway CLI..."
if ! command -v railway &>/dev/null; then
  echo -e "${YELLOW}  Installing Railway CLI...${NC}"
  npm install -g @railway/cli --silent
else
  echo -e "${GREEN}  ✓ Railway CLI found${NC}"
fi

# ---- 10. Docker ----
echo "▶ Checking Docker..."
if ! command -v docker &>/dev/null; then
  echo -e "${YELLOW}  ⚠ Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/${NC}"
else
  echo -e "${GREEN}  ✓ Docker found${NC}"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}  Setup complete!${NC}"
echo "=================================================="
echo ""
echo "次のステップ:"
echo "  1. .env に R2 のキーを記入してください"
echo "  2. assets/faces/ に8キャラの顔画像を置いてください (512x512 PNG)"
echo "  3. VOICEVOX Engine を起動してください"
echo "  4. Railway にサーバーをデプロイ: cd server && railway init && railway up"
echo "  5. RunPod Endpoint を作成して RUNPOD_ENDPOINT_ID を .env に記入"
echo "  6. テスト実行: cd client && python pipeline.py --count 2 --dry-run"
echo ""
