"""
カスタムイベントデコレータを管理するモジュールです。
EnhancedBot と連携し、特定の条件に基づいたイベント処理を簡潔に記述できるようにします。

このモジュール内のデコレータを使用することで、Botのイベント処理をより宣言的に記述できます。
各デコレータは、Cogクラス内のメソッドまたはEnhancedBotクラス自身のメソッドに適用できます。

使用例 (Cog内):
```python
from core.custom_events import on_message_contains
from core.other import EnhancedContext
from discord.ext import commands
import discord

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @on_message_contains("hello", ignore_bot=True)
    async def say_hello(self, ctx: EnhancedContext, message: discord.Message):
        await message.channel.send(f"Hello {message.author.mention}!")

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```
"""
import asyncio
import re
from functools import wraps
from typing import Callable, Coroutine, Dict, List, Tuple, Union, Pattern, Any, Optional
import discord
from discord.ext import commands

from .other import EnhancedContext # EnhancedContextをインポート

# 型エイリアス
EventPredicate = Callable[..., bool]
EventCoroutine = Callable[..., Coroutine[Any, Any, None]]

class CustomEventManager:
    """
    カスタムイベントの登録と管理を行うクラス。
    Botインスタンスごとにイベントリスナーを保持します。
    """
    def __init__(self, bot: 'EnhancedBot'):
        self.bot = bot
        # {event_type: [(predicate, coroutine, original_func_name), ...]}
        self._listeners: Dict[str, List[Tuple[Optional[EventPredicate], EventCoroutine, str]]] = {
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
        }

    def add_listener(self, event_type: str, predicate: Optional[EventPredicate], coro: EventCoroutine, func_name: str):
        """イベントリスナーを追加する"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append((predicate, coro, func_name))
        self.bot.logger.debug(f"Custom event listener added for '{event_type}': {func_name}")

    def get_listeners(self, event_type: str) -> List[Tuple[Optional[EventPredicate], EventCoroutine, str]]:
        """指定されたイベントタイプのリスナーを取得する"""
        return self._listeners.get(event_type, [])

# --- デコレータファクトリ ---

def _create_event_decorator(event_type: str, predicate_generator: Optional[Callable[..., EventPredicate]] = None):
    """汎用的なイベントデコレータを作成するファクトリ関数"""
    def decorator_factory(*args_deco, **kwargs_deco):
        def decorator(func: EventCoroutine) -> EventCoroutine:
            @wraps(func)
            async def wrapper(ctx_or_bot, *args_event, **kwargs_event): # BotインスタンスまたはContextを受け取る想定
                # 実際の処理はBot側のイベントハンドラで行う
                # ここではデコレータとして関数を登録する役割に注力
                # Botインスタンスを取得する必要がある
                if isinstance(ctx_or_bot, commands.Cog):
                    bot_instance = ctx_or_bot.bot
                elif hasattr(ctx_or_bot, 'bot'): # EnhancedContextの場合
                    bot_instance = ctx_or_bot.bot
                elif isinstance(ctx_or_bot, commands.Bot): # EnhancedBotの場合
                    bot_instance = ctx_or_bot
                else:
                    # 予期しないケース。本来はBot起動時にCog経由で登録される
                    # print(f"Warning: Could not determine bot instance for {func.__name__}")
                    # この場合、登録がうまくいかない可能性がある
                    # logging.warning(f"Could not determine bot instance for {func.__name__}")
                    return await func(ctx_or_bot, *args_event, **kwargs_event) # 通常の関数として実行を試みる

                # EnhancedBotのカスタムイベントマネージャに登録
                if hasattr(bot_instance, 'custom_event_manager'):
                    predicate = predicate_generator(*args_deco, **kwargs_deco) if predicate_generator else None
                    bot_instance.custom_event_manager.add_listener(event_type, predicate, func, func.__name__)
                else:
                    # print(f"Warning: Bot instance {bot_instance} does not have custom_event_manager.")
                    # logging.warning(f"Bot instance {bot_instance} does not have custom_event_manager.")
                    pass # 登録できない場合は何もしないか、エラーを出す

                # デコレータは元の関数を返す（Bot起動時に収集されるため）
                return func
            return wrapper # wrapperを返すことで、BotがCogをロードする際にこのwrapperがコマンドとして登録されることを防ぐ
                           # 代わりに、Bot側でこれらのデコレータが付いた関数を別途収集・管理する。
                           # いや、デコレータの目的はBotのイベントシステムにフックすることなので、
                           # Botのセットアップ時にこれらの関数が適切にBotのカスタムイベントマネージャに登録されるようにする必要がある。
                           # そのため、wrapperではなく、元の関数 `func` に属性でもつけて、Bot側でそれを探すか、
                           # あるいは、デコレータが適用された時点でBotインスタンスのどこかに登録する。
                           # ここでは `EnhancedBot` に `custom_event_manager` がある前提でそこに登録する。
                           # ただし、デコレータが評価される時点ではBotインスタンスが確定していない場合があるため、
                           # Cogのロード時などにBotインスタンスを渡して登録処理を行う必要がある。
                           #
                           # 一旦、BotのセットアップフックでCog内のデコレートされた関数を探索し、
                           # `custom_event_manager` に登録する方式を考える。
                           # その場合、デコレータは関数に目印（属性）を付けるだけでよい。

            # デコレータが関数に目印を付ける方式
            # setattr(func, f'_custom_event_{event_type}', True)
            # setattr(func, f'_custom_event_args_{event_type}', (args_deco, kwargs_deco))
            # return func

            # やはり、デコレータ適用時に直接登録する方がシンプルかもしれない。
            # ただし、Botインスタンスへのアクセス方法が課題。
            # グローバルなBotインスタンスや、`discord.ext.commands.Bot.get_bot()` のようなものがあれば良いが、
            # 通常はCogのコンストラクタでBotインスタンスを受け取る。
            #
            # 解決策：
            # 1. デコレータは関数に属性を設定するだけ。
            # 2. EnhancedBotの `add_cog` をオーバーライドし、Cog内の関数をスキャンして、
            #    属性を持つ関数を `custom_event_manager` に登録する。
            # これが最もクリーンな方法と思われる。

            # 上記の解決策を実装する
            if not hasattr(func, '_custom_event_handlers'):
                func._custom_event_handlers = []

            # predicate_generator が None の場合（単純なイベント登録）と、
            # predicate_generator がある場合（条件付きイベント登録）を考慮
            if predicate_generator:
                 # predicate_generator に渡す引数はデコレータの引数
                func._custom_event_handlers.append({
                    "event_type": event_type,
                    "predicate_generator": predicate_generator,
                    "decorator_args": args_deco,
                    "decorator_kwargs": kwargs_deco
                })
            else:
                # predicate_generator がない場合は、引数なしで呼び出すか、None を設定
                 func._custom_event_handlers.append({
                    "event_type": event_type,
                    "predicate_generator": None, # 条件なし
                    "decorator_args": args_deco, # デコレータ自身の引数は保持
                    "decorator_kwargs": kwargs_deco
                })
            return func
        return decorator

    return decorator_factory

# --- メッセージイベント用述語ジェネレータ ---
def _make_message_contains_predicate(substring: str, ignore_bot: bool, case_sensitive: bool):
    def predicate(message: discord.Message, bot_user: Optional[discord.User]):
        if ignore_bot and message.author == bot_user:
            return False
        if message.content is None:
            return False
        content_to_check = message.content if case_sensitive else message.content.lower()
        sub_to_check = substring if case_sensitive else substring.lower()
        return sub_to_check in content_to_check
    return predicate

def _make_message_matches_predicate(pattern: str, ignore_bot: bool, case_sensitive: bool):
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled_pattern = re.compile(pattern, flags)
    except re.error as e:
        # Bot起動時のエラーとしてログに出力したい
        raise ValueError(f"Invalid regex pattern provided to on_message_matches: {pattern} - {e}")

    def predicate(message: discord.Message, bot_user: Optional[discord.User]):
        if ignore_bot and message.author == bot_user:
            return False
        if message.content is None:
            return False
        return bool(compiled_pattern.search(message.content))
    return predicate

# --- リアクションイベント用述語ジェネレータ ---
def _make_reaction_predicate(emoji: Union[str, discord.Emoji, discord.PartialEmoji], on_bot_message: bool, by_bot: bool):
    def predicate(reaction: discord.Reaction, user: Union[discord.Member, discord.User], bot_user: Optional[discord.User]):
        if not by_bot and user == bot_user: # Bot自身のリアクションは無視 (by_bot=False の場合)
            return False
        if not on_bot_message and reaction.message.author == bot_user: # Botのメッセージへのリアクションは無視 (on_bot_message=False の場合)
            return False

        # 絵文字の比較
        # reaction.emoji は str か Emoji オブジェクト
        # 引数の emoji も str か Emoji オブジェクト
        if isinstance(emoji, str): # ユニコード絵文字の場合
            return str(reaction.emoji) == emoji
        elif isinstance(emoji, (discord.Emoji, discord.PartialEmoji)): # カスタム絵文字の場合
            if isinstance(reaction.emoji, discord.Emoji): # reaction.emoji もカスタム絵文字
                return reaction.emoji.id == emoji.id
            elif isinstance(reaction.emoji, discord.PartialEmoji):
                 return reaction.emoji.id == emoji.id and reaction.emoji.name == emoji.name # name も比較
            else: # reaction.emoji がユニコード絵文字の場合、一致しない
                return False
        return False # 不明な emoji 型
    return predicate

# --- Typingイベント用述語ジェネレータ ---
def _make_typing_in_predicate(target_channel: Union[discord.TextChannel, int], target_user: Optional[Union[discord.User, int]] = None):
    target_channel_id = target_channel.id if isinstance(target_channel, discord.TextChannel) else target_channel
    target_user_id = target_user.id if isinstance(target_user, discord.User) else target_user

    def predicate(channel: discord.TextChannel, user: Union[discord.User, discord.Member], when: datetime.datetime):
        if channel.id != target_channel_id:
            return False
        if target_user_id is not None and user.id != target_user_id:
            return False
        return True
    return predicate

def _make_user_typing_predicate(target_user: Union[discord.User, int], target_channel: Optional[Union[discord.TextChannel, int]] = None):
    target_user_id = target_user.id if isinstance(target_user, discord.User) else target_user
    target_channel_id = target_channel.id if isinstance(target_channel, discord.TextChannel) else target_channel if target_channel else None

    def predicate(channel: discord.TextChannel, user: Union[discord.User, discord.Member], when: datetime.datetime):
        if user.id != target_user_id:
            return False
        if target_channel_id is not None and channel.id != target_channel_id:
            return False
        return True
    return predicate


# --- Voice State イベント用述語ジェネレータ ---
def _make_user_voice_join_predicate(target_channel: Optional[Union[discord.VoiceChannel, int]] = None):
    target_channel_id = target_channel.id if isinstance(target_channel, discord.VoiceChannel) else target_channel if target_channel else None
    def predicate(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is None and after.channel is not None: # 参加
            if target_channel_id is None or after.channel.id == target_channel_id:
                return True
        return False
    return predicate

def _make_user_voice_leave_predicate(target_channel: Optional[Union[discord.VoiceChannel, int]] = None):
    target_channel_id = target_channel.id if isinstance(target_channel, discord.VoiceChannel) else target_channel if target_channel else None
    def predicate(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is None: # 退出
            if target_channel_id is None or before.channel.id == target_channel_id:
                return True
        return False
    return predicate

def _make_user_voice_move_predicate(
    from_target_channel: Optional[Union[discord.VoiceChannel, int]] = None,
    to_target_channel: Optional[Union[discord.VoiceChannel, int]] = None
):
    from_target_channel_id = from_target_channel.id if isinstance(from_target_channel, discord.VoiceChannel) else from_target_channel if from_target_channel else None
    to_target_channel_id = to_target_channel.id if isinstance(to_target_channel, discord.VoiceChannel) else to_target_channel if to_target_channel else None

    def predicate(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is not None and before.channel != after.channel: # 移動
            if from_target_channel_id is not None and before.channel.id != from_target_channel_id:
                return False
            if to_target_channel_id is not None and after.channel.id != to_target_channel_id:
                return False
            return True
        return False
    return predicate

# --- Member Update イベント用述語ジェネレータ ---
def _make_member_nickname_update_predicate(target_guild: Optional[Union[discord.Guild, int]] = None):
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild if target_guild else None
    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False
        return before.nick != after.nick
    return predicate

def _make_member_role_add_predicate(target_role: Union[discord.Role, int], target_guild: Optional[Union[discord.Guild, int]] = None):
    target_role_id = target_role.id if isinstance(target_role, discord.Role) else target_role
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild if target_guild else None

    # target_role_id はデコレータの引数から取得する
    # predicate_generator の引数として渡ってくる target_role を使う
    actual_target_role_id = target_role.id if isinstance(target_role, discord.Role) else target_role

    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False

        # 実際にどのロールが追加されたかを確認し、それが監視対象のロールであればTrue
        current_target_role_id = actual_target_role_id # クロージャで保持

        if current_target_role_id not in [r.id for r in before.roles] and \
           current_target_role_id in [r.id for r in after.roles]:
            return True
        return False
    return predicate

def _make_member_role_remove_predicate(target_role: Union[discord.Role, int], target_guild: Optional[Union[discord.Guild, int]] = None):
    target_role_id = target_role.id if isinstance(target_role, discord.Role) else target_role
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild if target_guild else None

    actual_target_role_id = target_role_id # クロージャで保持

    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False

        current_target_role_id = actual_target_role_id

        if current_target_role_id in [r.id for r in before.roles] and \
           current_target_role_id not in [r.id for r in after.roles]:
            return True
        return False
    return predicate

def _make_member_status_update_predicate(target_guild: Optional[Union[discord.Guild, int]] = None, target_status: Optional[discord.Status] = None):
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild if target_guild else None
    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False
        if before.status != after.status:
            if target_status is None or after.status == target_status:
                return True
        return False
    return predicate

# --- Guild Update イベント用述語ジェネレータ ---
def _make_guild_name_change_predicate():
    def predicate(before: discord.Guild, after: discord.Guild):
        return before.name != after.name
    return predicate

def _make_guild_owner_change_predicate():
    def predicate(before: discord.Guild, after: discord.Guild):
        return before.owner_id != after.owner_id
    return predicate


# --- デコレータ定義 ---
on_message_contains = _create_event_decorator(
    "message_contains",
    _make_message_contains_predicate
)
"""メッセージ内容に指定した部分文字列が含まれている場合に発火します。

