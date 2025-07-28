"""
Basic Discord bot example using dispyplus library.

This example demonstrates:
- Configuration management
- Custom event handling
- UI components (paginator, confirmation dialog)
- Forms with validation
- Utility functions
"""

import discord
from discord.ext import commands
import asyncio
from datetime import datetime

# Import dispyplus components
from dispyplus import (
    ConfigManager, EventHandler, Paginator, ConfirmDialog, EmbedPaginator,
    Form, FormField, Validators, Transformers,
    get_user_avatar, format_timestamp, safe_send, create_embed
)


class ExampleBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            description='Example bot using dispyplus'
        )
        
        # Initialize configuration
        self.config = ConfigManager("config.json")
        self.config.load()
        
        # Set default configuration values
        if not self.config.has('bot.prefix'):
            self.config.set('bot.prefix', '!')
        if not self.config.has('bot.name'):
            self.config.set('bot.name', 'DispyPlus Bot')
        
        # Initialize custom event handler
        self.event_handler = EventHandler(self)
        
        # Setup custom events
        self.setup_custom_events()
    
    def setup_custom_events(self):
        """Setup custom event listeners."""
        
        @self.event_handler.listen('user_join_server')
        async def on_user_join(event, member):
            """Handle custom user join event."""
            channel = member.guild.system_channel
            if channel:
                embed = create_embed(
                    title="Welcome!",
                    description=f"Welcome {member.mention} to {member.guild.name}!",
                    color=discord.Color.green(),
                    author=member,
                    timestamp=datetime.utcnow()
                )
                await safe_send(channel, embed=embed)
    
    async def on_ready(self):
        """Bot ready event."""
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guilds')
        
        # Dispatch custom event
        await self.event_handler.dispatch('bot_ready', bot=self)
    
    async def on_member_join(self, member):
        """Member join event - dispatch custom event."""
        await self.event_handler.dispatch('user_join_server', member)


# Create bot instance
bot = ExampleBot()


@bot.slash_command(name="config", description="Manage bot configuration")
async def config_command(ctx, action: str, key: str = None, value: str = None):
    """Configuration management command."""
    if action == "get":
        if key:
            config_value = bot.config.get(key, "Not found")
            await ctx.respond(f"**{key}**: `{config_value}`")
        else:
            await ctx.respond("Please provide a configuration key to get.")
    
    elif action == "set":
        if key and value:
            bot.config.set(key, value)
            bot.config.save()
            await ctx.respond(f"Set **{key}** to `{value}`")
        else:
            await ctx.respond("Please provide both key and value to set.")
    
    else:
        await ctx.respond("Available actions: `get`, `set`")


@bot.slash_command(name="paginator", description="Demonstrate paginator functionality")
async def paginator_command(ctx):
    """Demonstrate paginator with multiple pages."""
    
    # Create sample pages
    pages = [
        "This is page 1 of the paginator example.\nYou can navigate using the buttons below.",
        "This is page 2.\nPaginators are great for displaying large amounts of content.",
        "This is page 3.\nThey automatically handle navigation and timeouts.",
        "This is the final page (4).\nThanks for trying out the paginator!"
    ]
    
    # Create and start paginator
    paginator = Paginator(pages, timeout=60.0)
    await paginator.start(ctx.interaction)


