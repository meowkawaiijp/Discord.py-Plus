import os
import asyncio
import logging
import datetime
from datetime import timezone
from pathlib import Path
from functools import wraps
from typing import Optional, List, Union, Callable, Coroutine, Dict, TypeVar, Generic, cast
import discord
from discord.ext import commands

T = TypeVar('T')
import os
import configparser
import logging
from typing import Any, Optional
import json

class ConfigManager:
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = os.path.abspath(config_file)
        self.config = configparser.ConfigParser()
        self._ensure_config_exists()
        self._load_config()
        self._last_modified = self._get_modified_time()

    def _ensure_config_exists(self) -> None:
        """設定ファイルの存在確認と新規作成"""
        config_dir = os.path.dirname(self.config_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            logging.info(f"Created config directory: {config_dir}")
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write('# Auto-generated configuration file\n')
            logging.info(f"Created new config file: {self.config_file}")

    def _load_config(self) -> None:
        """設定ファイルを読み込む"""
        try:
            read_files = self.config.read(self.config_file, encoding='utf-8')
            if not read_files:
                logging.warning(f"Config file not found or empty: {self.config_file}")
        except Exception as e:
            logging.error(f"設定ファイル読み込みエラー: {str(e)}")
            raise

    def _get_modified_time(self) -> float:
        """ファイルの最終更新時刻を取得"""
        try:
            return os.path.getmtime(self.config_file)
        except OSError as e:
            logging.error(f"最終更新時刻取得エラー: {str(e)}")
            return 0

    def reload(self) -> bool:
        """設定ファイルの動的再読み込み。変更があった場合はTrueを返す"""
        current_time = self._get_modified_time()
        if current_time > self._last_modified:
            self._load_config()
            self._last_modified = current_time
            return True
        return False

    def get(self, section: str, key: str, fallback: Optional[Any] = None) -> Any:
        """型推論付き設定値取得"""
        if not self.config.has_section(section):
            return fallback
            
        if not self.config.has_option(section, key):
            return fallback
            
        value = self.config.get(section, key, fallback=fallback)
        if not isinstance(value, str):
            return value
            
        # 型変換の試行
        if value.lower() in ('true', 'yes', 'on', '1'):
            return True
        if value.lower() in ('false', 'no', 'off', '0'):
            return False
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                # JSON形式の値の場合
                if value.startswith(('[', '{')):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        pass
        return value

    def set(self, section: str, key: str, value: Any) -> None:
        """設定値の保存"""
        if not self.config.has_section(section):
            self.config.add_section(section)
            
        # 複雑な型はJSON形式で保存
        if isinstance(value, (list, dict, bool)):
            value = json.dumps(value, ensure_ascii=False)
            
        self.config.set(section, key, str(value))

    def save(self) -> None:
        """設定変更をファイルに保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            self._last_modified = self._get_modified_time()
            logging.info(f"設定ファイルを保存しました: {self.config_file}")
        except Exception as e:
            logging.error(f"設定ファイル保存エラー: {str(e)}")
            raise

    def __str__(self) -> str:
        """現在の設定内容を文字列で表現"""
        return "\n".join(
            f"[{section}]\n" + "\n".join(
                f"{key} = {value}" for key, value in self.config.items(section)
            ) for section in self.config.sections()
        )

class EnhancedView(discord.ui.View):
    """タイムアウト処理を改善したView基底クラス

    UIコンポーネント全体の無効化や、タイムアウト時のカスタム処理を実装。
    """
    def __init__(self, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def on_timeout(self) -> None:
        """タイムアウト発生時の処理

        ・内部ロックを用いて重複処理を防止  
        ・全UIコンポーネントの無効化とカスタムタイムアウト処理の実行
        """
        if self._closed:
            return

        async with self._lock:
            self._closed = True
            await self.disable_all_components()
            await self.on_custom_timeout()

    async def disable_all_components(self) -> None:
        """すべてのUIコンポーネントを無効化する

        ・ボタンなどのインタラクション部品の操作を無効にする  
        ・メッセージが存在する場合は更新を試みる
        """
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                logging.error(f"View update error: {e}")

    async def on_custom_timeout(self) -> None:
        """タイムアウト時に実行するカスタム処理"""
        pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        """インタラクション処理で発生したエラーのハンドリング

        エラーメッセージをログ出力し、ユーザーにはエラー通知を送信する。
        """
        logging.error(f"View interaction error: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "エラーが発生しました。しばらく経ってからもう一度お試しください。",
                ephemeral=True
            )


class Paginator(EnhancedView, Generic[T]):
    """型安全かつ柔軟なページネーションシステム

    指定データリストを複数ページに分割し、各ページをEmbedとして表示する。
    """
    def __init__(
        self,
        data: List[T],
        per_page: int = 10,
        embed_template: Optional[Callable[[List[T], int], discord.Embed]] = None,
        button_style: discord.ButtonStyle = discord.ButtonStyle.primary,
        timeout: float = 120,
        owner_only: bool = False
    ):
        super().__init__(timeout=timeout)
        self.data = data
        self.per_page = max(1, per_page)  # 最低1項目／ページ
        self.current_page = 0
        self.embed_template = embed_template or self.default_embed
        self.total_pages = max(1, (len(data) + per_page - 1) // per_page)
        self.button_style = button_style
        self.owner_id: Optional[int] = None
        self.owner_only = owner_only

        # ページ数が1ページのみの場合、操作用ボタンを非表示にする
        if self.total_pages <= 1:
            self.clear_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """操作権限チェック

        ・所有者限定の場合、操作できるユーザーを制限する
        """
        if self.owner_only and self.owner_id and interaction.user.id != self.owner_id:
            await interaction.response.send_message("このページネーションを操作する権限がありません", ephemeral=True)
            return False
        return True

    def default_embed(self, page_data: List[T], page: int) -> discord.Embed:
        """デフォルトのEmbed生成処理

        ・各ページのデータを文字列として結合し、Embedにセットする
        """
        embed = discord.Embed(
            title=f"ページ {page + 1}/{self.total_pages}",
            description="\n".join(str(item) for item in page_data),
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"全 {len(self.data)} 項目")
        return embed

    def get_page_data(self, page: int) -> List[T]:
        """指定ページのデータを抽出する"""
        start = page * self.per_page
        end = start + self.per_page
        return self.data[start:end]

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """最初のページへ移動するボタンの処理"""
        if self.current_page == 0:
            await interaction.response.defer()
            return
        self.current_page = 0
        await self._update_view(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """前のページへ移動するボタンの処理"""
        if self.current_page == 0:
            await interaction.response.defer()
            return
        self.current_page = max(0, self.current_page - 1)
        await self._update_view(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """次のページへ移動するボタンの処理"""
        if self.current_page >= self.total_pages - 1:
            await interaction.response.defer()
            return
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        await self._update_view(interaction)

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """最後のページへ移動するボタンの処理"""
        if self.current_page >= self.total_pages - 1:
            await interaction.response.defer()
            return
        self.current_page = self.total_pages - 1
        await self._update_view(interaction)

    async def _update_view(self, interaction: discord.Interaction):
        """内部処理：ページ更新時のEmbedおよびボタン状態の更新"""
        try:
            # ボタンの有効/無効状態を更新
            self.first_page.disabled = self.current_page == 0
            self.prev_page.disabled = self.current_page == 0
            self.next_page.disabled = self.current_page >= self.total_pages - 1
            self.last_page.disabled = self.current_page >= self.total_pages - 1

            if interaction.response.is_done():
                await interaction.followup.edit_message(
                    message_id=self.message.id,
                    embed=self.embed_template(self.get_page_data(self.current_page), self.current_page),
                    view=self
                )
            else:
                await interaction.response.edit_message(
                    embed=self.embed_template(self.get_page_data(self.current_page), self.current_page),
                    view=self
                )
        except discord.HTTPException as e:
            logging.error(f"Paginator update error: {e}")

    @classmethod
    async def start(
        cls, 
        destination: Union[commands.Context, discord.Interaction], 
        *args, 
        **kwargs
    ) -> 'Paginator[T]':
        """ページネーターの初期表示を行い、開始する

        ・送信先（ContextまたはInteraction）にEmbedとUIを送信  
        ・送信先のユーザーを所有者として設定
        """
        instance = cls(*args, **kwargs)
        page_data = instance.get_page_data(0)
        embed = instance.embed_template(page_data, 0)

        # 最初のページでは前へ移動ボタンを無効化
        instance.first_page.disabled = True
        instance.prev_page.disabled = True

        # 1ページのみの場合は次へ移動ボタンも無効化
        if instance.total_pages <= 1:
            instance.next_page.disabled = True
            instance.last_page.disabled = True

        # 所有者の設定と送信処理
        if isinstance(destination, commands.Context):
            instance.owner_id = destination.author.id
            instance.message = await destination.send(embed=embed, view=instance)
        elif isinstance(destination, discord.Interaction):
            instance.owner_id = destination.user.id
            if destination.response.is_done():
                instance.message = await destination.followup.send(embed=embed, view=instance)
            else:
                await destination.response.send_message(embed=embed, view=instance)
                instance.message = await destination.original_response()

        return instance


class EnhancedContext(commands.Context):
    """拡張コンテキストクラス

    標準Contextに各種ユーティリティメソッドを追加。
    """
    @property
    def created_at(self) -> datetime.datetime:
        """メッセージの作成日時を返す"""
        return self.message.created_at

    @property
    def is_dm(self) -> bool:
        """DMかどうかを判定する"""
        return self.guild is None

    async def success(self, message: str, **kwargs) -> discord.Message:
        """成功メッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"✅ {message}",
            color=discord.Color.green()
        )
        return await self.send(embed=embed, **kwargs)

    async def warning(self, message: str, **kwargs) -> discord.Message:
        """警告メッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"⚠️ {message}",
            color=discord.Color.orange()
        )
        return await self.send(embed=embed, **kwargs)

    async def error(self, message: str, **kwargs) -> discord.Message:
        """エラーメッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"❌ {message}",
            color=discord.Color.red()
        )
        return await self.send(embed=embed, **kwargs)

    async def info(self, message: str, **kwargs) -> discord.Message:
        """情報メッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"ℹ️ {message}",
            color=discord.Color.blue()
        )
        return await self.send(embed=embed, **kwargs)

    async def ask(self, message: str, **kwargs) -> Optional[bool]:
        """確認ダイアログを表示し、ユーザーの選択結果を待機する"""
        view = ConfirmationView(require_original_user=True)
        return await view.ask(self, message, **kwargs)

    async def paginate(self, data: List[T], **kwargs) -> Paginator[T]:
        """ページネーション表示を開始する"""
        return await Paginator.start(self, data, **kwargs)


class EnhancedBot(commands.Bot):
    """拡張Botクラス

    ・設定ファイル管理、ロガー設定  
    ・タスクスケジューリング機能や動的拡張機能読み込みなどを実装
    """
    def __init__(self, *args, **kwargs):
        self.config_path = kwargs.pop('config_path', 'config.ini')
        super().__init__(*args, **kwargs)
        self.config = ConfigManager(self.config_path)
        self._task_registry: Dict[str, asyncio.Task] = {}
        self.logger = self.setup_logger()
        self.start_time = datetime.datetime.now(timezone.utc)
        self._config_watcher: Optional[asyncio.Task] = None
        self.extension_dir = Path(self.config.get('Extensions', 'directory', fallback='extensions'))

    def setup_logger(self) -> logging.Logger:
        """ロガーを初期化し、ファイルおよびコンソール出力を設定する"""
        logger = logging.getLogger(self.__class__.__name__)
        log_level = getattr(logging, self.config.get('Logging', 'level', fallback='INFO').upper())
        logger.setLevel(log_level)

        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # ログファイル設定
        log_file = self.config.get('Logging', 'file', fallback='bot.log')
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)

        file_handler = logging.FileHandler(
            filename=log_file,
            encoding='utf-8',
            mode='a'
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # 既存ハンドラを一旦削除
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        return logger

    async def setup_hook(self) -> None:
        """Bot起動前の初期化処理

        ・設定ファイルの変更監視  
        ・自動拡張機能とJishakuの読み込み  
        ・コマンドの同期
        """
        await self._start_config_watcher()

        # 自動拡張機能の読み込み
        if self.extension_dir.exists() and self.extension_dir.is_dir():
            for ext_file in self.extension_dir.glob('*.py'):
                if ext_file.stem.startswith('_'):
                    continue
                extension_name = f"{self.extension_dir.name}.{ext_file.stem}"
                try:
                    await self.load_extension(extension_name)
                    self.logger.info(f"Extension loaded: {extension_name}")
                except Exception as e:
                    self.logger.error(f"Failed to load extension {extension_name}: {e}", exc_info=True)

        # Jishaku拡張機能の読み込み（必要な場合）
        if self.config.get('Extensions', 'jishaku', fallback=False):
            try:
                await self.load_extension('jishaku')
                self.logger.info("Jishaku extension loaded successfully")
            except Exception as e:
                self.logger.error(f"Failed to load jishaku: {str(e)}")

        # コマンド同期処理
        sync_option = self.config.get('Commands', 'sync', fallback='global')
        try:
            if sync_option == 'global':
                await self.tree.sync()
                self.logger.info("Globally synced application commands")
            elif sync_option == 'none':
                self.logger.info("Command syncing disabled")
            else:
                guild_id = int(sync_option)
                await self.tree.sync(guild=discord.Object(id=guild_id))
                self.logger.info(f"Synced application commands to guild: {guild_id}")
        except Exception as e:
            self.logger.error(f"Command sync error: {e}", exc_info=True)

    async def _start_config_watcher(self):
        """内部処理：設定ファイルの変更を監視するタスクを開始する"""
        if self._config_watcher:
            return

        async def _watch_task():
            while not self.is_closed():
                try:
                    # 設定ファイルに変更があればリロードし、イベントを発火
                    if self.config.reload():
                        self.logger.info("設定ファイルが更新されました")
                        self.dispatch('config_reload')
                except Exception as e:
                    self.logger.error(f"Config watcher error: {str(e)}")
                await asyncio.sleep(10)

        self._config_watcher = self.loop.create_task(_watch_task())
        self.logger.info("設定ファイル監視タスクを開始しました")

    def schedule_task(
        self,
        coro: Coroutine,
        *,
        name: str = None,
        interval: float = None,
        daily: bool = False,
        time: datetime.time = None
    ) -> asyncio.Task:
        """タスクをスケジュールする

        ・名前重複を防止し、指定間隔または毎日の指定時刻で実行  
        ・エラー発生時は適切な待機後に再試行する
        """
        if not name:
            name = f"task_{len(self._task_registry) + 1}"

        if name in self._task_registry:
            raise ValueError(f"タスク '{name}' は既に存在します")

        async def _task_wrapper():
            try:
                self.logger.info(f"タスク '{name}' を開始しました")
                if daily and time:
                    while not self.is_closed():
                        now = datetime.datetime.now(time.tzinfo or timezone.utc)
                        target = datetime.datetime.combine(now.date(), time)
                        # 今日の指定時刻を過ぎている場合は翌日に設定
                        if now.time() >= time:
                            target += datetime.timedelta(days=1)
                        wait_seconds = (target - now).total_seconds()
                        self.logger.debug(f"タスク '{name}' は {wait_seconds:.1f} 秒後に実行されます")
                        try:
                            await asyncio.sleep(wait_seconds)
                            await coro
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            self.logger.error(f"タスク '{name}' でエラーが発生しました: {e}", exc_info=True)
                            # エラー後は15分待機
                            await asyncio.sleep(900)
                elif interval:
                    while not self.is_closed():
                        try:
                            start_time = datetime.datetime.now(timezone.utc)
                            await coro
                            # 実行時間を差し引いた待機
                            elapsed = (datetime.datetime.now(timezone.utc) - start_time).total_seconds()
                            wait_time = max(0.1, interval - elapsed)
                            await asyncio.sleep(wait_time)
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            self.logger.error(f"タスク '{name}' でエラーが発生しました: {e}", exc_info=True)
                            # エラー後は待機時間を設定
                            await asyncio.sleep(min(interval, 60))
                else:
                    await coro
            except asyncio.CancelledError:
                self.logger.info(f"タスク '{name}' がキャンセルされました")
            except Exception as e:
                self.logger.error(f"タスク '{name}' が予期せぬエラーで終了しました: {e}", exc_info=True)
            finally:
                # タスクレジストリから削除
                self._task_registry.pop(name, None)

        task = self.loop.create_task(_task_wrapper(), name=name)
        self._task_registry[name] = task
        return task

    def cancel_task(self, name: str) -> bool:
        """指定したタスクをキャンセルする  
        
        成功した場合はTrueを返す
        """
        if task := self._task_registry.get(name):
            task.cancel()
            self._task_registry.pop(name, None)
            return True
        return False

    def get_task(self, name: str) -> Optional[asyncio.Task]:
        """タスク名から該当するタスクを取得する"""
        return self._task_registry.get(name)

    def get_all_tasks(self) -> Dict[str, asyncio.Task]:
        """全登録タスクの辞書を返す"""
        return self._task_registry.copy()

    async def close(self) -> None:
        """Botの終了処理を行い、全タスクをキャンセルする"""
        self.logger.info("Botシャットダウン中...")
        # 設定ファイル監視タスクの停止
        if self._config_watcher:
            self._config_watcher.cancel()
        # 登録済みタスクのキャンセル
        for name, task in list(self._task_registry.items()):
            self.logger.info(f"タスク '{name}' を停止中...")
            task.cancel()
        await super().close()
        self.logger.info("Botは正常に終了しました")

    async def get_context(self, message, *, cls=EnhancedContext) -> EnhancedContext:
        """拡張コンテキストを取得する"""
        return await super().get_context(message, cls=cls)


def hybrid_group(**kwargs) -> Callable:
    """ハイブリッドコマンドグループのデコレータ（内部でcommands.hybrid_groupを呼び出す）"""
    def decorator(func: Callable) -> commands.HybridGroup:
        return commands.hybrid_group(**kwargs)(func)
    return decorator


def permission_check(**kwargs) -> Callable:
    """拡張パーミッションチェックのデコレータ

    指定ロール・権限のチェックを行い、条件を満たさない場合は例外を発生させる
    """
    permissions = kwargs.get('permissions', [])
    roles = kwargs.get('roles', [])
    guild_only = kwargs.get('guild_only', True)
    bot_owner_bypass = kwargs.get('bot_owner_bypass', True)

    async def predicate(ctx: EnhancedContext) -> bool:
        # Bot所有者はチェックをバイパス
        if bot_owner_bypass and await ctx.bot.is_owner(ctx.author):
            return True
        if guild_only and not ctx.guild:
            raise commands.NoPrivateMessage("このコマンドはサーバー内でのみ使用できます")
        if roles and ctx.guild:
            role_ids = [r.id if isinstance(r, discord.Role) else r for r in roles]
            if not any(role.id in role_ids for role in ctx.author.roles):
                role_names = ", ".join([f"<@&{r_id}>" if isinstance(r_id, int) else r_id for r_id in role_ids])
                raise commands.MissingAnyRole([roles, f"以下のいずれかのロールが必要です: {role_names}"])
        if permissions:
            missing = [perm for perm in permissions if not getattr(ctx.author.guild_permissions, perm, False)]
            if missing:
                readable_missing = [perm.replace('_', ' ').title() for perm in missing]
                raise commands.MissingPermissions([missing, f"以下の権限が必要です: {', '.join(readable_missing)}"])
        return True

    return commands.check(predicate)


class ConfirmationView(EnhancedView):
    """拡張確認ダイアログ

    ユーザーに対し、確認（はい/いいえ）の選択を促すUIを提供する。
    """
    def __init__(self, **kwargs):
        super().__init__(timeout=kwargs.get('timeout', 30))
        self.require_original_user = kwargs.get('require_original_user', True)
        self.original_user: Optional[discord.User] = None
        self.value: Optional[bool] = None
        self.custom_labels = kwargs.get('custom_labels', {})
        # ボタンラベルのカスタマイズ
        self.confirm_label = self.custom_labels.get('confirm', "はい")
        self.cancel_label = self.custom_labels.get('cancel', "いいえ")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """確認ダイアログの操作権限チェック

        ・オリジナルユーザー以外の操作を拒否する
        """
        if self.require_original_user and interaction.user != self.original_user:
            await interaction.response.send_message("この操作は実行できません", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認ボタンの処理"""
        button.label = self.confirm_label
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """キャンセルボタンの処理"""
        button.label = self.cancel_label
        self.value = False
        await interaction.response.defer()
        self.stop()

    async def ask(self, ctx: EnhancedContext, message: str, **kwargs) -> Optional[bool]:
        """確認ダイアログを表示し、ユーザーの選択結果を返す"""
        self.original_user = ctx.author
        # ボタンラベルの再設定（必要な場合）
        self.confirm_button.label = self.confirm_label
        self.cancel_button.label = self.cancel_label
        embed = discord.Embed(
            description=f"❓ {message}",
            color=discord.Color.gold()
        )
        self.message = await ctx.send(embed=embed, view=self, **kwargs)
        await self.wait()
        try:
            if self.message:
                await self.message.edit(view=None)
        except discord.NotFound:
            pass
        return self.value


