# Discord.py Enhanced
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
git clone https://github.com/meowkawaiijp/Discord.py-Enhanced.git
cd Discord.py-Enhanced
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
import datetime
import discord
from discord.ext import commands
from Dispyplus import EnhancedBot, EnhancedContext, log_execution, ConfigManager

config = ConfigManager("config.ini")
intents = discord.Intents.all()
bot = EnhancedBot(
    command_prefix=config.get('Bot', 'prefix', fallback='!'),
    intents=intents,
    config=config
)

@bot.command()
@log_execution()
async def uptime(ctx: EnhancedContext):
    uptime_delta = datetime.datetime.now(datetime.timezone.utc) - ctx.bot.start_time
    hours, remainder = divmod(uptime_delta.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    await ctx.success(f"Uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s")

@bot.command()
async def userinfo(ctx: EnhancedContext, member: discord.Member):
    entries = [f"name: {member.name}", f"ID: {member.id}", ...]
    await ctx.paginate(entries, per_page=5)

async def main():
    await bot.start(config.get('Bot', 'token'))
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