Args:
    substring (str): 検索する部分文字列。
    ignore_bot (bool, optional): Botからのメッセージを無視するかどうか。デフォルトは True。
    case_sensitive (bool, optional): 大文字小文字を区別するかどうか。デフォルトは False。

デコレートされる関数のシグネチャ:
    `async def func(self, ctx: EnhancedContext, message: discord.Message)`
    (Cog内の場合、第一引数は `self` (Cogインスタンス))
"""

on_message_matches = _create_event_decorator(
    "message_matches",
    _make_message_matches_predicate
)
"""メッセージ内容が指定した正規表現パターンにマッチする場合に発火します。

Args:
    pattern (str): マッチさせる正規表現パターン。
    ignore_bot (bool, optional): Botからのメッセージを無視するかどうか。デフォルトは True。
    case_sensitive (bool, optional): 大文字小文字を区別するかどうか。正規表現フラグ re.IGNORECASE に影響。デフォルトは False。

デコレートされる関数のシグネチャ:
    `async def func(self, ctx: EnhancedContext, message: discord.Message)`
"""

on_reaction_add = _create_event_decorator(
    "reaction_add",
    _make_reaction_predicate
)
"""メッセージに特定のリアクションが追加された場合に発火します。

Args:
    emoji (Union[str, discord.Emoji, discord.PartialEmoji]): 対象の絵文字。
    on_bot_message (bool, optional): Bot自身のメッセージへのリアクションも検知するかどうか。デフォルトは False。
    by_bot (bool, optional): Botによるリアクションも検知対象とするか。デフォルトは False。

