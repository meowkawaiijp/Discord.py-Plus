# Dispyplus (Discord.py-Plus)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/dispyplus.svg)](https://badge.fury.io/py/dispyplus) <!-- PyPIに公開後有効化 -->
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English](/README.md)

Dispyplusは、discord.pyを使用したDiscordボット開発を強化するための様々な拡張機能やユーティリティを提供するPythonライブラリです。設定管理、カスタムイベント処理、ページネーターや確認ダイアログのようなUIコンポーネントなど、一般的なタスクを簡素化します。

## 🚀 主な機能

- **拡張ボットクラス (`DispyplusBot`)**:
    - ホットリロード対応の統合設定管理 (`ConfigManager`)。
    - ロギングの自動セットアップ。
    - タスクスケジューリング機能。
    - 動的な拡張機能 (Cog) 読み込み。
    - Jishaku統合サポート。
- **拡張コンテキスト (`EnhancedContext`)**:
    - スタイル付きメッセージ送信ユーティリティメソッド: `.success()`, `.error()`, `.warning()`, `.info()`。
    - 対話型ダイアログ:
        - はい/いいえ確認用の `.ask()` (`dispyplus.ui.ConfirmationView` を使用)。
        - **新機能**: モーダルフォーム表示・送信待機用の `.ask_form(YourFormClass)` (`DispyplusForm` を使用)。
    - ページネーション:
        - **新機能**: リスト、非同期イテレータ、テキスト行、カスタムEmbedリストなどを柔軟にページ分けする `PaginatorView` を使用した `.paginate(data_source, ...)`。多様なナビゲーションコントロールをサポート。
    - インタラクションタイプ確認プロパティ: `.interaction_type`。
    - Webhook送信ヘルパー: `.send_webhook()`。
- **UIコンポーネント (`dispyplus.ui`)**:
    - `EnhancedView`: タイムアウト処理が組み込まれたベースビュー。
    - `ConfirmationView`: 簡単な はい/いいえ 確認ダイアログ。
    - `PaginatedSelectView`: セレクトメニューの選択肢をページ分けします。
    - `SimpleSelectView`: 基本的なセレクトメニュー。
    - **新機能**: `PaginatorView`: 様々なデータ型に対応し、複数のコントロールオプション（ボタン、ページジャンプモーダル、セレクトメニュー）を持つ高機能なページネーション。
    - **新機能**: `DispyplusForm`: フィールド定義、型変換、バリデーション機能を備えたモーダルフォームを宣言的に作成。`EnhancedContext.ask_form()` と連携。
    - **新機能**: `JumpToPageModal`: `PaginatorView` で使用され、ユーザーが特定のページにジャンプできるようにするモーダル。
- **カスタムイベントシステム**:
    - カスタムイベントタイプを管理・ディスパッチする `CustomEventManager`。
    - 条件ベースフィルタリング付きの一般的なDiscordイベント用デコレータ:
        - `@on_message_contains`: メッセージ内容に部分文字列が含まれる場合に発火。
        - `@on_message_matches`: メッセージ内容が正規表現にマッチする場合に発火。
        - `@on_reaction_add` / `@on_reaction_remove`: 特定のリアクション用。
        - `@on_typing_in` / `@on_user_typing`: チャンネル/ユーザーのタイピングイベント用。
        - `@on_user_voice_join` / `@on_user_voice_leave` / `@on_user_voice_move`: ボイスステート変更用。
        - `@on_member_nickname_update`, `@on_member_role_add` / `@on_member_role_remove`, `@on_member_status_update`: メンバー更新用。
        - `@on_guild_name_change`, `@on_guild_owner_change`: サーバー更新用。
- **便利なデコレータ**:
    - `@permission_check`: ユーザー権限やロールを簡単にチェック。
    - `@log_execution`: コマンド実行詳細をログ記録。
- **Webhookユーティリティ**:
  - `DispyplusBot.send_webhook()` および `EnhancedContext.send_webhook()` による簡単なWebhookメッセージ送信。

## ⚙️ インストール

```bash
pip install git+https://github.com/meowkawaiijp/dispyplus.git
```

## 💡 基本的な使い方

`DispyplusBot` とその機能の簡単な使用例です:

