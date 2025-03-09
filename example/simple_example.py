import asyncio
import logging
from core.Dispyplus import EnhancedBot
from core.config import ConfigManager
from core.decorators import log_execution, permission_check
from core.other import EnhancedContext
import discord
from discord.ext import commands
from discord import app_commands
import discord
CONFIG_FILE = 'config.ini'

config = ConfigManager(CONFIG_FILE)

logging.basicConfig(
    level=config.get('Logging', 'level', fallback='INFO'),
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    handlers=[
        logging.FileHandler(
            filename=config.get('Logging', 'file', fallback='bot.log'),
            encoding='utf-8', mode='a'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = EnhancedBot(
    command_prefix=config.get('Bot', 'prefix', fallback='!'),
    intents=intents,
    config=config
)

@bot.hybrid_command(name="ping", description="pong")
@log_execution()
async def ping(ctx: EnhancedContext):
    await ctx.success(f"pong")

@commands.hybrid_command(name="purge")
@app_commands.describe(limit="削除するメッセージ数")
@permission_check(permissions=['manage_messages'])
async def purge_messages(
        ctx: EnhancedContext,
        limit: int = 10
    ):
        """メッセージを一括削除します"""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        confirm = await ctx.ask(f"本当に直近 {limit}件 のメッセージを削除しますか？")
        if not confirm:
            return
        
        try:
            deleted = await ctx.channel.purge(limit=limit + 1)
            await ctx.success(f"{len(deleted)-1}件のメッセージを削除しました", delete_after=5)
        except discord.Forbidden:
            await ctx.error("権限が不足しています")
async def main():
    await bot.start(config.get('Bot', 'token'))

if __name__ == "__main__":
    asyncio.run(main())