デコレートされる関数のシグネチャ:
    `async def func(self, ctx: EnhancedContext, reaction: discord.Reaction, user: Union[discord.Member, discord.User])`
"""

on_reaction_remove = _create_event_decorator(
    "reaction_remove",
    _make_reaction_predicate
)
"""メッセージから特定のリアクションが削除された場合に発火します。

Args:
    emoji (Union[str, discord.Emoji, discord.PartialEmoji]): 対象の絵文字。
    on_bot_message (bool, optional): Bot自身のメッセージへのリアクションも検知するかどうか。デフォルトは False。
    by_bot (bool, optional): Botによるリアクションも検知対象とするか。デフォルトは False。

デコレートされる関数のシグネチャ:
    `async def func(self, ctx: EnhancedContext, reaction: discord.Reaction, user: Union[discord.Member, discord.User])`
"""

on_typing_in = _create_event_decorator(
    "typing_in",
    _make_typing_in_predicate
)
"""指定されたチャンネルで、オプションで指定されたユーザーがタイピングを開始した時に発火します。

Args:
    target_channel (Union[discord.TextChannel, int]): タイピングを監視するチャンネルまたはチャンネルID。
    target_user (Optional[Union[discord.User, int]], optional): 特定のユーザーのタイピングのみを監視する場合に指定。デフォルトは None (全ユーザー)。