class TimeoutSelect(discord.ui.Select):
    """タイムアウト付きセレクトメニュー

    指定された選択肢からユーザーに選択させ、タイムアウトを設定する
    """
    def __init__(self, options: List[discord.SelectOption], placeholder: str = "選択してください...", **kwargs):
        min_values = kwargs.pop('min_values', 1)
        max_values = kwargs.pop('max_values', 1)
        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """ユーザー選択後の処理"""
        view = cast(InteractiveSelect, self.view)
        view.selected_value = self.values[0] if len(self.values) == 1 else self.values
        view.interaction = interaction
        view.stop()
        await interaction.response.defer()


class InteractiveSelect(EnhancedView):
    """インタラクティブな選択UI

    ユーザーに対して選択メニューを提示し、その結果を返す
    """
    def __init__(
        self, 
        options: List[discord.SelectOption], 
        placeholder: str = "選択してください...", 
        timeout: float = 30,
        **kwargs
    ):
        super().__init__(timeout=timeout)
        self.selected_value: Optional[Union[str, List[str]]] = None
        self.interaction: Optional[discord.Interaction] = None
        self.original_user: Optional[discord.User] = None
        self.require_original_user = kwargs.pop('require_original_user', True)
        self.add_item(TimeoutSelect(options, placeholder, **kwargs))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """選択UIの操作権限チェック"""
        if self.require_original_user and self.original_user and interaction.user != self.original_user:
            await interaction.response.send_message("この操作は実行できません", ephemeral=True)
            return False
        return True

    async def prompt(self, ctx: EnhancedContext, message: str, **kwargs) -> Optional[Union[str, List[str]]]:
        """選択メニューを表示し、結果を待機する"""
        self.original_user = ctx.author
        embed = discord.Embed(
            description=message,
            color=discord.Color.blue()
        )
        self.message = await ctx.send(embed=embed, view=self, **kwargs)
        await self.wait()
        try:
            if self.message:
                await self.message.edit(view=None)
        except discord.NotFound:
            pass
        return self.selected_value