```python
import asyncio
import discord
from discord.ext import commands # commands.Cog をインポートするために追加
from dispyplus import DispyplusBot, EnhancedContext, on_message_contains

# Intentsの設定
intents = discord.Intents.default()
intents.message_content = True # メッセージ内容関連のイベント/コマンドに必要
intents.members = True       # メンバー関連のイベントに役立つことが多い

# ボットの初期化
# config.ini ファイルへのパスを指定します
bot = DispyplusBot(
    command_prefix="!",
    intents=intents,
    config_path='config.ini' # DispyplusBotが内部でConfigManagerを管理します
)

# 簡単なハイブリッドコマンド
@bot.hybrid_command(name="ping", description="Pong! と返します")
async def ping(ctx: EnhancedContext):
    await ctx.success(f"Pong! 遅延: {bot.latency*1000:.2f}ms")

# カスタムイベントデコレータの使用 (Cog内での使用を推奨)
# この例はメインファイルにありますが、通常はCogに配置します。
@on_message_contains("こんにちはボット", ignore_bot=True)
async def respond_to_hello(ctx: EnhancedContext, message: discord.Message):
    # この関数はデコレータにより自動的に登録されます。
    # ボットの on_message ハンドラが条件を満たした場合にこれを呼び出します。
    # Cog内で定義する場合、Cogがボットに追加されている必要があります。
    await message.reply(f"こんにちは、{message.author.mention}さん！")

# サンプルCog (コマンドやイベントハンドラを整理するために推奨)
class MyCog(commands.Cog):
    def __init__(self, bot: DispyplusBot):
        self.bot = bot

    @commands.command()
    async def ask_test(self, ctx: EnhancedContext):
        confirm = await ctx.ask("本当にこれを実行しますか？")
        if confirm:
            await ctx.send("はい と回答しました！")
        elif confirm is False: # 明示的に False (Noneではない、タイムアウトした場合)
            await ctx.send("いいえ と回答しました。")
        else:
            await ctx.send("時間内に回答しませんでした。")

    @on_message_contains("魔法の言葉") # Cog内のカスタムイベント
    async def magic_handler(self, ctx: EnhancedContext, message: discord.Message):
        await message.channel.send("魔法の言葉を言いましたね！")

async def main():
    # config.ini に 'Bot' セクションと 'token' があることを確認してください
    # 設定例 config.ini:
    # [Bot]
    # token = あなたのボットトークン
    # prefix = !
    #
    # [Logging]
    # level = INFO
    # file = bot.log

    # Cogの追加
    await bot.add_cog(MyCog(bot))

    # config.ini からトークンを取得してボットを起動
    # トークンは bot.config.get('Bot', 'token') で取得されます
    token = bot.config.get('Bot', 'token')
    if not token:
        print("エラー: config.ini にボットトークンが見つかりません。")
        return
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
```

全てのカスタムイベントデコレータや、様々なUIコンポーネント（ボタン、セレクトメニュー、モーダルなどの `discord.ui` ベースの例）を含むより詳細な例については、リポジトリの `example/simple_example.py` および `example/ui_example.py` ファイルを参照してください。

## 🔧 設定 (`config.ini`)

DispyplusBotは設定に `config.ini` ファイルを使用します。デフォルトでは、カレントワーキングディレクトリの `config.ini` を探します。

最小限の `config.ini` は以下のようになります:
```ini
[Bot]
token = あなたのDISCORDボットトークンをここに
prefix = !

[Logging]
# オプション: デフォルトは INFO
level = INFO
# オプション: デフォルトは bot.log
file = my_bot.log
```

`ConfigManager` はホットリロードをサポートしています。ボット実行中に `config.ini` を変更すると、変更が反映されることがあります（例: プレフィックス、ログレベル、ボットが使用するカスタム設定など）。設定がリロードされると、ボットは `on_config_reload` イベントを発行します。

## 🤝 貢献

貢献を歓迎します！以下の手順に従ってください:

1. リポジトリをフォークします。
2. 機能ブランチを作成します: `git checkout -b feature/あなたの新機能`
3. 変更をコミットします: `git commit -m '機能追加'`
4. ブランチにプッシュします: `git push origin feature/あなたの新機能`
5. プルリクエストを開きます。

必要に応じてテストを更新してください。

## 📜 ライセンス

MITライセンスで配布されています。詳細は `LICENSE` ファイルを参照してください。