デコレートされる関数のシグネチャ:
    `async def func(self, channel: discord.TextChannel, user: Union[discord.User, discord.Member], when: datetime.datetime)`
"""

on_user_typing = _create_event_decorator(
    "user_typing",
    _make_user_typing_predicate
)
"""指定されたユーザーが、オプションで指定されたチャンネルでタイピングを開始した時に発火します。

Args:
    target_user (Union[discord.User, int]): タイピングを監視するユーザーまたはユーザーID。
    target_channel (Optional[Union[discord.TextChannel, int]], optional): 特定のチャンネルでのタイピングのみを監視する場合に指定。デフォルトは None (全チャンネル)。

デコレートされる関数のシグネチャ:
    `async def func(self, channel: discord.TextChannel, user: Union[discord.User, discord.Member], when: datetime.datetime)`
"""

on_user_voice_join = _create_event_decorator(
    "user_voice_join",
    _make_user_voice_join_predicate
)
"""ユーザーがボイスチャンネルに参加した時に発火します。オプションで特定のチャンネルを指定できます。

Args:
    target_channel (Optional[Union[discord.VoiceChannel, int]], optional): 特定のボイスチャンネルへの参加のみを監視する場合に指定。デフォルトは None (全ボイスチャンネル)。

デコレートされる関数のシグネチャ:
    `async def func(self, member: discord.Member, channel: discord.VoiceChannel)`
