# Dispyplus (Discord.py-Plus)

Dispyplusはdiscord.pyを使ったDiscordボット開発を強化するPythonライブラリです。高度なページネーション、フォーム、設定管理、UIコンポーネントなどの機能を提供します。

## 特徴

- 🔧 **設定管理**: JSONファイルや環境変数からの設定読み込み
- 🎯 **カスタムイベント**: 優先度とコンディション付きのイベントハンドリング
- 📄 **高度なページネーション**: ボタンやセレクトメニューを使用したページネーター
- 📝 **フォームシステム**: バリデーション付きのDiscordモーダルフォーム
- 🛠️ **ユーティリティ**: アバター取得、タイムスタンプフォーマット、安全なメッセージ送信など
- ✅ **確認ダイアログ**: ユーザー確認のためのインタラクティブなダイアログ

## インストール

```bash
pip install git+https://github.com/meowkawaiijp/Discord.py-Plus.git
```

## クイックスタート

```python
import discord
from discord.ext import commands
from dispyplus import ConfigManager, Paginator, Form, create_embed

# 設定管理
config = ConfigManager("config.json")
config.load()

# ボット初期化
bot = commands.Bot(command_prefix=config.get('bot.prefix', '!'))

@bot.slash_command()
async def paginate(ctx):
    """ページネーションの例"""
    pages = ["ページ 1", "ページ 2", "ページ 3"]
    paginator = Paginator(pages)
    await paginator.start(ctx.interaction)

@bot.slash_command()
async def user_form(ctx):
    """フォームの例"""
    form = Form("ユーザー情報")
    form.field("name", "名前", required=True)
    form.field("email", "メールアドレス", validator=Validators.email)
    
    result = await form.show(ctx.interaction)
    if result:
        embed = create_embed(
            title="フォーム送信完了",
            description=f"名前: {result['name']}\nメール: {result['email']}"
        )
        await ctx.followup.send(embed=embed)

bot.run(config.get('bot.token'))
```

## 主要コンポーネント

### 1. 設定管理 (Config)

```python
from dispyplus import ConfigManager

# 設定ファイルの読み込み
config = ConfigManager("config.json")
config.load()

# ドット記法での設定アクセス
bot_name = config.get('bot.name', 'デフォルト名')
config.set('bot.prefix', '!')

# 環境変数からの設定読み込み
config = ConfigManager.from_env(prefix="BOT_")
```

### 2. ページネーション

```python
from dispyplus import Paginator, EmbedPaginator

# テキストページネーション
pages = ["ページ1の内容", "ページ2の内容", "ページ3の内容"]
paginator = Paginator(pages, timeout=60.0)
await paginator.start(interaction)

# Embedページネーション
embeds = [discord.Embed(title=f"ページ {i}") for i in range(1, 4)]
embed_paginator = EmbedPaginator(embeds)
await embed_paginator.start(interaction)
```

### 3. フォームシステム

```python
from dispyplus import Form, Validators, Transformers

# フォーム作成
form = Form("ユーザー登録フォーム")

form.field(
    "username", 
    "ユーザー名",
    min_length=3,
    max_length=20,
    required=True
).field(
    "email",
    "メールアドレス", 
    validator=Validators.email
).field(
    "age",
    "年齢",
    validator=Validators.integer(min_val=13, max_val=120),
    transformer=Transformers.integer
)

# フォーム表示と結果取得
result = await form.show(interaction)
if result:
    print(f"ユーザー名: {result['username']}")
    print(f"メール: {result['email']}")
    print(f"年齢: {result['age']}")  # 整数に変換済み
```

### 4. カスタムイベント

```python
from dispyplus import EventHandler

event_handler = EventHandler(bot)

@event_handler.listen('user_level_up', priority=10)
async def on_level_up(event, user, new_level):
    """ユーザーレベルアップ時の処理"""
    channel = bot.get_channel(123456789)
    await channel.send(f"{user.mention} がレベル {new_level} になりました！")

# イベント発行
await event_handler.dispatch('user_level_up', user, 5)
```

### 5. 確認ダイアログ

```python
from dispyplus import ConfirmDialog

dialog = ConfirmDialog(
    confirm_label="削除する",
    cancel_label="キャンセル",
    timeout=30.0
)

result = await dialog.start(
    interaction,
    content="本当にこのデータを削除しますか？"
)

if result:
    # 削除処理
    await interaction.followup.send("削除しました。")
else:
    await interaction.followup.send("キャンセルしました。")
```

### 6. ユーティリティ関数

```python
from dispyplus import get_user_avatar, format_timestamp, safe_send, create_embed
from datetime import datetime

# ユーザーアバター取得
avatar_url = get_user_avatar(user, size=512)

# タイムスタンプフォーマット
timestamp = format_timestamp(datetime.utcnow(), style='R')  # 相対時間

# 安全なメッセージ送信（エラーハンドリング付き）
await safe_send(channel, "メッセージ", embed=embed, fallback_dm=True)

# Embed作成ヘルパー
embed = create_embed(
    title="タイトル",
    description="説明",
    color=discord.Color.blue(),
    author=user,
    timestamp=datetime.utcnow()
)
```

## サンプルコード

完全なサンプルボットは `examples/basic_bot.py` をご覧ください。

## API リファレンス

### ConfigManager

- `load()`: 設定ファイルを読み込み
- `save()`: 設定ファイルを保存
- `get(key, default=None)`: 設定値取得
- `set(key, value)`: 設定値設定
- `from_env(prefix)`: 環境変数から設定作成

### Paginator

- `__init__(pages, timeout=180.0, show_page_count=True)`: ページネーター初期化
- `start(interaction)`: ページネーター開始

### Form

- `field(name, label, **options)`: フィールド追加
- `show(interaction)`: フォーム表示
- `validate(data)`: データ検証

### EventHandler

- `listen(event_name, priority=0, condition=None, once=False)`: イベントリスナー登録
- `dispatch(event_name, *args, **kwargs)`: イベント発行

## 要件

- Python 3.8+
- discord.py 2.0+
- aiohttp 3.8+

## ライセンス

MITライセンスです。詳細はLICENSEファイルを参照してください。

## コントリビューション

プルリクエストやイシューは歓迎します。バグ報告や機能要望がありましたら、GitHubのIssuesをご利用ください。
