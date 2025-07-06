# Dispyplus (Discord.py-Plus)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/dispyplus.svg)](https://badge.fury.io/py/dispyplus) <!-- PyPIに公開後有効化 -->
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[日本語](/README_JA.md)

Dispyplus is a Python library that provides several enhancements and utility features
for developing Discord bots with discord.py. It simplifies common tasks such as
configuration management, custom event handling, UI components like paginators and
confirmation dialogs, and more.

## 🚀 Key Features

- **Enhanced Bot Class (`DispyplusBot`)**:
    - Integrated configuration management (`ConfigManager`) with hot-reloading.
    - Automatic setup of logging.
    - Task scheduling capabilities.
    - Dynamic extension (Cog) loading.
    - Jishaku integration support.
- **Extended Context (`EnhancedContext`)**:
    - Utility methods for sending styled messages: `.success()`, `.error()`, `.warning()`, `.info()`.
    - Interactive dialogs: `.ask()` for confirmations.
    - Pagination: `.paginate()` using `Paginator` class.
    - Property to check interaction type: `.interaction_type`.
    - Helper to send webhooks: `.send_webhook()`.
- **Custom Event System**:
    - `CustomEventManager` to manage and dispatch custom event types.
    - Decorators for common Discord events with predicate-based filtering:
        - `@on_message_contains`: Triggers if message content includes a substring.
        - `@on_message_matches`: Triggers if message content matches a regex.
        - `@on_reaction_add` / `@on_reaction_remove`: For specific reactions.
        - `@on_typing_in` / `@on_user_typing`: For typing events in channels/by users.
        - `@on_user_voice_join` / `@on_user_voice_leave` / `@on_user_voice_move`: For voice state changes.
        - `@on_member_nickname_update`, `@on_member_role_add` / `@on_member_role_remove`, `@on_member_status_update`: For member updates.
        - `@on_guild_name_change`, `@on_guild_owner_change`: For guild updates.
- **Useful Decorators**:
    - `@permission_check`: Easily check for user permissions or roles.
    - `@log_execution`: Log command execution details.
- **UI Components**:
    - `EnhancedView`: Base view with built-in timeout handling and component disabling.
    - `Paginator`: For creating paginated embeds.
    - `ConfirmationView`: Simple Yes/No confirmation dialogs.
    - `InteractiveSelect`: Select menus that return user's choice.
    - `AdvancedSelect`: Select menus with pagination for many options.
- **Webhook Utility**:
  - `DispyplusBot.send_webhook()` and `EnhancedContext.send_webhook()` for easy webhook message sending.

## ⚙️ Installation

```bash
pip install git+https://github.com/meowkawaiijp/dispyplus.git
```

## 💡 Basic Usage

Here's a simple example of how to use `DispyplusBot` and some of its features:

```python
import asyncio
import discord
from discord.ext import commands # Import commands for Cog
from dispyplus import DispyplusBot, EnhancedContext, on_message_contains

# Initialize ConfigManager (optional, DispyplusBot handles it internally if config_path is given)
# config = ConfigManager('config.ini')

intents = discord.Intents.default()
intents.message_content = True # Required for message content related events/commands
intents.members = True       # Often useful for member related events

# Initialize the bot
# Provide the path to your config.ini file
bot = DispyplusBot(
    command_prefix="!",
    intents=intents,
    config_path='config.ini' # DispyplusBot will manage ConfigManager internally
)

# A simple hybrid command
@bot.hybrid_command(name="ping", description="Replies with Pong!")
async def ping(ctx: EnhancedContext):
    await ctx.success(f"Pong! Latency: {bot.latency*1000:.2f}ms")

# Using a custom event decorator (Recommended to be in a Cog)
@on_message_contains("hello bot", ignore_bot=True)
async def respond_to_hello(ctx: EnhancedContext, message: discord.Message):
    # This function is automatically registered due to the decorator.
    # The bot's on_message handler will dispatch to this if conditions are met.
    # Note: For this to work, the function must be part of a Cog that's added to the bot,
    # or defined in the main bot file where the DispyplusBot instance can find it during setup.
    # If this is in the main file, ensure the bot instance is defined before this.
    # For better organization, place event handlers in Cogs.
    await message.reply(f"Hello to you too, {message.author.mention}!")

# Example Cog (recommended for organizing commands and event handlers)
class MyCog(commands.Cog):
    def __init__(self, bot: DispyplusBot):
        self.bot = bot

    @commands.command()
    async def ask_test(self, ctx: EnhancedContext):
        confirm = await ctx.ask("Are you sure you want to do this?")
        if confirm:
            await ctx.send("You said yes!")
        elif confirm is False: # Explicitly False, not None (timeout)
            await ctx.send("You said no.")
        else:
            await ctx.send("You didn't answer in time.")

    @on_message_contains("magic word") # Custom event inside a Cog
    async def magic_handler(self, ctx: EnhancedContext, message: discord.Message):
        await message.channel.send("You said the magic word!")

async def main():
    # Make sure your config.ini has a 'Bot' section with a 'token'
    # Example config.ini:
    # [Bot]
    # token = YOUR_BOT_TOKEN
    # prefix = !
    #
    # [Logging]
    # level = INFO
    # file = bot.log

    # Add cogs
    await bot.add_cog(MyCog(bot))

    # Start the bot using the token from config.ini
    # The token is retrieved via bot.config.get('Bot', 'token')
    token = bot.config.get('Bot', 'token')
    if not token:
        print("Error: Bot token not found in config.ini.")
        return
    await bot.start(token)

if __name__ == "__main__":
    # Setup basic logging if you are not relying on DispyplusBot's logger for everything
    # discord.utils.setup_logging() # Or use your custom logging setup
    asyncio.run(main())
```

For more detailed examples, including all custom event decorators and UI components, please refer to the `example/simple_example.py` file in the repository.

## 🔧 Configuration (`config.ini`)

DispyplusBot uses a `config.ini` file for its settings. By default, it looks for `config.ini` in the current working directory.

A minimal `config.ini` would be:
```ini
[Bot]
token = YOUR_DISCORD_BOT_TOKEN_HERE
prefix = !

[Logging]
# Optional: Default is INFO
level = INFO
# Optional: Default is bot.log
file = my_bot.log
```

The `ConfigManager` supports hot-reloading. If you modify `config.ini` while the bot is running, changes can be picked up (e.g., for prefix, logging level, or custom configurations your bot uses). The bot dispatches an `on_config_reload` event when the configuration is reloaded.

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-new-feature`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-new-feature`
5. Open a Pull Request.

Please make sure to update tests as appropriate.

## 📜 License

Distributed under the MIT License. See the `LICENSE` file for details.
