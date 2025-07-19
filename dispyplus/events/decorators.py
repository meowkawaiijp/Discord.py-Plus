import re
import discord
from discord.ext import commands
from functools import wraps
from typing import Callable, Coroutine, Any, Optional, Union, Pattern, TYPE_CHECKING
import datetime
if TYPE_CHECKING:
    from ..core.context import EnhancedContext
EventPredicate = Callable[..., bool]
EventCoroutine = Callable[..., Coroutine[Any, Any, None]]

def _create_event_decorator(event_type: str, predicate_generator: Optional[Callable[..., EventPredicate]]=None):

    def decorator_factory(*args_deco, **kwargs_deco):

        def decorator(func: EventCoroutine) -> EventCoroutine:
            if not hasattr(func, '_custom_event_handlers'):
                func._custom_event_handlers = []
            handler_info = {'event_type': event_type, 'predicate_generator': predicate_generator, 'decorator_args': args_deco, 'decorator_kwargs': kwargs_deco}
            func._custom_event_handlers.append(handler_info)
            return func
        return decorator
    return decorator_factory

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
        raise ValueError(f'Invalid regex pattern for on_message_matches: {pattern} - {e}')

    def predicate(message: discord.Message, bot_user: Optional[discord.User]):
        if ignore_bot and message.author == bot_user:
            return False
        if message.content is None:
            return False
        return bool(compiled_pattern.search(message.content))
    return predicate

def _make_reaction_predicate(emoji: Union[str, discord.Emoji, discord.PartialEmoji], on_bot_message: bool, by_bot: bool):

    def predicate(reaction: discord.Reaction, user: Union[discord.Member, discord.User], bot_user: Optional[discord.User]):
        if not by_bot and user == bot_user:
            return False
        if not on_bot_message and reaction.message.author == bot_user:
            return False
        if isinstance(emoji, str):
            return str(reaction.emoji) == emoji
        elif isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            if isinstance(reaction.emoji, (discord.Emoji, discord.PartialEmoji)):
                return reaction.emoji.id == emoji.id
            return False
        return False
    return predicate

def _make_typing_in_predicate(target_channel: Union[discord.TextChannel, int], target_user: Optional[Union[discord.User, discord.Member, int]]=None):
    target_channel_id = target_channel.id if isinstance(target_channel, discord.TextChannel) else int(target_channel)
    target_user_id = None
    if target_user:
        target_user_id = target_user.id if isinstance(target_user, (discord.User, discord.Member)) else int(target_user)

    def predicate(channel: discord.abc.MessageableChannel, user: Union[discord.User, discord.Member], when: datetime.datetime):
        if not isinstance(channel, discord.TextChannel) or channel.id != target_channel_id:
            return False
        if target_user_id is not None and user.id != target_user_id:
            return False
        return True
    return predicate

def _make_user_typing_predicate(target_user: Union[discord.User, discord.Member, int], target_channel: Optional[Union[discord.TextChannel, int]]=None):
    target_user_id = target_user.id if isinstance(target_user, (discord.User, discord.Member)) else int(target_user)
    target_channel_id = None
    if target_channel:
        target_channel_id = target_channel.id if isinstance(target_channel, discord.TextChannel) else int(target_channel)

    def predicate(channel: discord.abc.MessageableChannel, user: Union[discord.User, discord.Member], when: datetime.datetime):
        if user.id != target_user_id:
            return False
        if target_channel_id is not None:
            if not isinstance(channel, discord.TextChannel) or channel.id != target_channel_id:
                return False
        return True
    return predicate