class AdvancedSelect(EnhancedView):
    """拡張セレクトメニュー（ページネーション対応）

    ・選択肢が多い場合に複数ページでの表示をサポートする
    """
    def __init__(
        self,
        options: List[discord.SelectOption],
        *,
        page_size: int = 25,
        placeholder: str = "選択してください...",
        timeout: float = 30,
        **kwargs
    ):
        super().__init__(timeout=timeout)
        self.current_page = 0
        self.options = options
        self.page_size = page_size
        self.placeholder = placeholder
        self.selected_values = []
        self.original_user: Optional[discord.User] = None
        self.require_original_user = kwargs.pop('require_original_user', True)
        self._update_components()

    def _update_components(self):
        """内部処理：UIコンポーネント（選択メニューとページ切替ボタン）の更新"""
        self.clear_items()
        page_options = self._current_page_options()
        self.add_item(AdvancedSelectMenu(
            options=page_options,
            placeholder=self.placeholder,
            max_values=len(page_options)
        ))
        if len(self.options) > self.page_size:
            self._add_pagination_buttons()

    def _current_page_options(self) -> List[discord.SelectOption]:
        """内部処理：現在のページに表示する選択肢の抽出"""
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.options[start:end]

    def _add_pagination_buttons(self):
        """内部処理：ページ移動用のボタンを追加する"""
        self.add_item(PageButton(
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            callback=self._prev_page
        ))
        self.add_item(PageButton(
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            callback=self._next_page
        ))

    async def _prev_page(self, interaction: discord.Interaction):
        """内部処理：前のページへ移動する"""
        self.current_page = max(0, self.current_page - 1)
        self._update_components()
        await interaction.response.edit_message(view=self)

    async def _next_page(self, interaction: discord.Interaction):
        """内部処理：次のページへ移動する"""
        self.current_page = min((len(self.options) // self.page_size), self.current_page + 1)
        self._update_components()
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """選択UIの操作権限チェック"""
        if self.require_original_user and self.original_user and interaction.user != self.original_user:
            await interaction.response.send_message("この操作は実行できません", ephemeral=True)
            return False
        return True

    async def prompt(self, ctx: EnhancedContext, message: str, **kwargs) -> Optional[List[str]]:
        """選択メニューを表示し、選択結果を待機する"""
        self.original_user = ctx.author
        embed = discord.Embed(
            description=message,
            color=discord.Color.blue()
        )
        self.message = await ctx.send(embed=embed, view=self, **kwargs)
        await self.wait()
        try:
            if self.message:
                await self.message.edit(view=None)
        except discord.NotFound:
            pass
        return self.selected_values


class AdvancedSelectMenu(discord.ui.Select):
    """拡張セレクトメニュー用の内部クラス

    選択後に指定のコールバック処理を実行する
    """
    def __init__(self, *, callback=None, **kwargs):
        super().__init__(**kwargs)
        self._callback_func = callback

    async def callback(self, interaction: discord.Interaction):
        """ユーザー選択後の処理"""
        if self._callback_func:
            await self._callback_func(interaction, self.values)
        view = cast(AdvancedSelect, self.view)
        view.selected_values = self.values
        view.stop()
        await interaction.response.defer()


class PageButton(discord.ui.Button):
    """ページ移動用ボタン

    押下時に内部で設定されたコールバックを実行する
    """
    def __init__(self, *, callback=None, **kwargs):
        super().__init__(**kwargs)
        self._callback_func = callback

    async def callback(self, interaction: discord.Interaction):
        """ボタン押下時の処理"""
        if self._callback_func:
            await self._callback_func(interaction)


def log_execution(
    log_level: int = logging.INFO,
    with_args: bool = False,
    sensitive_keys: List[str] = None
) -> Callable:
    """Cog対応の実行ログデコレータ

    ・関数実行前後の情報（実行時間、引数、ユーザー情報など）をログ出力する
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # コマンド実行時のContext抽出（Cog対応）
            ctx = None
            for arg in args:
                if isinstance(arg, (commands.Context, EnhancedContext)):
                    ctx = arg
                    break
            # Interactionの場合はEnhancedContextを生成
            if not ctx:
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        ctx = await EnhancedContext.from_interaction(arg)
                        break

            log_data = {
                "command": func.__name__,
                "execution_time": 0.0
            }
            if ctx:
                log_data.update({
                    "user": f"{ctx.author} ({ctx.author.id})",
                    "channel": getattr(ctx.channel, 'name', 'DM'),
                    "guild": getattr(ctx.guild, 'name', 'None')
                })
            if with_args and ctx:
                args_data = {}
                for i, arg in enumerate(args[2:]):  # selfとctxを除外
                    args_data[f"arg_{i}"] = str(arg)
                for k, v in kwargs.items():
                    if sensitive_keys and k in sensitive_keys:
                        args_data[k] = "***"
                    else:
                        args_data[k] = str(v)
                log_data["args"] = args_data

            start_time = datetime.datetime.now(timezone.utc)
            try:
                result = await func(*args, **kwargs)
            except Exception as e:
                if ctx and ctx.bot:
                    ctx.bot.logger.log(log_level, log_data)
                raise
            finally:
                duration = (datetime.datetime.now(timezone.utc) - start_time).total_seconds()
                log_data["execution_time"] = duration
                if ctx and ctx.bot:
                    ctx.bot.logger.log(log_level, log_data)
            return result
        return wrapper
    return decorator
