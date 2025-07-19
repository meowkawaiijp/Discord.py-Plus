# Dispyplus (Discord.py-Plus)

Dispyplusはdiscord.pyを使ったDiscordボット開発を強化するPythonライブラリです。設定管理、イベント処理、UIコンポーネントなどのユーティリティを提供します。

## インストール

```bash
pip install git+https://github.com/meowkawaiijp/Discord.py-Plus.git
```

## 基本的な使い方

```python
from dispyplus import DispyplusBot
import discord

intents = discord.Intents.default()
intents.message_content = True

bot = DispyplusBot(command_prefix="!", intents=intents, config_path='config.ini')

@bot.hybrid_command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

bot.run()
```

## ライセンス

MITライセンスです。詳細はLICENSEファイルを参照してください。
