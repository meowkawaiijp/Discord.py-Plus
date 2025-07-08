# Dispyplus: Discord APIイベントハンドラを実装するモジュール
# これらのハンドラは DispyplusBot によって内部的に使用され、
# カスタムイベントディスパッチなどの追加機能を提供します。
import discord
from discord.ext import commands
from typing import Union, TYPE_CHECKING

from .context import EnhancedContext # EnhancedContextのインポートパスを修正

if TYPE_CHECKING:
    from .Dispyplus import DispyplusBot


async def on_message_custom(bot: "DispyplusBot", message: discord.Message) -> None:
    """メッセージ受信時のイベントハンドラ。カスタムメッセージイベントも処理する。"""
    if message.author.bot and not bot.config.get("Bot", "process_bot_messages", fallback=False): # type: ignore
        return

    # カスタムメッセージイベントの処理
    ctx = await bot.get_context(message, cls=EnhancedContext)

    # on_message_contains
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("message_contains"):
        if predicate and predicate(message, bot.user):
            try:
                # Cogのメソッドとして呼び出すために、Cogインスタンスを取得
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, ctx, message)
                elif cog_instance is bot: # Bot直下のリスナー
                     await coro(bot, ctx, message) # 第1引数としてself (Botインスタンス) を渡す
                else: # 想定外のケース
                    bot.logger.warning(f"Executing listener {func_name} for message_contains with unknown context. Attempting to call directly.")
                    await coro(ctx, message)
            except Exception as e:
                bot.logger.error(f"Error in custom event 'message_contains' ({func_name}): {e}", exc_info=True)
                await ctx.error(f"メッセージイベント '{func_name}' の処理中にエラーが発生しました。")


    # on_message_matches
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("message_matches"):
        if predicate and predicate(message, bot.user):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, ctx, message)
                elif cog_instance is bot:
                    await coro(bot, ctx, message)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for message_matches with unknown context. Attempting to call directly.")
                    await coro(ctx, message)
            except Exception as e:
                bot.logger.error(f"Error in custom event 'message_matches' ({func_name}): {e}", exc_info=True)
                await ctx.error(f"メッセージイベント '{func_name}' の処理中にエラーが発生しました。")

    # 通常のコマンド処理
    if not message.author.bot or bot.config.get("Bot", "process_bot_commands", fallback=False): # type: ignore # type: ignore
        await bot.process_commands(message)


async def on_reaction_add_custom(bot: "DispyplusBot", reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> None:
    """リアクション追加時のイベントハンドラ。カスタムリアクションイベントも処理する。"""
    if user.bot and not bot.config.get("Bot", "process_bot_reactions", fallback=False): # type: ignore
        return

    ctx = await bot.get_context(reaction.message, cls=EnhancedContext)

    # on_reaction_add
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("reaction_add"):
        if predicate and predicate(reaction, user, bot.user):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, ctx, reaction, user)
                elif cog_instance is bot:
                    await coro(bot, ctx, reaction, user)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for reaction_add with unknown context. Attempting to call directly.")
                    await coro(ctx, reaction, user)
            except Exception as e:
                bot.logger.error(f"Error in custom event 'reaction_add' ({func_name}): {e}", exc_info=True)


async def on_reaction_remove_custom(bot: "DispyplusBot", reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> None:
    """リアクション削除時のイベントハンドラ。カスタムリアクションイベントも処理する。"""
    if user.bot and not bot.config.get("Bot", "process_bot_reactions", fallback=False): # type: ignore
        return

    ctx = await bot.get_context(reaction.message, cls=EnhancedContext)

    # on_reaction_remove
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("reaction_remove"):
        if predicate and predicate(reaction, user, bot.user):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, ctx, reaction, user)
                elif cog_instance is bot:
                    await coro(bot, ctx, reaction, user)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for reaction_remove with unknown context. Attempting to call directly.")
                    await coro(ctx, reaction, user)
            except Exception as e:
                bot.logger.error(f"Error in custom event 'reaction_remove' ({func_name}): {e}", exc_info=True)

async def on_typing_custom(bot: "DispyplusBot", channel: discord.TextChannel, user: Union[discord.User, discord.Member], when: discord.utils.utcnow) -> None:
    """タイピング開始時のイベントハンドラ。カスタムタイピングイベントも処理する。"""
    if user.bot and not bot.config.get("Bot", "process_bot_typing", fallback=False): # type: ignore
        return

    # on_typing_in
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("typing_in"):
        if predicate and predicate(channel, user, when):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, channel, user, when)
                elif cog_instance is bot:
                    await coro(bot, channel, user, when)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for typing_in with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'typing_in' ({func_name}): {e}", exc_info=True)

    # on_user_typing
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("user_typing"):
        if predicate and predicate(channel, user, when):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, channel, user, when)
                elif cog_instance is bot:
                    await coro(bot, channel, user, when)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for user_typing with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'user_typing' ({func_name}): {e}", exc_info=True)


async def on_voice_state_update_custom(bot: "DispyplusBot", member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
    """ボイスステート更新時のイベントハンドラ。カスタムボイスイベントも処理する。"""
    if member.bot and not bot.config.get("Bot", "process_bot_voice_state", fallback=False): # type: ignore
        return

    # on_user_voice_join
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("user_voice_join"):
        if predicate and predicate(member, before, after):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, member, after.channel)
                elif cog_instance is bot:
                    await coro(bot, member, after.channel)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for user_voice_join with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'user_voice_join' ({func_name}): {e}", exc_info=True)

    # on_user_voice_leave
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("user_voice_leave"):
        if predicate and predicate(member, before, after):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, member, before.channel)
                elif cog_instance is bot:
                    await coro(bot, member, before.channel)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for user_voice_leave with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'user_voice_leave' ({func_name}): {e}", exc_info=True)

    # on_user_voice_move
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("user_voice_move"):
        if predicate and predicate(member, before, after):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, member, before.channel, after.channel)
                elif cog_instance is bot:
                    await coro(bot, member, before.channel, after.channel)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for user_voice_move with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'user_voice_move' ({func_name}): {e}", exc_info=True)


