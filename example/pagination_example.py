import asyncio
import discord
from discord.ext import commands

from dispyplus import DispyplusBot, EnhancedContext, ConfigManager
# PaginatorView is automatically imported via dispyplus.ui
# from dispyplus.ui import PaginatorView # Direct import if needed

# --- Bot Setup (similar to other examples) ---
CONFIG_FILE = 'config.ini'
config = ConfigManager(CONFIG_FILE)

intents = discord.Intents.default()
# Add any necessary intents, e.g., for message content if testing text commands
# intents.message_content = True

bot = DispyplusBot(
    command_prefix=config.get('Bot', 'prefix_pagination_example', fallback='!page '),
    intents=intents,
    config_path=CONFIG_FILE
)

# --- Pagination Example Cog ---
class PaginationExamplesCog(commands.Cog):
    def __init__(self, bot: DispyplusBot):
        self.bot = bot

    @commands.hybrid_command(name="pagelist", description="Paginates a simple list of strings.")
    async def paginate_list_command(self, ctx: EnhancedContext, num_items: int = 50):
        if num_items <= 0:
            await ctx.error("Number of items must be positive.")
            return
        if num_items > 200: # Prevent overly large lists for example
            await ctx.warning("Number of items capped at 200 for this example.")
            num_items = 200

        data = [f"This is item number {i+1} in the list." for i in range(num_items)]

        await ctx.paginate(
            data_source=data,
            items_per_page=7,
            content_type="text_lines", # Will format as lines in an embed description
            show_jump_button=True,
            show_page_select=True,
            initial_message_content=f"Paginating {num_items} text lines:"
        )

    @commands.hybrid_command(name="pageembeds", description="Paginates a list of embeds.")
    async def paginate_embeds_command(self, ctx: EnhancedContext, num_embeds: int = 15):
        if num_embeds <= 0:
            await ctx.error("Number of embeds must be positive.")
            return
        if num_embeds > 50: # Prevent too many embeds
            await ctx.warning("Number of embeds capped at 50 for this example.")
            num_embeds = 50

        embeds = []
        for i in range(num_embeds):
            embed = discord.Embed(
                title=f"Embed Page {i+1}/{num_embeds}",
                description=f"This is the content of embed number {i+1}.",
                color=discord.Color.random()
            )
            embed.add_field(name="Field A", value=f"Value A for embed {i+1}")
            embed.set_footer(text=f"Original footer for embed {i+1}")
            embeds.append(embed)

        await ctx.paginate(
            data_source=embeds,
            items_per_page=1, # Typically 1 embed per page for this content type
            content_type="embeds",
            show_jump_button=True,
            show_page_select=True # Select menu will show 1 option per embed page
        )

    async def _async_data_generator(self, count: int):
        for i in range(count):
            await asyncio.sleep(0.1) # Simulate some async work (e.g., API call, DB query)
            yield f"Asynchronously generated item {i+1}"

    @commands.hybrid_command(name="pageasync", description="Paginates data from an async generator.")
    async def paginate_async_command(self, ctx: EnhancedContext, num_items: int = 40):
        if num_items <= 0:
            await ctx.error("Number of items must be positive.")
            return
        if num_items > 100:
            await ctx.warning("Async items capped at 100 for this example.")
            num_items = 100

        data_gen = self._async_data_generator(num_items)

        await ctx.paginate(
            data_source=data_gen,
            items_per_page=6,
            content_type="text_lines",
            show_jump_button=True, # Jump button might be less useful if total pages unknown for a while
            show_page_select=True, # Select menu will populate as pages are buffered
            initial_message_content="Paginating items from an async source (may take a moment to load all pages):"
        )

    def _custom_item_formatter(self, items_on_page, page_number, view_instance):
        # items_on_page is a list of items for the current page
        # page_number is 0-indexed
        # view_instance is the PaginatorView instance (for accessing total_pages etc. if needed)

        title = f"Custom Formatted - Page {page_number + 1}"
        if view_instance.total_pages is not None:
            title += f" / {view_instance.total_pages}"

        description_lines = [f"✨ **{item['name']}** (ID: {item['id']}) - Status: _{item['status']}_" for item in items_on_page]

        embed = discord.Embed(title=title, description="\n".join(description_lines), color=discord.Color.purple())
        embed.set_footer(text=f"Showing {len(items_on_page)} custom items.")

        # You can return (content, embed), just content, or just embed
        return (f"Displaying page {page_number + 1} with custom formatting.", embed)

    @commands.hybrid_command(name="pagecustom", description="Paginates custom data with a formatter function.")
    async def paginate_custom_command(self, ctx: EnhancedContext, num_items: int = 25):
        if num_items <= 0:
            await ctx.error("Number of items must be positive.")
            return
        if num_items > 75:
            await ctx.warning("Custom items capped at 75 for this example.")
            num_items = 75

        custom_data = [
            {"id": i, "name": f"Object Alpha-{i}", "status": "Active" if i % 2 == 0 else "Inactive"}
            for i in range(num_items)
        ]

        await ctx.paginate(
            data_source=custom_data,
            items_per_page=4,
            content_type="generic", # Important for using formatter_func
            formatter_func=self._custom_item_formatter,
            show_jump_button=True,
            show_page_select=True
        )

    @commands.hybrid_command(name="pagesimple", description="Minimal pagination with only next/prev.")
    async def paginate_simple_command(self, ctx: EnhancedContext):
        data = [f"Simple Item {i+1}" for i in range(10)] # Short list
        await ctx.paginate(
            data,
            items_per_page=3,
            content_type="text_lines",
            show_page_buttons=True, # Standard buttons
            show_jump_button=False, # No jump
            show_page_select=False  # No select
        )


async def setup(bot: DispyplusBot):
    await bot.add_cog(PaginationExamplesCog(bot))

async def main():
    # It's good practice to ensure config.ini has the bot token
    token = config.get('Bot', 'token')
    if not token:
        print("Bot token not found in config.ini. Please add [Bot] section with 'token = YOUR_TOKEN'.")
        return

    await setup(bot)
    print(f"Starting pagination example bot with prefix '{bot.command_prefix}'...")
    await bot.start(token)

if __name__ == "__main__":
    # Ensure this example is run with a valid config.ini containing the bot token.
    # If you have other example bots, ensure only one is running with a given token at a time.
    asyncio.run(main())
