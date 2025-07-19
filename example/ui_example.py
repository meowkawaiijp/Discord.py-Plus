import discord
from dispyplus import DispyplusBot, EnhancedContext
intents = discord.Intents.default()
intents.message_content = True

bot = DispyplusBot(command_prefix="!", intents=intents, config_path='config.ini')

@bot.hybrid_command(name="confirm")
async def confirm(ctx: EnhancedContext):
    result = await ctx.ask("本当に実行しますか？")
    if result:
        await ctx.send("はいが選択されました。")
    elif result is False:
        await ctx.send("いいえが選択されました。")
    else:
        await ctx.send("タイムアウトしました。")

bot.run()
