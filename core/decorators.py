
import logging
import datetime
from datetime import timezone
from functools import wraps
from typing import List, Callable, TypeVar
from core.view import EnhancedContext
import discord
from discord.ext import commands
T = TypeVar('T')
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