@bot.slash_command(name="embed_paginator", description="Demonstrate embed paginator")
async def embed_paginator_command(ctx):
    """Demonstrate embed paginator with rich content."""
    
    # Create sample embeds
    embeds = []
    colors = [discord.Color.red(), discord.Color.green(), discord.Color.blue(), discord.Color.purple()]
    
    for i, color in enumerate(colors, 1):
        embed = discord.Embed(
            title=f"Embed Page {i}",
            description=f"This is embed page {i} with a {color.name} color theme.",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Page Number", value=str(i), inline=True)
        embed.add_field(name="Color", value=color.name.title(), inline=True)
        embed.set_footer(text="Embed Paginator Example")
        embeds.append(embed)
    
    # Create and start embed paginator
    paginator = EmbedPaginator(embeds, timeout=60.0)
    await paginator.start(ctx.interaction)


@bot.slash_command(name="confirm", description="Demonstrate confirmation dialog")
async def confirm_command(ctx):
    """Demonstrate confirmation dialog."""
    
    embed = create_embed(
        title="Confirmation Required",
        description="Do you want to proceed with this action?",
        color=discord.Color.orange()
    )
    
    # Create and show confirmation dialog
    dialog = ConfirmDialog(timeout=30.0)
    result = await dialog.start(ctx.interaction, embed=embed)
    
    if result:
        success_embed = create_embed(
            title="✅ Confirmed",
            description="You confirmed the action!",
            color=discord.Color.green()
        )
        await safe_send(ctx.interaction, embed=success_embed, ephemeral=True)
    else:
        cancel_embed = create_embed(
            title="❌ Cancelled",
            description="You cancelled the action.",
            color=discord.Color.red()
        )
        await safe_send(ctx.interaction, embed=cancel_embed, ephemeral=True)


@bot.slash_command(name="form", description="Demonstrate form functionality")
async def form_command(ctx):
    """Demonstrate form with validation."""
    
    # Create form with various field types
    form = Form("User Information Form", timeout=300.0)
    
    form.field(
        "name",
        "Full Name",
        placeholder="Enter your full name",
        min_length=2,
        max_length=50,
        required=True
    ).field(
        "email",
        "Email Address",
        placeholder="your.email@example.com",
        validator=Validators.email,
        required=True
    ).field(
        "age",
        "Age",
        placeholder="Enter your age",
        validator=Validators.integer(min_val=13, max_val=120),
        transformer=Transformers.integer,
        required=True
    ).field(
        "bio",
        "Biography",
        placeholder="Tell us about yourself...",
        style=discord.TextStyle.long,
        max_length=500,
        required=False
    )
    
    # Show form and get results
    result = await form.show(ctx.interaction)
    
    if result:
        # Create summary embed
        embed = create_embed(
            title="Form Submitted Successfully",
            description="Here's what you submitted:",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Name", value=result['name'], inline=True)
        embed.add_field(name="Email", value=result['email'], inline=True)
        embed.add_field(name="Age", value=str(result['age']), inline=True)
        
        if result.get('bio'):
            embed.add_field(name="Bio", value=result['bio'], inline=False)
        
        await safe_send(ctx.interaction.user, embed=embed)


@bot.slash_command(name="utilities", description="Demonstrate utility functions")
async def utilities_command(ctx):
    """Demonstrate various utility functions."""
    
    user = ctx.author
    now = datetime.utcnow()
    
    embed = create_embed(
        title="Utility Functions Demo",
        description="Here are some utility function examples:",
        color=discord.Color.blue(),
        author=user,
        timestamp=now
    )
    
    # Avatar utility
    embed.add_field(
        name="User Avatar",
        value=f"[Avatar URL]({get_user_avatar(user)})",
        inline=False
    )
    
    # Timestamp formatting
    embed.add_field(
        name="Formatted Timestamps",
        value=f"Short: {format_timestamp(now, 't')}\n"
              f"Long: {format_timestamp(now, 'F')}\n"
              f"Relative: {format_timestamp(now, 'R')}",
        inline=False
    )
    
    # Text utilities
    long_text = "This is a very long text that demonstrates the text chunking utility function."
    chunks = []
    from dispyplus.utils import chunk_text, humanize_duration, escape_markdown
    
    text_chunks = chunk_text(long_text * 5, max_length=100)
    embed.add_field(
        name="Text Chunking",
        value=f"Original length: {len(long_text * 5)}\nChunks created: {len(text_chunks)}",
        inline=True
    )
    
    # Duration formatting
    embed.add_field(
        name="Duration Formatting",
        value=f"3661 seconds = {humanize_duration(3661)}",
        inline=True
    )
    
    # Markdown escaping
    markdown_text = "This *has* **markdown** `formatting`"
    embed.add_field(
        name="Markdown Escaping",
        value=f"Original: {markdown_text}\nEscaped: {escape_markdown(markdown_text)}",
        inline=False
    )
    
    await ctx.respond(embed=embed)


@bot.slash_command(name="events", description="Demonstrate custom events")
async def events_command(ctx):
    """Demonstrate custom event system."""
    
    # Add a temporary event listener
    @bot.event_handler.listen('demo_event', once=True)
    async def demo_listener(event, message):
        embed = create_embed(
            title="Custom Event Triggered!",
            description=f"Received message: {message}",
            color=discord.Color.green()
        )
        await safe_send(ctx.channel, embed=embed)
    
    # Dispatch the custom event
    await bot.event_handler.dispatch('demo_event', "Hello from custom event!")
    
    await ctx.respond("Custom event dispatched! Check the channel for the response.", ephemeral=True)


if __name__ == "__main__":
    # Load bot token from config or environment
    token = bot.config.get('bot.token')
    
    if not token:
        print("Please set your bot token in config.json:")
        print('{"bot": {"token": "YOUR_BOT_TOKEN_HERE"}}')
        exit(1)
    
    # Run the bot
    bot.run(token)