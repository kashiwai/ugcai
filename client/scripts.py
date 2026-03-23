"""
UGC Engine - Script Generator (Claude API)
============================================
Generates video scripts in batch using Claude API.
"""

import json
import random
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, CHARACTERS, CONTENT_TYPES

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# claude-sonnet-4-6 = 最新モデル (2026年3月現在)
# claude-3-opus-20240229    = 最高品質（低速・高コスト）
CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """あなたは日本のSNSマーケティングの天才CMOです。
TikTok/Instagram/Xで1億ビューを達成した実績があります。

以下のサービスのUGC動画台本を生成してください：
- マウスピース矯正サービス（35万円）
- 年間100枚のマウスピースで矯正力1.5倍
- キレイラインを作った会社の第2弾サービス
- 競合: インビザライン(80-120万) / キレイライン(60-65万)

ルール:
- 台本は30秒（150-200文字）
- 最初の一文が最重要（フック）。スクロールを止める
- 広告感ゼロ。友達に話すような口語体
- 必ず「35万円」の数字を含める
- 指定されたキャラクターの口調/性格で話す

出力形式: JSONのみ。余計なテキストなし。
[{"character": "キャラキー", "type": "コンテンツ種別", "hook": "フック(15文字以内)", "text": "30秒台本の全文", "telop": "テロップ案1 / テロップ案2 / テロップ案3", "hashtags": "#ハッシュタグ1 #ハッシュタグ2 #ハッシュタグ3 #ハッシュタグ4 #ハッシュタグ5"}]
"""

def generate_scripts(count=10, characters=None, content_type=None):
    """Generate video scripts using Claude API"""
    if characters is None:
        characters = list(CHARACTERS.keys())

    results = []
    batch_size = min(count, 20)  # Claude can handle ~20 scripts per call
    remaining = count

    while remaining > 0:
        current_batch = min(batch_size, remaining)

        # Build persona instructions
        char_descs = []
        for ck in characters:
            ch = CHARACTERS[ck]
            char_descs.append(f"- {ck}: {ch['name']} / {ch['tone']} / {ch['persona_prompt']}")

        char_instruction = "\n".join(char_descs)
        type_instruction = f"コンテンツ種別は「{content_type}」のみ" if content_type else "全種別からランダムに選択"

        user_prompt = f"""{current_batch}本の台本を生成してください。

キャラクター（ランダムに使い分け）:
{char_instruction}

{type_instruction}

各台本はユニークに。フックは全て異なるパターンで。"""

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            text = response.content[0].text
            clean = text.replace("```json", "").replace("```", "").strip()
            scripts = json.loads(clean)
            results.extend(scripts)

        except Exception as e:
            print(f"  Script generation error: {e}")
            # Fallback: generate simple scripts locally
            for _ in range(current_batch):
                char = random.choice(characters)
                results.append({
                    "character": char,
                    "type": random.choice(CONTENT_TYPES),
                    "hook": "120万の矯正が35万でできるって知ってた？",
                    "text": f"まって、これ聞いて。マウスピース矯正って普通80万から120万するんだけど、35万円でできるサービス見つけたの。しかも年間100枚のマウスピースで矯正力1.5倍。キレイライン作った会社の新サービスなんだって。詳しくはプロフのリンクから見てみて。",
                    "telop": "120万→35万 / 矯正力1.5倍 / 100枚のマウスピース",
                    "hashtags": "#マウスピース矯正 #35万矯正 #歯列矯正 #矯正革命 #歯並び",
                })

        remaining -= current_batch

    return results[:count]


if __name__ == "__main__":
    scripts = generate_scripts(count=3, characters=["miku", "kenta"])
    for s in scripts:
        print(f"\n[{s['character']}] {s['hook']}")
        print(f"  {s['text'][:80]}...")
