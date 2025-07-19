import asyncio
import datetime
from datetime import timezone
from pathlib import Path
from typing import Optional, Coroutine, Dict, TypeVar, Callable, Any, Union, List
from .utils.config import ConfigManager
from .core.context import EnhancedContext
from .events.manager import CustomEventManager
from .utils.logging import setup_logger as setup_logger_util
from .services.tasks import schedule_task as schedule_task_util, cancel_task as cancel_task_util, get_task as get_task_util, get_all_tasks as get_all_tasks_util
from .services.webhook import send_webhook_message
from .utils.helpers import start_config_watcher as start_config_watcher_util
from .events.handlers import register_event_handlers
import discord
from discord.ext import commands
import inspect
T = TypeVar('T')
EventCoroutine = Callable[..., Coroutine[Any, Any, None]]
EventPredicate = Callable[..., bool]

class DispyplusBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        self.config_path = kwargs.pop('config_path', 'config.ini')
        super().__init__(*args, **kwargs)
        self.config = ConfigManager(self.config_path)
        self._task_registry: Dict[str, asyncio.Task] = {}
        self.logger = setup_logger_util(self.__class__.__name__, self.config)
        self.start_time = datetime.datetime.now(timezone.utc)
        self._config_watcher: Optional[asyncio.Task] = None
        self.extension_dir = Path(str(self.config.get('Extensions', 'directory', fallback='extensions')))
        self.custom_event_manager = CustomEventManager(self)
        register_event_handlers(self)

    async def setup_hook(self) -> None:
        """Bot起動前の初期化処理

        ・設定ファイルの変更監視
        ・カスタムイベントリスナーの登録
        ・自動拡張機能とJishakuの読み込み
        ・コマンドの同期
        """
        await start_config_watcher_util(self)
        await self._register_custom_event_listeners()
        if self.extension_dir.exists() and self.extension_dir.is_dir():
            for ext_file in self.extension_dir.glob('*.py'):
                if ext_file.stem.startswith('_'):
                    continue
                extension_name = f'{self.extension_dir.name}.{ext_file.stem}'
                try:
                    await self.load_extension(extension_name)
                    self.logger.info(f'Extension loaded: {extension_name}')
                except Exception as e:
                    self.logger.error(f'Failed to load extension {extension_name}: {e}', exc_info=True)
        if self.config.get('Extensions', 'jishaku', fallback=False):
            try:
                await self.load_extension('jishaku')
                self.logger.info('Jishaku extension loaded successfully')
            except Exception as e:
                self.logger.error(f'Failed to load jishaku: {str(e)}')
        sync_option = self.config.get('Commands', 'sync', fallback='global')
        try:
            if sync_option == 'global':
                await self.tree.sync()
                self.logger.info('Globally synced application commands')
            elif sync_option == 'none':
                self.logger.info('Command syncing disabled')
            else:
                guild_id = int(str(sync_option))
                await self.tree.sync(guild=discord.Object(id=guild_id))
                self.logger.info(f'Synced application commands to guild: {guild_id}')
        except Exception as e:
            self.logger.error(f'Command sync error: {e}', exc_info=True)

    def schedule_task(self, coro: Coroutine, *, name: str=None, interval: float=None, daily: bool=False, time: datetime.time=None) -> asyncio.Task:
        return schedule_task_util(self, coro, name=name, interval=interval, daily=daily, time=time)

    def cancel_task(self, name: str) -> bool:
        return cancel_task_util(self, name)

    def get_task(self, name: str) -> Optional[asyncio.Task]:
        return get_task_util(self, name)

    def get_all_tasks(self) -> Dict[str, asyncio.Task]:
        return get_all_tasks_util(self)

    async def close(self) -> None:
        """Botの終了処理を行い、全タスクをキャンセルする"""
        self.logger.info('Botシャットダウン中...')
        if self._config_watcher:
            self._config_watcher.cancel()
        for name in list(self._task_registry.keys()):
            self.cancel_task(name)
        await super().close()
        self.logger.info('Botは正常に終了しました')

    async def get_context(self, message, *, cls=None) -> EnhancedContext:
        context_class = cls if cls is not None else EnhancedContext
        return await super().get_context(message, cls=context_class)

    async def _register_custom_event_listeners(self):
        """
        Cog内のカスタムイベントデコレータが付与されたメソッドを探索し、
        CustomEventManagerにリスナーとして登録する。
        """
        self.logger.info('Registering custom event listeners...')
        for cog_name, cog in self.cogs.items():
            for member_name, member in inspect.getmembers(cog):
                if inspect.iscoroutinefunction(member) and hasattr(member, '_custom_event_handlers'):
                    handlers_info = getattr(member, '_custom_event_handlers', [])
                    for handler_info in handlers_info:
                        event_type = handler_info['event_type']
                        predicate_generator = handler_info['predicate_generator']
                        decorator_args = handler_info['decorator_args']
                        decorator_kwargs = handler_info['decorator_kwargs']
                        predicate: Optional[EventPredicate] = None
                        if predicate_generator:
                            try:
                                predicate = predicate_generator(*decorator_args, **decorator_kwargs)
                            except Exception as e:
                                self.logger.error(f'Error generating predicate for {member.__name__} in {cog_name} for event {event_type}: {e}', exc_info=True)
                                continue
                        self.custom_event_manager.add_listener(event_type, predicate, member, member.__name__)
                        self.logger.debug(f'Registered custom event: {event_type} - {cog_name}.{member.__name__}')
        for member_name, member in inspect.getmembers(self):
            if inspect.iscoroutinefunction(member) and hasattr(member, '_custom_event_handlers'):
                handlers_info = getattr(member, '_custom_event_handlers', [])
                for handler_info in handlers_info:
                    event_type = handler_info['event_type']
                    predicate_generator = handler_info['predicate_generator']
                    decorator_args = handler_info['decorator_args']
                    decorator_kwargs = handler_info['decorator_kwargs']
                    predicate: Optional[EventPredicate] = None
                    if predicate_generator:
                        try:
                            predicate = predicate_generator(*decorator_args, **decorator_kwargs)
                        except Exception as e:
                            self.logger.error(f'Error generating predicate for bot-level listener {member.__name__} for event {event_type}: {e}', exc_info=True)
                            continue
                    self.custom_event_manager.add_listener(event_type, predicate, member, f'bot.{member.__name__}')
                    self.logger.debug(f'Registered bot-level custom event: {event_type} - bot.{member.__name__}')
        self.logger.info('Custom event listeners registration complete.')

    async def send_webhook(self, url: str, content: Optional[str]=None, *, username: Optional[str]=None, avatar_url: Optional[str]=None, tts: bool=False, file: Optional[discord.File]=None, files: Optional[List[discord.File]]=None, embed: Optional[discord.Embed]=None, embeds: Optional[List[discord.Embed]]=None, allowed_mentions: Optional[discord.AllowedMentions]=None, wait: bool=False) -> Optional[discord.WebhookMessage]:
        return await send_webhook_message(self, url, content, username=username, avatar_url=avatar_url, tts=tts, file=file, files=files, embed=embed, embeds=embeds, allowed_mentions=allowed_mentions, wait=wait)
