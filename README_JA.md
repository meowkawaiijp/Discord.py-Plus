# Discord.py-Plus

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

高度な機能を備えたDiscord.py拡張フレームワーク

## 🚀 主な機能

- **スマートページネーション**  
  大規模データのインタラクティブなページ管理
- **対話型ダイアログ**  
  確認ダイアログと動的選択メニューの内蔵
- **タスクスケジューラー**  
  柔軟なタイミング設定による定期タスク実行
- **拡張コンテキスト**  
  ユーティリティメソッドを追加した拡張Contextクラス
- **設定管理**  
  ホットリロード可能な.ini形式設定システム
- **拡張機能システム**  
  Jishaku連携による動的なCog読み込み

## ⚙️ インストール

1. リポジトリをクローン
```bash
git clone https://github.com/meowkawaiijp/Discord.py-Plus.git
cd Discord.py-Enhanced
```

2. 依存関係をインストール
```bash
pip install -r requirements.txt
```

3. Botを起動
```bash
python bot.py
```

## 💡 基本的な使い方

```python
import asyncio
import logging
from core.Dispyplus import EnhancedBot
from core.config import ConfigManager
from core.decorators import log_execution
from core.view import EnhancedContext
import discord

CONFIG_FILE = 'config.ini'

config = ConfigManager(CONFIG_FILE)

logging.basicConfig(
    level=config.get('Logging', 'level', fallback='INFO'),
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    handlers=[
        logging.FileHandler(
            filename=config.get('Logging', 'file', fallback='bot.log'),
            encoding='utf-8', mode='a'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = EnhancedBot(
    command_prefix=config.get('Bot', 'prefix', fallback='!'),
    intents=intents,
    config=config
)

@bot.hybrid_command(name="ping", description="pong")
@log_execution()
async def ping(ctx: EnhancedContext):
    await ctx.success(f"pong")

async def main():
    await bot.start(config.get('Bot', 'token'))

if __name__ == "__main__":
    asyncio.run(main())
```

## 🤝 貢献について

1. リポジトリをフォーク
2. 機能ブランチ作成  
   `git checkout -b feature/新機能`
3. 変更をコミット  
   `git commit -m '新機能を追加'`
4. ブランチにプッシュ  
   `git push origin feature/新機能`
5. プルリクエストを作成

## 📜 ライセンス

MITライセンスで配布されています。詳細は`LICENSE`ファイルを参照してください。
