import logging
from dispyplus import DispyplusBot,ConfigManager
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

intents = discord.Intents.default()
intents.message_content = True

bot = DispyplusBot(command_prefix="!", intents=intents, config_path='config.ini')

@bot.hybrid_command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

bot.run()