"""

on_user_voice_leave = _create_event_decorator(
    "user_voice_leave",
    _make_user_voice_leave_predicate
)
"""ユーザーがボイスチャンネルから退出した時に発火します。オプションで特定のチャンネルを指定できます。

Args:
    target_channel (Optional[Union[discord.VoiceChannel, int]], optional): 特定のボイスチャンネルからの退出のみを監視する場合に指定。デフォルトは None (全ボイスチャンネル)。

デコレートされる関数のシグネチャ:
    `async def func(self, member: discord.Member, channel: discord.VoiceChannel)`
"""

on_user_voice_move = _create_event_decorator(
    "user_voice_move",
    _make_user_voice_move_predicate
)
"""ユーザーがボイスチャンネル間を移動した時に発火します。オプションで移動元・移動先のチャンネルを指定できます。

Args:
    from_target_channel (Optional[Union[discord.VoiceChannel, int]], optional): 移動元のチャンネルを指定。デフォルトは None。
    to_target_channel (Optional[Union[discord.VoiceChannel, int]], optional): 移動先のチャンネルを指定。デフォルトは None。

デコレートされる関数のシグネチャ:
    `async def func(self, member: discord.Member, before_channel: discord.VoiceChannel, after_channel: discord.VoiceChannel)`
"""

on_member_nickname_update = _create_event_decorator(
    "member_nickname_update",
    _make_member_nickname_update_predicate
)
"""メンバーのニックネームが変更された時に発火します。オプションで特定のサーバーを指定できます。

