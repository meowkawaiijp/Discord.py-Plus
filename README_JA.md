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
  ユーティリティメソッド (`.success()`, `.error()`, `.ask()`, `.paginate()`, `.interaction_type` 等) を追加した拡張Contextクラス
- **カスタムイベントデコレータ**
  メッセージ内容、リアクション、ボイスステート変化など、特定のイベントに対するハンドラをデコレータ (`@on_message_contains`, `@on_reaction_add` 等) を使って簡単に作成
- **Webhookユーティリティ**
  Webhook経由でメッセージを簡単に送信できるヘルパーメソッド (`bot.send_webhook()` または `ctx.send_webhook()`)
- **設定管理**
  ホットリロード可能な.ini形式設定システム
- **拡張機能システム**
  Jishaku連携による動的なCog読み込み

## ⚙️ インストール

1.  リポジトリをクローンします:
    ```bash
    git clone https://github.com/meowkawaiijp/Discord.py-Plus.git
    cd Discord.py-Plus
    ```
    注意: クローンURLのディレクトリ名は `Discord.py-Plus` ですが、ローカルで名前を変更した場合は `cd` コマンドを適宜調整してください。

2.  必要なライブラリをインストールします:
    ```bash
    pip install -r requirements.txt
    ```

3.  ボットを設定します:
    *   `config.ini.example` を `config.ini` にリネーム（またはコピー）します。
    *   `config.ini` を編集し、`[Bot]` セクションにボットトークンを追加します:
        ```ini
        [Bot]
        token = あなたのボットトークンをここに
        prefix = !
        ```
    *   必要に応じて他の設定も調整してください。

4.  ボットを起動します:
    デフォルトでは、新機能を含むメインのサンプルを実行できます:
    ```bash
    python example/simple_example.py
    ```
    もし古いバージョンのこのREADMEで言及されていたようなメインの `bot.py` を使用している場合は、それが更新されていることを確認するか、上記のサンプルを使用してください。

## 💡 基本的な使い方

リポジトリ内の `example/simple_example.py` ファイルが大幅に更新されました。このファイルは、新しく追加されたイベントデコレータやユーティリティを含む、Discord.py-Plusのさまざまな機能を使用するための包括的なガイドとして機能します。

**実践的な実装詳細と実行可能なコードについては、`example/simple_example.py` ファイルを参照することを強くお勧めします。**

`simple_example.py` ファイルでは、元のシンプルな `ping` コマンドやロガー設定はそのままに、以下の内容が示されています：

*   **`EnhancedBot` の初期化**: `config.ini` から設定を読み込むための `ConfigManager` と、必要なDiscordインテントを使用して `EnhancedBot` をセットアップする方法。
*   **ハイブリッドコマンド**: 基本的な `ping` ハイブリッドコマンドと、メッセージを削除する前に `ctx.ask()` を使用してユーザー確認を行う改良版 `purge` ハイブリッドコマンド。インタラクティブなダイアログの使用例です。
*   **`ExampleCog`**: `simple_example.py` 内にサンプルCogクラスが定義されています。このCogはボットによって読み込まれ、新しいカスタムイベントデコレータを整理して使用する明確な例を提供します：
    *   **`@on_message_contains`**: このデコレータが付いたメソッドは、メッセージに特定のサブストリング（例: "hello example"）が含まれている場合にトリガーされ、応答します。
    *   **`@on_reaction_add`**: 別のメソッドは、特定の絵文字リアクション（例: "👍"）がメッセージに追加されたときに動作します。
    *   **`@on_user_voice_join`**: ある関数例では、ユーザーが任意のボイスチャンネルに参加したときにログを記録したりアナウンスしたりします。
*   **Webhookユーティリティ**: `webhooktest` ハイブリッドコマンドは、`ctx.send_webhook()` メソッドを使用して、指定されたWebhook URLにリッチな埋め込みを含むメッセージを送信する方法を示します。これは、ボットが完全なメンバーでなくても、またはメッセージ送信に特定のボット権限を使用しなくても、チャンネルに整形されたメッセージを送信するのに役立ちます。
*   **インタラクションタイプの検出**: `invoketype` ハイブリッドコマンドは、`EnhancedContext` で利用可能な `ctx.interaction_type` プロパティを使用して、コマンドがスラッシュコマンド、メッセージコンポーネント（ボタンクリックなど）、または従来のプレフィックスベースのメッセージコマンド経由で呼び出されたかどうかを判断する方法を示します。

**更新されたサンプルを実行するには：**

1.  「インストール」セクションで説明されているように、`config.ini` ファイルが正しく設定されていること（特にボットトークン）を確認してください。
2.  `webhooktest` コマンドを完全にテストするには、Discordサーバーチャンネルの有効なWebhook URLが必要です。コマンドを呼び出す際に、このURLを引数として渡すことができます。
3.  ターミナルを開き、リポジトリのルートディレクトリに移動して、Pythonを使用してサンプルファイルを実行します：
    ```bash
    python example/simple_example.py
    ```

この大幅に拡張された `simple_example.py` は、新しいコンポーネントがどのように連携して動作し、それらを独自のCogやボットロジック全体に統合する方法を理解するための最良のリソースとなることを意図しています。

*利用可能なすべてのカスタムイベントデコレータとその特定のパラメータ（`ignore_bot`、`case_sensitive`、`target_channel`など）の詳細なリストについては、`core/custom_events.py`ファイル内のdocstringを参照してください。*

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
