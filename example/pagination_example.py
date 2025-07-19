import discord
from dispyplus import DispyplusBot, EnhancedContext
intents = discord.Intents.default()
intents.message_content = True

bot = DispyplusBot(command_prefix="!", intents=intents, config_path='config.ini')

@bot.hybrid_command(name="paginate")
async def paginate(ctx: EnhancedContext):
    data = [f"Item {i+1}" for i in range(20)]
    await ctx.paginate(data, items_per_page=5)

bot.run()
