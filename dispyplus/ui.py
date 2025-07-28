"""
UI components for Discord bots including paginators and confirmation dialogs.
"""

import asyncio
from typing import Any, Callable, List, Optional, Union
import discord
from discord.ext import commands


class Paginator(discord.ui.View):
    """
    A paginator that can display multiple pages of content with navigation buttons.
    """
    
    def __init__(
        self,
        pages: List[Union[str, discord.Embed]],
        *,
        timeout: float = 180.0,
        per_page: int = 1,
        show_page_count: bool = True,
        show_first_last: bool = True,
        ephemeral: bool = False
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.per_page = per_page
        self.show_page_count = show_page_count
        self.show_first_last = show_first_last
        self.ephemeral = ephemeral
        self.current_page = 0
        self.message: Optional[discord.Message] = None
        
        # Calculate total pages
        self.total_pages = len(pages)
        
        # Add buttons based on configuration
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Setup navigation buttons based on configuration."""
        if self.total_pages <= 1:
            return
        
        if self.show_first_last:
            self.add_item(FirstPageButton())
        
        self.add_item(PreviousPageButton())
        
        if self.show_page_count:
            self.add_item(PageCountButton())
        
        self.add_item(NextPageButton())
        
        if self.show_first_last:
            self.add_item(LastPageButton())
        
        self.add_item(StopButton())
    
    def get_current_page_content(self) -> Union[str, discord.Embed]:
        """Get the content for the current page."""
        return self.pages[self.current_page]
    
    def get_page_kwargs(self) -> dict:
        """Get kwargs for sending/editing the message."""
        content = self.get_current_page_content()
        
        if isinstance(content, discord.Embed):
            return {"embed": content, "content": None, "view": self}
        else:
            return {"content": content, "embed": None, "view": self}
    
    async def start(self, interaction: discord.Interaction) -> discord.Message:
        """Start the paginator by sending the initial message."""
        kwargs = self.get_page_kwargs()
        
        if self.ephemeral:
            await interaction.response.send_message(ephemeral=True, **kwargs)
            self.message = await interaction.original_response()
        else:
            await interaction.response.send_message(**kwargs)
            self.message = await interaction.original_response()
        
        return self.message
    
    async def update_page(self, interaction: discord.Interaction):
        """Update the message with the current page content."""
        kwargs = self.get_page_kwargs()
        await interaction.response.edit_message(**kwargs)
    
    async def on_timeout(self):
        """Handle timeout by disabling all buttons."""
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


class FirstPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="⏪", style=discord.ButtonStyle.gray)
    
    async def callback(self, interaction: discord.Interaction):
        view: Paginator = self.view
        view.current_page = 0
        await view.update_page(interaction)


class PreviousPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="◀️", style=discord.ButtonStyle.gray)
    
    async def callback(self, interaction: discord.Interaction):
        view: Paginator = self.view
        view.current_page = max(0, view.current_page - 1)
        await view.update_page(interaction)


class PageCountButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.gray, disabled=True)
    
    def update_label(self, current: int, total: int):
        self.label = f"{current + 1}/{total}"


class NextPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="▶️", style=discord.ButtonStyle.gray)
    
    async def callback(self, interaction: discord.Interaction):
        view: Paginator = self.view
        view.current_page = min(view.total_pages - 1, view.current_page + 1)
        await view.update_page(interaction)


class LastPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="⏩", style=discord.ButtonStyle.gray)
    
    async def callback(self, interaction: discord.Interaction):
        view: Paginator = self.view
        view.current_page = view.total_pages - 1
        await view.update_page(interaction)


class StopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="⏹️", style=discord.ButtonStyle.red)
    
    async def callback(self, interaction: discord.Interaction):
        view: Paginator = self.view
        view.stop()
        
        for item in view.children:
            item.disabled = True
        
        await interaction.response.edit_message(view=view)


class EmbedPaginator(Paginator):
    """
    A specialized paginator for Discord embeds with additional features.
    """
    
    def __init__(
        self,
        embeds: List[discord.Embed],
        *,
        timeout: float = 180.0,
        show_page_count: bool = True,
        show_first_last: bool = True,
        ephemeral: bool = False,
        add_page_numbers: bool = True
    ):
        self.add_page_numbers = add_page_numbers
        
        # Add page numbers to embeds if requested
        if add_page_numbers:
            for i, embed in enumerate(embeds):
                if embed.footer.text:
                    embed.set_footer(text=f"{embed.footer.text} • Page {i + 1}/{len(embeds)}")
                else:
                    embed.set_footer(text=f"Page {i + 1}/{len(embeds)}")
        
        super().__init__(
            embeds,
            timeout=timeout,
            show_page_count=show_page_count,
            show_first_last=show_first_last,
            ephemeral=ephemeral
        )


class ConfirmDialog(discord.ui.View):
    """
    A confirmation dialog with Yes/No buttons.
    """
    
    def __init__(
        self,
        *,
        timeout: float = 60.0,
        confirm_label: str = "Yes",
        cancel_label: str = "No",
        confirm_style: discord.ButtonStyle = discord.ButtonStyle.green,
        cancel_style: discord.ButtonStyle = discord.ButtonStyle.red
    ):
        super().__init__(timeout=timeout)
        self.result: Optional[bool] = None
        self.message: Optional[discord.Message] = None
        
        # Add confirm button
        confirm_button = discord.ui.Button(
            label=confirm_label,
            style=confirm_style,
            emoji="✅"
        )
        confirm_button.callback = self._confirm_callback
        self.add_item(confirm_button)
        
        # Add cancel button
        cancel_button = discord.ui.Button(
            label=cancel_label,
            style=cancel_style,
            emoji="❌"
        )
        cancel_button.callback = self._cancel_callback
        self.add_item(cancel_button)
    
    async def _confirm_callback(self, interaction: discord.Interaction):
        """Handle confirm button click."""
        self.result = True
        self.stop()
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(view=self)
    
    async def _cancel_callback(self, interaction: discord.Interaction):
        """Handle cancel button click."""
        self.result = False
        self.stop()
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(view=self)
    
    async def start(
        self,
        interaction: discord.Interaction,
        content: str = None,
        embed: discord.Embed = None,
        ephemeral: bool = False
    ) -> bool:
        """
        Start the confirmation dialog.
        
        Args:
            interaction: The interaction to respond to
            content: Text content for the message
            embed: Embed for the message
            ephemeral: Whether the message should be ephemeral
            
        Returns:
            True if confirmed, False if cancelled or timed out
        """
        if ephemeral:
            await interaction.response.send_message(
                content=content,
                embed=embed,
                view=self,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                content=content,
                embed=embed,
                view=self
            )
        
        self.message = await interaction.original_response()
        
        # Wait for user interaction
        await self.wait()
        
        return self.result if self.result is not None else False
    
    async def on_timeout(self):
        """Handle timeout by disabling all buttons."""
        self.result = False
        
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


class SelectPaginator(discord.ui.View):
    """
    A paginator that uses a select menu for navigation.
    """
    
    def __init__(
        self,
        pages: List[Union[str, discord.Embed]],
        page_labels: List[str] = None,
        *,
        timeout: float = 180.0,
        placeholder: str = "Choose a page...",
        ephemeral: bool = False
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.page_labels = page_labels or [f"Page {i + 1}" for i in range(len(pages))]
        self.ephemeral = ephemeral
        self.current_page = 0
        self.message: Optional[discord.Message] = None
        
        # Create select menu
        select = PageSelect(self.page_labels, placeholder)
        self.add_item(select)
    
    def get_current_page_content(self) -> Union[str, discord.Embed]:
        """Get the content for the current page."""
        return self.pages[self.current_page]
    
    def get_page_kwargs(self) -> dict:
        """Get kwargs for sending/editing the message."""
        content = self.get_current_page_content()
        
        if isinstance(content, discord.Embed):
            return {"embed": content, "content": None, "view": self}
        else:
            return {"content": content, "embed": None, "view": self}
    
    async def start(self, interaction: discord.Interaction) -> discord.Message:
        """Start the paginator by sending the initial message."""
        kwargs = self.get_page_kwargs()
        
        if self.ephemeral:
            await interaction.response.send_message(ephemeral=True, **kwargs)
            self.message = await interaction.original_response()
        else:
            await interaction.response.send_message(**kwargs)
            self.message = await interaction.original_response()
        
        return self.message
    
    async def update_page(self, interaction: discord.Interaction, page_index: int):
        """Update the message with the specified page content."""
        self.current_page = page_index
        kwargs = self.get_page_kwargs()
        await interaction.response.edit_message(**kwargs)


class PageSelect(discord.ui.Select):
    def __init__(self, page_labels: List[str], placeholder: str):
        options = [
            discord.SelectOption(
                label=label,
                value=str(i),
                description=f"Go to {label}"
            )
            for i, label in enumerate(page_labels)
        ]
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: SelectPaginator = self.view
        page_index = int(self.values[0])
        await view.update_page(interaction, page_index)