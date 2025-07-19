from typing import Callable, Coroutine, Dict, List, Tuple, Optional, Any, TYPE_CHECKING
import asyncio
if TYPE_CHECKING:
    from ..bot import DispyplusBot
    from .decorators import EventPredicate, EventCoroutine

class CustomEventManager:

    def __init__(self, bot: 'DispyplusBot'):
        self.bot = bot
        self._listeners: Dict[str, List[Tuple[Optional['EventPredicate'], 'EventCoroutine', str]]] = {'message_contains': [], 'message_matches': [], 'reaction_add': [], 'reaction_remove': [], 'typing_in': [], 'user_typing': [], 'user_voice_join': [], 'user_voice_leave': [], 'user_voice_move': [], 'member_nickname_update': [], 'member_role_add': [], 'member_role_remove': [], 'member_status_update': [], 'guild_name_change': [], 'guild_owner_change': [], 'config_reload': []}

    def add_listener(self, event_type: str, predicate: Optional['EventPredicate'], coro: 'EventCoroutine', func_name: str):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append((predicate, coro, func_name))
        if hasattr(self.bot, 'logger'):
            self.bot.logger.debug(f"Custom event listener added for '{event_type}': {func_name}")

    def get_listeners(self, event_type: str) -> List[Tuple[Optional['EventPredicate'], 'EventCoroutine', str]]:
        return self._listeners.get(event_type, [])

    def dispatch(self, event_type: str, *args: Any, **kwargs: Any) -> None:
        if hasattr(self.bot, 'logger'):
            self.bot.logger.debug(f"Dispatching custom event '{event_type}' with args: {args}, kwargs: {kwargs}")
        listeners = self.get_listeners(event_type)
        for predicate, coro, func_name in listeners:
            if predicate is None or predicate(*args, **kwargs):
                asyncio.create_task(self._safe_execute_listener(coro, func_name, event_type, *args, **kwargs))

    async def _safe_execute_listener(self, coro: 'EventCoroutine', func_name: str, event_type: str, *args: Any, **kwargs: Any):
        """リスナーコルーチンを安全に実行する内部メソッド"""
        try:
            instance = getattr(coro, '__self__', None)
            if instance:
                await coro(*args, **kwargs)
            else:
                await coro(*args, **kwargs)
        except Exception as e:
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error(f"Error in custom event listener '{func_name}' for event '{event_type}': {e}", exc_info=True)