Args:
    target_guild (Optional[Union[discord.Guild, int]], optional): 特定のサーバーのメンバーのみを監視する場合に指定。デフォルトは None (全サーバー)。

デコレートされる関数のシグネチャ:
    `async def func(self, member: discord.Member, before_nick: Optional[str], after_nick: Optional[str])`
"""

on_member_role_add = _create_event_decorator(
    "member_role_add",
    _make_member_role_add_predicate
)
"""メンバーに特定のロールが付与された時に発火します。オプションで特定のサーバーを指定できます。

Args:
    target_role (Union[discord.Role, int]): 対象のロールまたはロールID。
    target_guild (Optional[Union[discord.Guild, int]], optional): 特定のサーバーのメンバーのみを監視する場合に指定。デフォルトは None。

デコレートされる関数のシグネチャ:
    `async def func(self, member: discord.Member, added_role: discord.Role)`
"""

on_member_role_remove = _create_event_decorator(
    "member_role_remove",
    _make_member_role_remove_predicate
)
"""メンバーから特定のロールが剥奪された時に発火します。オプションで特定のサーバーを指定できます。

Args:
    target_role (Union[discord.Role, int]): 対象のロールまたはロールID。
    target_guild (Optional[Union[discord.Guild, int]], optional): 特定のサーバーのメンバーのみを監視する場合に指定。デフォルトは None。

デコレートされる関数のシグネチャ:
    `async def func(self, member: discord.Member, removed_role: discord.Role)`
"""

on_member_status_update = _create_event_decorator(
    "member_status_update",
    _make_member_status_update_predicate
)
"""メンバーのステータス (オンライン, オフライン等) が変更された時に発火します。
オプションで特定のサーバーや変更後のステータスを指定できます。

Args:
    target_guild (Optional[Union[discord.Guild, int]], optional): 特定のサーバーのメンバーのみを監視する場合に指定。デフォルトは None。
    target_status (Optional[discord.Status], optional): このステータスになった時のみ発火。デフォルトは None (全てのステータス変更)。

デコレートされる関数のシグネチャ:
    `async def func(self, member: discord.Member, before_status: discord.Status, after_status: discord.Status)`
"""

on_guild_name_change = _create_event_decorator(
    "guild_name_change",
    _make_guild_name_change_predicate
)
"""サーバーの名前が変更された時に発火します。

デコレートされる関数のシグネチャ:
    `async def func(self, guild: discord.Guild, before_name: str, after_name: str)`
"""

on_guild_owner_change = _create_event_decorator(
    "guild_owner_change",
    _make_guild_owner_change_predicate
)
"""サーバーの所有者が変更された時に発火します。

デコレートされる関数のシグネチャ:
    `async def func(self, guild: discord.Guild, before_owner: Union[discord.User, discord.Member], after_owner: Union[discord.User, discord.Member])`
"""

# EnhancedBot の型ヒントのため (循環参照を避ける)
if False:
    from .Dispyplus import EnhancedBot