def _make_user_voice_join_predicate(target_channel: Optional[Union[discord.VoiceChannel, int]]=None):
    target_channel_id = target_channel.id if isinstance(target_channel, discord.VoiceChannel) else target_channel if target_channel else None

    def predicate(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is None and after.channel is not None:
            if target_channel_id is None or (after.channel and after.channel.id == target_channel_id):
                return True
        return False
    return predicate

def _make_user_voice_leave_predicate(target_channel: Optional[Union[discord.VoiceChannel, int]]=None):
    target_channel_id = target_channel.id if isinstance(target_channel, discord.VoiceChannel) else target_channel if target_channel else None

    def predicate(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is None:
            if target_channel_id is None or (before.channel and before.channel.id == target_channel_id):
                return True
        return False
    return predicate

def _make_user_voice_move_predicate(from_target_channel: Optional[Union[discord.VoiceChannel, int]]=None, to_target_channel: Optional[Union[discord.VoiceChannel, int]]=None):
    from_id = from_target_channel.id if isinstance(from_target_channel, discord.VoiceChannel) else from_target_channel
    to_id = to_target_channel.id if isinstance(to_target_channel, discord.VoiceChannel) else to_target_channel

    def predicate(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is not None and (before.channel.id != after.channel.id):
            if from_id is not None and before.channel.id != from_id:
                return False
            if to_id is not None and after.channel.id != to_id:
                return False
            return True
        return False
    return predicate

def _make_member_nickname_update_predicate(target_guild: Optional[Union[discord.Guild, int]]=None):
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild

    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False
        return before.nick != after.nick
    return predicate

def _make_member_role_add_predicate(target_role: Union[discord.Role, int], target_guild: Optional[Union[discord.Guild, int]]=None):
    target_role_id = target_role.id if isinstance(target_role, discord.Role) else target_role
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild

    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False
        added_roles = set(after.roles) - set(before.roles)
        return any((r.id == target_role_id for r in added_roles))
    return predicate

def _make_member_role_remove_predicate(target_role: Union[discord.Role, int], target_guild: Optional[Union[discord.Guild, int]]=None):
    target_role_id = target_role.id if isinstance(target_role, discord.Role) else target_role
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild

    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False
        removed_roles = set(before.roles) - set(after.roles)
        return any((r.id == target_role_id for r in removed_roles))
    return predicate

def _make_member_status_update_predicate(target_guild: Optional[Union[discord.Guild, int]]=None, target_status: Optional[discord.Status]=None):
    target_guild_id = target_guild.id if isinstance(target_guild, discord.Guild) else target_guild

    def predicate(before: discord.Member, after: discord.Member):
        if target_guild_id is not None and after.guild.id != target_guild_id:
            return False
        if before.status != after.status:
            if target_status is None or after.status == target_status:
                return True
        return False
    return predicate

def _make_guild_name_change_predicate():

    def predicate(before: discord.Guild, after: discord.Guild):
        return before.name != after.name
    return predicate

def _make_guild_owner_change_predicate():

    def predicate(before: discord.Guild, after: discord.Guild):
        return before.owner_id != after.owner_id
    return predicate
on_message_contains = _create_event_decorator('message_contains', _make_message_contains_predicate)
on_message_matches = _create_event_decorator('message_matches', _make_message_matches_predicate)
on_reaction_add = _create_event_decorator('reaction_add', _make_reaction_predicate)
on_reaction_remove = _create_event_decorator('reaction_remove', _make_reaction_predicate)
on_typing_in = _create_event_decorator('typing_in', _make_typing_in_predicate)
on_user_typing = _create_event_decorator('user_typing', _make_user_typing_predicate)
on_user_voice_join = _create_event_decorator('user_voice_join', _make_user_voice_join_predicate)
on_user_voice_leave = _create_event_decorator('user_voice_leave', _make_user_voice_leave_predicate)
on_user_voice_move = _create_event_decorator('user_voice_move', _make_user_voice_move_predicate)
on_member_nickname_update = _create_event_decorator('member_nickname_update', _make_member_nickname_update_predicate)
on_member_role_add = _create_event_decorator('member_role_add', _make_member_role_add_predicate)
on_member_role_remove = _create_event_decorator('member_role_remove', _make_member_role_remove_predicate)
on_member_status_update = _create_event_decorator('member_status_update', _make_member_status_update_predicate)
on_guild_name_change = _create_event_decorator('guild_name_change', _make_guild_name_change_predicate)
on_guild_owner_change = _create_event_decorator('guild_owner_change', _make_guild_owner_change_predicate)
on_config_reload = _create_event_decorator('config_reload')
'設定ファイルがリロードされた時に発火します。\nデコレートされる関数のシグネチャ:\n    `async def func(self)` (Cog内の場合)\n    `async def func()` (Bot直下の場合)\n    引数は取りません。\n'
__all__ = ['on_message_contains', 'on_message_matches', 'on_reaction_add', 'on_reaction_remove', 'on_typing_in', 'on_user_typing', 'on_user_voice_join', 'on_user_voice_leave', 'on_user_voice_move', 'on_member_nickname_update', 'on_member_role_add', 'on_member_role_remove', 'on_member_status_update', 'on_guild_name_change', 'on_guild_owner_change', 'on_config_reload', 'EventPredicate', 'EventCoroutine']
