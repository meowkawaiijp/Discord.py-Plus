
import os
import asyncio
import logging
import datetime
from datetime import timezone
from pathlib import Path
from typing import Optional, Coroutine, Dict, TypeVar, List, Tuple, Callable, Any
from core.config import ConfigManager
from core.other import EnhancedContext
from core.custom_events import CustomEventManager # 追加
import discord
from discord.ext import commands
import inspect # 追加
import aiohttp # 追加

T = TypeVar('T')
EventCoroutine = Callable[..., Coroutine[Any, Any, None]] # 追加
EventPredicate = Callable[..., bool] # 追加
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
        self.config.get('Extensions', 'directory', fallback='extensions')
        self.extension_dir = Path(self.config.get('Extensions', 'directory', fallback='extensions'))
        self.custom_event_manager = CustomEventManager(self) # 追加

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
        ・カスタムイベントリスナーの登録
        ・自動拡張機能とJishakuの読み込み
        ・コマンドの同期
        """
        await self._start_config_watcher()
        await self._register_custom_event_listeners() # カスタムイベントリスナー登録処理の呼び出し

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
        if self.config.get('Extensions', 'jishaku', fallback=False): # type: ignore
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

    async def _register_custom_event_listeners(self):
        """
        Cog内のカスタムイベントデコレータが付与されたメソッドを探索し、
        CustomEventManagerにリスナーとして登録する。
        """
        self.logger.info("Registering custom event listeners...")
        for cog_name, cog in self.cogs.items():
            for member_name, member in inspect.getmembers(cog):
                if inspect.iscoroutinefunction(member) and hasattr(member, '_custom_event_handlers'):
                    handlers_info = getattr(member, '_custom_event_handlers', [])
                    for handler_info in handlers_info:
                        event_type = handler_info["event_type"]
                        predicate_generator = handler_info["predicate_generator"]
                        decorator_args = handler_info["decorator_args"]
                        decorator_kwargs = handler_info["decorator_kwargs"]

                        predicate: Optional[EventPredicate] = None
                        if predicate_generator:
                            try:
                                predicate = predicate_generator(*decorator_args, **decorator_kwargs)
                            except Exception as e:
                                self.logger.error(
                                    f"Error generating predicate for {member.__name__} in {cog_name} for event {event_type}: {e}",
                                    exc_info=True
                                )
                                continue

                        # ラップされたコルーチンをリスナーとして登録
                        # member はデコレートされた元のコルーチン関数
                        self.custom_event_manager.add_listener(event_type, predicate, member, member.__name__)
                        self.logger.debug(f"Registered custom event: {event_type} - {cog_name}.{member.__name__}")

        # Bot直下のリスナーも登録 (Cogに属さないリスナー)
        for member_name, member in inspect.getmembers(self):
            if inspect.iscoroutinefunction(member) and hasattr(member, '_custom_event_handlers'):
                # Bot直下のメソッドの場合、`self` はBotインスタンスそのもの
                # ただし、通常カスタムイベントはCog内で定義することを推奨
                handlers_info = getattr(member, '_custom_event_handlers', [])
                for handler_info in handlers_info:
                    event_type = handler_info["event_type"]
                    predicate_generator = handler_info["predicate_generator"]
                    decorator_args = handler_info["decorator_args"]
                    decorator_kwargs = handler_info["decorator_kwargs"]
                    predicate: Optional[EventPredicate] = None
                    if predicate_generator:
                        try:
                            predicate = predicate_generator(*decorator_args, **decorator_kwargs)
                        except Exception as e:
                            self.logger.error(
                                f"Error generating predicate for bot-level listener {member.__name__} for event {event_type}: {e}",
                                exc_info=True
                            )
                            continue
                    # Bot直下のリスナーの場合、coroの__self__はBotインスタンス自身になるか、あるいは存在しない
                    # 呼び出し側でCogインスタンスの有無を確認し、なければBotインスタンスを渡すか、引数なしで呼び出す
                    self.custom_event_manager.add_listener(event_type, predicate, member, f"bot.{member.__name__}")
                    self.logger.debug(f"Registered bot-level custom event: {event_type} - bot.{member.__name__}")
        self.logger.info("Custom event listeners registration complete.")


    async def on_message(self, message: discord.Message) -> None:
        """メッセージ受信時のイベントハンドラ。カスタムメッセージイベントも処理する。"""
        if message.author.bot and not self.config.get("Bot", "process_bot_messages", fallback=False): # type: ignore
            return

        # カスタムメッセージイベントの処理
        ctx = await self.get_context(message, cls=EnhancedContext)

        # on_message_contains
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("message_contains"):
            if predicate and predicate(message, self.user):
                try:
                    # Cogのメソッドとして呼び出すために、Cogインスタンスを取得
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, ctx, message)
                    elif cog_instance is self: # Bot直下のリスナー
                         await coro(self, ctx, message) # 第1引数としてself (Botインスタンス) を渡す
                    else: # 想定外のケース
                        self.logger.warning(f"Executing listener {func_name} for message_contains with unknown context. Attempting to call directly.")
                        await coro(ctx, message)
                except Exception as e:
                    self.logger.error(f"Error in custom event 'message_contains' ({func_name}): {e}", exc_info=True)
                    await ctx.error(f"メッセージイベント '{func_name}' の処理中にエラーが発生しました。")


        # on_message_matches
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("message_matches"):
            if predicate and predicate(message, self.user):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, ctx, message)
                    elif cog_instance is self:
                        await coro(self, ctx, message)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for message_matches with unknown context. Attempting to call directly.")
                        await coro(ctx, message)
                except Exception as e:
                    self.logger.error(f"Error in custom event 'message_matches' ({func_name}): {e}", exc_info=True)
                    await ctx.error(f"メッセージイベント '{func_name}' の処理中にエラーが発生しました。")

        # 通常のコマンド処理
        if not message.author.bot or self.config.get("Bot", "process_bot_commands", fallback=False): # type: ignore # type: ignore
            await self.process_commands(message)


    async def on_reaction_add(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> None:
        """リアクション追加時のイベントハンドラ。カスタムリアクションイベントも処理する。"""
        if user.bot and not self.config.get("Bot", "process_bot_reactions", fallback=False): # type: ignore
            return

        ctx = await self.get_context(reaction.message, cls=EnhancedContext)
        # EnhancedContextにリアクションユーザー情報を付与する方法を検討 (現状ctx.authorはメッセージ送信者)
        # reaction_add イベントの引数として user を渡すので、ctx経由でなくても良いかもしれない。

        # on_reaction_add
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("reaction_add"):
            if predicate and predicate(reaction, user, self.user):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, ctx, reaction, user)
                    elif cog_instance is self:
                        await coro(self, ctx, reaction, user)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for reaction_add with unknown context. Attempting to call directly.")
                        await coro(ctx, reaction, user)
                except Exception as e:
                    self.logger.error(f"Error in custom event 'reaction_add' ({func_name}): {e}", exc_info=True)
                    # エラーをユーザーに通知するかは検討 (リアクションイベントでは難しい場合も)

    async def on_reaction_remove(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> None:
        """リアクション削除時のイベントハンドラ。カスタムリアクションイベントも処理する。"""
        if user.bot and not self.config.get("Bot", "process_bot_reactions", fallback=False): # type: ignore
            return

        ctx = await self.get_context(reaction.message, cls=EnhancedContext)

        # on_reaction_remove
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("reaction_remove"):
            if predicate and predicate(reaction, user, self.user):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, ctx, reaction, user)
                    elif cog_instance is self:
                        await coro(self, ctx, reaction, user)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for reaction_remove with unknown context. Attempting to call directly.")
                        await coro(ctx, reaction, user)
                except Exception as e:
                    self.logger.error(f"Error in custom event 'reaction_remove' ({func_name}): {e}", exc_info=True)

    async def on_typing(self, channel: discord.TextChannel, user: Union[discord.User, discord.Member], when: datetime.datetime) -> None:
        """タイピング開始時のイベントハンドラ。カスタムタイピングイベントも処理する。"""
        if user.bot and not self.config.get("Bot", "process_bot_typing", fallback=False): # type: ignore
            return

        # EnhancedContext をどうするか。メッセージがないので通常のContextは作りにくい。
        # ダミーのメッセージオブジェクトを作るか、あるいはイベントハンドラにはctxを渡さない設計にするか。
        # ここでは、ctxは必須とせず、必要な情報(channel, user, when)を直接渡す。
        # もしctxが必要な場合は、Botインスタンス(self)から限定的な情報を取得する。
        # → カスタムイベントの呼び出しシグネチャを (self, channel, user, when) に統一する。
        #   Cogのメソッドであれば第一引数はCogインスタンス。

        # on_typing_in
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("typing_in"):
            if predicate and predicate(channel, user, when):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, channel, user, when)
                    elif cog_instance is self:
                        await coro(self, channel, user, when)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for typing_in with unknown context.")
                        # このケースでは引数構成が不明瞭なため呼び出しをスキップするか、限定的な引数で試みる
                        # await coro(channel, user, when) # 引数が合わない可能性
                except Exception as e:
                    self.logger.error(f"Error in custom event 'typing_in' ({func_name}): {e}", exc_info=True)

        # on_user_typing
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("user_typing"):
            if predicate and predicate(channel, user, when):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, channel, user, when)
                    elif cog_instance is self:
                        await coro(self, channel, user, when)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for user_typing with unknown context.")
                except Exception as e:
                    self.logger.error(f"Error in custom event 'user_typing' ({func_name}): {e}", exc_info=True)


    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """ボイスステート更新時のイベントハンドラ。カスタムボイスイベントも処理する。"""
        if member.bot and not self.config.get("Bot", "process_bot_voice_state", fallback=False): # type: ignore
            return

        # ctxは同様に生成が難しい。member, before, after を渡す。

        # on_user_voice_join
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("user_voice_join"):
            if predicate and predicate(member, before, after): # predicate は True/False を返す
                # 述語がTrueなら、それは「参加」イベントに合致したということ
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, member, after.channel) # 参加チャンネルを渡す
                    elif cog_instance is self:
                        await coro(self, member, after.channel)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for user_voice_join with unknown context.")
                except Exception as e:
                    self.logger.error(f"Error in custom event 'user_voice_join' ({func_name}): {e}", exc_info=True)

        # on_user_voice_leave
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("user_voice_leave"):
            if predicate and predicate(member, before, after): # 退出イベントに合致
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, member, before.channel) # 退出したチャンネルを渡す
                    elif cog_instance is self:
                        await coro(self, member, before.channel)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for user_voice_leave with unknown context.")
                except Exception as e:
                    self.logger.error(f"Error in custom event 'user_voice_leave' ({func_name}): {e}", exc_info=True)

        # on_user_voice_move
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("user_voice_move"):
            if predicate and predicate(member, before, after): # 移動イベントに合致
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, member, before.channel, after.channel) # 移動前後のチャンネルを渡す
                    elif cog_instance is self:
                        await coro(self, member, before.channel, after.channel)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for user_voice_move with unknown context.")
                except Exception as e:
                    self.logger.error(f"Error in custom event 'user_voice_move' ({func_name}): {e}", exc_info=True)


    async def send_webhook(
        self,
        url: str,
        content: Optional[str] = None,
        *,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
        tts: bool = False,
        file: Optional[discord.File] = None,
        files: Optional[List[discord.File]] = None,
        embed: Optional[discord.Embed] = None,
        embeds: Optional[List[discord.Embed]] = None,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        wait: bool = False
    ) -> Optional[discord.WebhookMessage]:
        """
        指定されたWebhook URLにメッセージを送信します。

        Args:
            url: WebhookのURL。
            content: 送信するメッセージの本文。
            username: Webhook投稿者名として使用する名前。
            avatar_url: Webhook投稿者のアバターURL。
            tts: メッセージをTTSで読み上げるか。
            file: 送信する単一ファイル。
            files: 送信する複数ファイル (file引数とは併用不可)。
            embed: 送信する単一Embed。
            embeds: 送信する複数Embed (embed引数とは併用不可)。
            allowed_mentions: メッセージのメンション設定。
            wait: Webhookからの応答を待つか (メッセージオブジェクトを取得する場合True)。

        Returns:
            wait=Trueの場合、送信された discord.WebhookMessage。それ以外はNone。

        Raises:
            discord.HTTPException: Webhookの実行に失敗した場合。
            ValueError: fileとfilesが同時に指定された場合、またはembedとembedsが同時に指定された場合。
        """
        if file and files:
            raise ValueError("Cannot mix file and files keyword arguments.")
        if embed and embeds:
            raise ValueError("Cannot mix embed and embeds keyword arguments.")

        # discord.pyのWebhookオブジェクトを利用して送信
        # セッション管理は discord.py 内部で行われるため、自前で aiohttp.ClientSession を作る必要は薄い
        # (discord.Webhook.from_url に session を渡すことも可能)
        async with aiohttp.ClientSession() as session: # discord.pyのWebhookは内部でセッションを扱うが、明示的に渡すことも可能
            webhook = discord.Webhook.from_url(url, session=session)
            try:
                # files と file の処理
                actual_files: List[discord.File] = []
                if files:
                    actual_files.extend(files)
                if file:
                    actual_files.append(file)

                # embeds と embed の処理
                actual_embeds: List[discord.Embed] = []
                if embeds:
                    actual_embeds.extend(embeds)
                if embed:
                    actual_embeds.append(embed)

                # discord.py 3.0以降では、files引数は存在しない。代わりに send メソッドの file/files を使う。
                # Webhook.send は file と files を両方取ることはできない (discord.py の File オブジェクトのリストを期待するのは files のみ)
                # しかし、私たちのシグネチャでは両方許容しているので、ここで調整する。
                # ひとまず、discord.pyのWebhook.sendのシグネチャに合わせる。
                # username, avatar_url, tts, file, files, embed, embeds, allowed_mentions, wait

                # discord.py の Webhook.send は file と files を同時に取れない。
                # ここでは files が優先されるようにする (もし両方指定されたら)。
                # file と files が両方ある場合はエラーにしているので、片方だけが存在するはず。

                final_file: Optional[discord.File] = None
                final_files: Optional[List[discord.File]] = None

                if actual_files:
                    if len(actual_files) == 1 and not files: # file引数で単一ファイルが来た場合
                        final_file = actual_files[0]
                    else: # files引数で複数ファイルが来たか、file引数でもfilesとして扱いたい場合
                        final_files = actual_files

                # username と avatar_url は webhook オブジェクトの属性ではなく、sendメソッドの引数
                sent_message = await webhook.send(
                    content=content,
                    username=username or self.user.name if self.user else None, # Bot名フォールバック
                    avatar_url=avatar_url or self.user.display_avatar.url if self.user else None, # Botアバターフォールバック
                    tts=tts,
                    file=final_file, # 単一ファイルの場合
                    files=final_files, # 複数ファイルの場合
                    embed=embed, # 単一Embed
                    embeds=embeds, # 複数Embed (discord.pyのWebhook.sendはembedsを取る)
                    allowed_mentions=allowed_mentions or self.allowed_mentions, # Botのデフォルト設定をフォールバック
                    wait=wait
                )
                return sent_message
            except discord.HTTPException as e:
                self.logger.error(f"Webhook send failed to {url}: {e}", exc_info=True)
                raise
            except ValueError as e: # file/files, embed/embeds の重複など
                self.logger.error(f"Webhook parameter error: {e}", exc_info=True)
                raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred during webhook send to {url}: {e}", exc_info=True)
                raise

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """メンバー更新時のイベントハンドラ。カスタムメンバー更新イベントも処理する。"""
        if after.bot and not self.config.get("Bot", "process_bot_member_updates", fallback=False): # type: ignore
            return

        # Nickname update
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("member_nickname_update"):
            if predicate and predicate(before, after):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, after, before.nick, after.nick)
                    elif cog_instance is self:
                        await coro(self, after, before.nick, after.nick)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for member_nickname_update with unknown context.")
                except Exception as e:
                    self.logger.error(f"Error in custom event 'member_nickname_update' ({func_name}): {e}", exc_info=True)

        # Role add
        added_roles = set(after.roles) - set(before.roles)
        for role in added_roles:
            for predicate, coro, func_name in self.custom_event_manager.get_listeners("member_role_add"):
                # 述語ジェネレータ側でロールIDのチェックは行われているので、ここでは単純に呼び出す
                # ただし、述語自体がロールオブジェクトを引数に取るように変更した場合は、ここでロールを渡す必要がある。
                # 現状の _make_member_role_add_predicate は target_role をクロージャで保持している。
                if predicate and predicate(before, after): # predicate は before, after を見て特定のロールが追加されたか判断
                    try:
                        cog_instance = getattr(coro, '__self__', None)
                        # 述語がTrueを返した場合、その述語が監視していた特定のロールが追加されたことを意味する
                        # そのため、coro に渡すのは、追加されたロールのうち、述語が関心を持つロール
                        # しかし、現在の述語の作りでは、どのロールでTrueになったか特定できない。
                        # predicate_generator が target_role を知っているので、predicate 側で完全なチェックを行う。
                        # -> predicate が True を返せば、その coro はその target_role に関するもの。

                        # どのロールが追加されたかを知るために、coro に渡すロールは述語が True を返した原因のロールであるべき。
                        # 述語(_make_member_role_add_predicate)は特定の target_role に対して True/False を返す。
                        # なので、ここで再度どのロールが追加されたかを確認し、述語が対象としたロールを coro に渡す。
                        # listener登録時に target_role_id を保持しておき、ここで比較する方が良いかもしれない。
                        # または、述語が (before, after, role_to_check) を取るようにする。
                        # 現状の _custom_event_handlers の構造では、デコレータの引数(target_role)は predicate_generator に渡されるだけ。
                        # 呼び出し時にどのロールがトリガーになったかをcoroに伝えるには、predicateがその情報を返すか、
                        # あるいは、ここで再度ループしてチェックする必要がある。
                        #
                        # シンプルにするため、述語がTrueを返したなら、そのデコレータで指定されたロールが追加されたとみなし、
                        # そのロールオブジェクトを渡す。そのためには、述語がどのロールでTrueになったかを知る必要がある。
                        #
                        # 修正案：predicate_generator が返す predicate が (before, after) を受け取り、
                        # マッチしたロールオブジェクトを返すか、Noneを返すようにする。
                        # そして、ここでそのロールオブジェクトを使う。
                        #
                        # もっと簡単なのは、coro のシグネチャを (self, member, added_role) とし、
                        # predicate が True を返した時点で、その predicate に紐づく target_role が追加されたと判断し、
                        # その target_role のオブジェクトを渡す。
                        # そのためには、add_listener 時に target_role の情報を保持する必要がある。
                        #
                        # 現状の predicate は (before, after) のみ。
                        # `predicate_generator(*decorator_args, **decorator_kwargs)` で生成されている。
                        # `decorator_args` に `target_role` が入っている。
                        # 述語がTrueを返したので、このリスナーの対象。追加されたロールは `role`。
                        target_added_role = role
                        if isinstance(cog_instance, commands.Cog):
                            await coro(cog_instance, after, target_added_role)
                        elif cog_instance is self:
                            await coro(self, after, target_added_role)
                        else:
                            self.logger.warning(f"Executing listener {func_name} for member_role_add with unknown context.")
                    except Exception as e:
                        self.logger.error(f"Error in custom event 'member_role_add' for role {role.name} ({func_name}): {e}", exc_info=True)

        # Role remove
        removed_roles = set(before.roles) - set(after.roles)
        for role in removed_roles:
            for predicate, coro, func_name in self.custom_event_manager.get_listeners("member_role_remove"):
                # 述語は decorator_args にある target_role に基づいて評価される
                if predicate and predicate(before, after):
                    try:
                        cog_instance = getattr(coro, '__self__', None)
                        target_removed_role = role
                        if isinstance(cog_instance, commands.Cog):
                            await coro(cog_instance, after, target_removed_role)
                        elif cog_instance is self:
                            await coro(self, after, target_removed_role)
                        else:
                            self.logger.warning(f"Executing listener {func_name} for member_role_remove with unknown context.")
                    except Exception as e:
                        self.logger.error(f"Error in custom event 'member_role_remove' for role {role.name} ({func_name}): {e}", exc_info=True)

        # Status update
        if before.status != after.status:
            for predicate, coro, func_name in self.custom_event_manager.get_listeners("member_status_update"):
                if predicate and predicate(before, after):
                    try:
                        cog_instance = getattr(coro, '__self__', None)
                        if isinstance(cog_instance, commands.Cog):
                            await coro(cog_instance, after, before.status, after.status)
                        elif cog_instance is self:
                            await coro(self, after, before.status, after.status)
                        else:
                            self.logger.warning(f"Executing listener {func_name} for member_status_update with unknown context.")
                    except Exception as e:
                        self.logger.error(f"Error in custom event 'member_status_update' ({func_name}): {e}", exc_info=True)

    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        """サーバー更新時のイベントハンドラ。カスタムサーバー更新イベントも処理する。"""
        # Name change
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("guild_name_change"):
            if predicate and predicate(before, after):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, after, before.name, after.name)
                    elif cog_instance is self:
                        await coro(self, after, before.name, after.name)
                    else:
                        self.logger.warning(f"Executing listener {func_name} for guild_name_change with unknown context.")
                except Exception as e:
                    self.logger.error(f"Error in custom event 'guild_name_change' ({func_name}): {e}", exc_info=True)

        # Owner change
        for predicate, coro, func_name in self.custom_event_manager.get_listeners("guild_owner_change"):
            if predicate and predicate(before, after):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        # after.owner は Member | User | None, before.owner も同様だが古い情報かもしれないのでIDから取得推奨
                        # ただし、on_guild_update の時点では after.owner は最新のはず
                        before_owner_obj = before.get_member(before.owner_id) or await self.fetch_user(before.owner_id)
                        after_owner_obj = after.owner # これは最新のはず
                        if before_owner_obj and after_owner_obj:
                             await coro(cog_instance, after, before_owner_obj, after_owner_obj)
                        else:
                            self.logger.warning(f"Could not fetch owner objects for guild_owner_change event on guild {after.id}")
                    elif cog_instance is self:
                        before_owner_obj = before.get_member(before.owner_id) or await self.fetch_user(before.owner_id)
                        after_owner_obj = after.owner
                        if before_owner_obj and after_owner_obj:
                            await coro(self, after, before_owner_obj, after_owner_obj)
                        else:
                             self.logger.warning(f"Could not fetch owner objects for guild_owner_change event on guild {after.id} (bot-level listener)")
                    else:
                        self.logger.warning(f"Executing listener {func_name} for guild_owner_change with unknown context.")
                except Exception as e:
                    self.logger.error(f"Error in custom event 'guild_owner_change' ({func_name}): {e}", exc_info=True)