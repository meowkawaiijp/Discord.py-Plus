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
  An extended Context class with additional utility methods (`.success()`, `.error()`, `.ask()`, `.paginate()`, `.interaction_type`, etc.).
- **Custom Event Decorators**
  Easily create handlers for specific events like message content, reactions, voice state changes, and more, using decorators (`@on_message_contains`, `@on_reaction_add`, etc.).
- **Webhook Utility**
  Simple helper method (`bot.send_webhook()` or `ctx.send_webhook()`) to send messages via webhooks.
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
Note: The directory name in the clone URL is `Discord.py-Plus`, but you might have it as `Discord.py-Enhanced` locally if you renamed it. Adjust `cd` command accordingly.

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure your bot
   - Rename `config.ini.example` to `config.ini`.
   - Edit `config.ini` and add your bot token under the `[Bot]` section:
     ```ini
     [Bot]
     token = YOUR_BOT_TOKEN_HERE
     prefix = !
     ```
   - Adjust other settings as needed.

4. Run the bot
   By default, you can run the main example which includes new features:
   ```bash
   python example/simple_example.py
   ```
   If you have a main `bot.py` (as referenced in older versions of this README), ensure it's updated or use the example.

## 💡 Basic Usage

The `example/simple_example.py` file in the repository has been significantly updated. This file now serves as a comprehensive guide for using the various features of Discord.py-Plus, including the newly added custom event decorators and utility functions.

**We highly recommend referring to the `example/simple_example.py` file for practical implementation details and runnable code.**

The `simple_example.py` file demonstrates:

*   **Initialization of `EnhancedBot`**: Shows how the `EnhancedBot` is set up, utilizing `ConfigManager` for loading settings from `config.ini` and configuring necessary Discord intents.
*   **Hybrid Commands**: The example includes the basic `ping` hybrid command and an improved `purge` hybrid command. The `purge` command now uses `ctx.ask()` for user confirmation before proceeding with message deletion, showcasing an interactive dialog.
*   **`ExampleCog`**: A sample Cog class is defined directly within `simple_example.py`. This Cog is loaded by the bot and provides clear examples of how to organize and use the new custom event decorators:
    *   **`@on_message_contains`**: A method decorated with this will trigger and respond when a message includes a specific substring (e.g., "hello example").
    *   **`@on_reaction_add`**: Another method acts when a particular emoji reaction (e.g., "👍") is added to a message.
    *   **`@on_user_voice_join`**: An example function logs or announces when a user joins any voice channel.
*   **Webhook Utility**: The `webhooktest` hybrid command demonstrates how to send messages, including rich embeds, to a specified webhook URL using the `ctx.send_webhook()` method. This is useful for sending formatted messages to channels without needing the bot to be a full member or to use specific bot permissions for sending.
*   **Interaction Type Detection**: The `invoketype` hybrid command shows how to use the `ctx.interaction_type` property (available in `EnhancedContext`) to determine if a command was invoked via a slash command, a message component (like a button press), or a traditional prefix-based message command.

**To run the updated example:**

1.  Ensure your `config.ini` file is correctly set up as described in the "Installation" section (especially your bot token).
2.  To fully test the `webhooktest` command, you will need a valid webhook URL from one of your Discord server's channels. You can pass this URL as an argument when you invoke the command.
3.  Open your terminal, navigate to the root directory of the repository, and run the example file using Python:
    ```bash
    python example/simple_example.py
    ```

This significantly expanded `simple_example.py` is intended to be a live demonstration and should be your primary resource for understanding how the new components work together and how you can integrate them into your own cogs and overall bot logic.

*For a detailed list of all available custom event decorators and their specific parameters (like `ignore_bot`, `case_sensitive`, `target_channel`, etc.), please consult the docstrings provided directly within the `core/custom_events.py` file.*

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
