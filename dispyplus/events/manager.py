# Dispyplus: カスタムイベントの登録と管理を行う CustomEventManager を提供するモジュール
from typing import Callable, Coroutine, Dict, List, Tuple, Optional, Any, TYPE_CHECKING
import asyncio # asyncio をインポート

if TYPE_CHECKING:
    from ..bot import DispyplusBot #循環参照を避ける
    from .decorators import EventPredicate, EventCoroutine # event_decoratorsから型をインポート

class CustomEventManager:
    """
    カスタムイベントの登録と管理を行うクラス。
    Botインスタンスごとにイベントリスナーを保持します。
    """
    def __init__(self, bot: 'DispyplusBot'):
        self.bot = bot
        # {event_type: [(predicate, coroutine, original_func_name), ...]}
        self._listeners: Dict[str, List[Tuple[Optional['EventPredicate'], 'EventCoroutine', str]]] = {
            "message_contains": [],
            "message_matches": [],
            "reaction_add": [],
            "reaction_remove": [],
            "typing_in": [],
            "user_typing": [],
            "user_voice_join": [],
            "user_voice_leave": [],
            "user_voice_move": [],
            "member_nickname_update": [],
            "member_role_add": [],
            "member_role_remove": [],
            "member_status_update": [],
            "guild_name_change": [],
            "guild_owner_change": [],
            # config_reload イベントも管理対象にするか検討
            "config_reload": [],
        }

    def add_listener(self, event_type: str, predicate: Optional['EventPredicate'], coro: 'EventCoroutine', func_name: str):
        """イベントリスナーを追加する"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append((predicate, coro, func_name))
        if hasattr(self.bot, 'logger'): # loggerの存在を確認
            self.bot.logger.debug(f"Custom event listener added for '{event_type}': {func_name}")

    def get_listeners(self, event_type: str) -> List[Tuple[Optional['EventPredicate'], 'EventCoroutine', str]]:
        """指定されたイベントタイプのリスナーを取得する"""
        return self._listeners.get(event_type, [])

    def dispatch(self, event_type: str, *args: Any, **kwargs: Any) -> None:
        """
        登録されたカスタムイベントリスナーにイベントを発火させます。
        Botの `dispatch` とは独立しており、CustomEventManagerが管理するイベント専用です。
        """
        # このメソッドは現状 DispyplusBot.dispatch('config_reload') のように直接呼ばれる想定
        # 将来的には、より多くのカスタムイベントタイプで汎用的に使えるように拡張可能
        if hasattr(self.bot, 'logger'):
            self.bot.logger.debug(f"Dispatching custom event '{event_type}' with args: {args}, kwargs: {kwargs}")

        listeners = self.get_listeners(event_type)
        for predicate, coro, func_name in listeners:
            # config_reload のような単純なイベントでは predicate は通常 None
            if predicate is None or predicate(*args, **kwargs): #述語がある場合は評価
                # Botインスタンスからコルーチンを実行
                # asyncio.create_task を使用してノンブロッキングで実行
                asyncio.create_task(self._safe_execute_listener(coro, func_name, event_type, *args, **kwargs))


    async def _safe_execute_listener(self, coro: 'EventCoroutine', func_name: str, event_type: str, *args: Any, **kwargs: Any):
        """リスナーコルーチンを安全に実行する内部メソッド"""
        try:
            # CogのメソッドかBot直下のメソッドかで呼び出し方を調整する必要があるかもしれない
            # 現在の add_listener の使われ方では、coro は Cog のメソッドまたは Bot のメソッドそのもの
            # inspect.iscoroutinefunction(coro) でコルーチン関数であることは保証されている
            # getattr(coro, '__self__', None) でインスタンスを取得できる
            instance = getattr(coro, '__self__', None)
            if instance: # CogまたはBotのメソッドの場合
                await coro(*args, **kwargs) # インスタンスメソッドとして呼び出し
            else: # 静的メソッドや通常の関数の場合（通常は考えにくいが念のため）
                await coro(*args, **kwargs)

        except Exception as e:
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error(f"Error in custom event listener '{func_name}' for event '{event_type}': {e}", exc_info=True)

# 型エイリアスは event_decorators.py に移動するため、ここでは削除
# EventPredicate = Callable[..., bool]
# EventCoroutine = Callable[..., Coroutine[Any, Any, None]]