async def on_member_update_custom(bot: "DispyplusBot", before: discord.Member, after: discord.Member) -> None:
    """メンバー更新時のイベントハンドラ。カスタムメンバー更新イベントも処理する。"""
    if after.bot and not bot.config.get("Bot", "process_bot_member_updates", fallback=False): # type: ignore
        return

    # Nickname update
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("member_nickname_update"):
        if predicate and predicate(before, after):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, after, before.nick, after.nick)
                elif cog_instance is bot:
                    await coro(bot, after, before.nick, after.nick)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for member_nickname_update with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'member_nickname_update' ({func_name}): {e}", exc_info=True)

    # Role add
    added_roles = set(after.roles) - set(before.roles)
    for role in added_roles:
        for predicate, coro, func_name in bot.custom_event_manager.get_listeners("member_role_add"):
            if predicate and predicate(before, after):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    target_added_role = role
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, after, target_added_role)
                    elif cog_instance is bot:
                        await coro(bot, after, target_added_role)
                    else:
                        bot.logger.warning(f"Executing listener {func_name} for member_role_add with unknown context.")
                except Exception as e:
                    bot.logger.error(f"Error in custom event 'member_role_add' for role {role.name} ({func_name}): {e}", exc_info=True)

    # Role remove
    removed_roles = set(before.roles) - set(after.roles)
    for role in removed_roles:
        for predicate, coro, func_name in bot.custom_event_manager.get_listeners("member_role_remove"):
            if predicate and predicate(before, after):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    target_removed_role = role
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, after, target_removed_role)
                    elif cog_instance is bot:
                        await coro(bot, after, target_removed_role)
                    else:
                        bot.logger.warning(f"Executing listener {func_name} for member_role_remove with unknown context.")
                except Exception as e:
                    bot.logger.error(f"Error in custom event 'member_role_remove' for role {role.name} ({func_name}): {e}", exc_info=True)

    # Status update
    if before.status != after.status:
        for predicate, coro, func_name in bot.custom_event_manager.get_listeners("member_status_update"):
            if predicate and predicate(before, after):
                try:
                    cog_instance = getattr(coro, '__self__', None)
                    if isinstance(cog_instance, commands.Cog):
                        await coro(cog_instance, after, before.status, after.status)
                    elif cog_instance is bot:
                        await coro(bot, after, before.status, after.status)
                    else:
                        bot.logger.warning(f"Executing listener {func_name} for member_status_update with unknown context.")
                except Exception as e:
                    bot.logger.error(f"Error in custom event 'member_status_update' ({func_name}): {e}", exc_info=True)


async def on_guild_update_custom(bot: "DispyplusBot", before: discord.Guild, after: discord.Guild) -> None:
    """サーバー更新時のイベントハンドラ。カスタムサーバー更新イベントも処理する。"""
    # Name change
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("guild_name_change"):
        if predicate and predicate(before, after):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    await coro(cog_instance, after, before.name, after.name)
                elif cog_instance is bot:
                    await coro(bot, after, before.name, after.name)
                else:
                    bot.logger.warning(f"Executing listener {func_name} for guild_name_change with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'guild_name_change' ({func_name}): {e}", exc_info=True)

    # Owner change
    for predicate, coro, func_name in bot.custom_event_manager.get_listeners("guild_owner_change"):
        if predicate and predicate(before, after):
            try:
                cog_instance = getattr(coro, '__self__', None)
                if isinstance(cog_instance, commands.Cog):
                    before_owner_obj = before.get_member(before.owner_id) or await bot.fetch_user(before.owner_id)
                    after_owner_obj = after.owner
                    if before_owner_obj and after_owner_obj:
                         await coro(cog_instance, after, before_owner_obj, after_owner_obj)
                    else:
                        bot.logger.warning(f"Could not fetch owner objects for guild_owner_change event on guild {after.id}")
                elif cog_instance is bot:
                    before_owner_obj = before.get_member(before.owner_id) or await bot.fetch_user(before.owner_id)
                    after_owner_obj = after.owner
                    if before_owner_obj and after_owner_obj:
                        await coro(bot, after, before_owner_obj, after_owner_obj)
                    else:
                         bot.logger.warning(f"Could not fetch owner objects for guild_owner_change event on guild {after.id} (bot-level listener)")
                else:
                    bot.logger.warning(f"Executing listener {func_name} for guild_owner_change with unknown context.")
            except Exception as e:
                bot.logger.error(f"Error in custom event 'guild_owner_change' ({func_name}): {e}", exc_info=True)

def register_event_handlers(bot: "DispyplusBot"):
    bot.on_message = lambda message: on_message_custom(bot, message)
    bot.on_reaction_add = lambda reaction, user: on_reaction_add_custom(bot, reaction, user)
    bot.on_reaction_remove = lambda reaction, user: on_reaction_remove_custom(bot, reaction, user)
    bot.on_typing = lambda channel, user, when: on_typing_custom(bot, channel, user, when)
    bot.on_voice_state_update = lambda member, before, after: on_voice_state_update_custom(bot, member, before, after)
    bot.on_member_update = lambda before, after: on_member_update_custom(bot, before, after)
    bot.on_guild_update = lambda before, after: on_guild_update_custom(bot, before, after)
    bot.logger.info("Custom event handlers registered.")
