# Discord.py-Plus
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[日本語](/README_JA.md)

An enhanced framework for Discord.py with advanced features.

## 🚀 Key Features

- **Smart Pagination**  
  Interactive page management for large datasets.
- **Interactive Dialogs**  
  Built-in confirmation dialogs and dynamic selection menus.
- **Task Scheduler**  
  Flexible scheduling of recurring tasks with custom timing.
- **Extended Context**  
  An extended Context class with additional utility methods.
- **Configuration Management**  
  .ini-based hot-reloadable configuration system.
- **Extension System**  
  Dynamic Cog loading with Jishaku integration.

## ⚙️ Installation

1. Clone the repository
```bash
git clone https://github.com/meowkawaiijp/Discord.py-Plus.git
cd Discord.py-Plus
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Run the bot
```bash
python bot.py
```

## 💡 Basic Usage

```python
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
@app_commands.describe(limit="delete message limit")
@permission_check(permissions=['manage_messages'])
async def purge_messages(
        ctx: EnhancedContext,
        limit: int = 10
    ):
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        confirm = await ctx.ask(f"{limit}n oky?")
        if not confirm:
            return
        
        try:
            deleted = await ctx.channel.purge(limit=limit + 1)
            await ctx.success(f"{len(deleted)-1}n deleted.", delete_after=5)
        except discord.Forbidden:
            await ctx.error("permission error")
async def main():
    await bot.start(config.get('Bot', 'token'))

if __name__ == "__main__":
    asyncio.run(main())
```

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch  
   `git checkout -b feature/new-feature`
3. Commit your changes  
   `git commit -m 'Add new feature'`
4. Push the branch  
   `git push origin feature/new-feature`
5. Create a pull request.

## 📜 License

Distributed under the MIT License. See the `LICENSE` file for details.
