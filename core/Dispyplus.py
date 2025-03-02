
import os
import asyncio
import logging
import datetime
from datetime import timezone
from pathlib import Path
from typing import Optional, Coroutine, Dict, TypeVar
from core.config import ConfigManager
from core.other import EnhancedContext
import discord
from discord.ext import commands
T = TypeVar('T')
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