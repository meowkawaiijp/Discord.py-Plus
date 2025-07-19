import logging
import discord
from discord import ui
from typing import Optional, Callable, Awaitable, List, Any, Generic, TypeVar
from .components import EnhancedView
ItemType = TypeVar('ItemType')

class ConfirmationView(EnhancedView):

    def __init__(self, *, timeout: float=180.0, interaction_check: Optional[Callable[[discord.Interaction], Awaitable[bool]]]=None):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self._interaction_check_func = interaction_check
        self._original_user_id: Optional[int] = None
        self.message: Optional[discord.Message] = None
        self.view = self

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        logger = getattr(self.view.bot, 'logger', None) if hasattr(self.view, 'bot') else logging.getLogger(self.__class__.__name__)
        if self._original_user_id is None and (not self._interaction_check_func):
            if logger:
                logger.warning('ConfirmationView original_user_id not set and no custom interaction_check provided.')
            return False
        if self._interaction_check_func:
            return await self._interaction_check_func(interaction)
        if self._original_user_id:
            return interaction.user.id == self._original_user_id
        return False

    def set_original_user_id(self, user_id: int):
        self._original_user_id = user_id

    @ui.button(label='Yes', style=discord.ButtonStyle.green, custom_id='confirm_yes_new_ui')
    async def confirm_button_ui(self, interaction: discord.Interaction, button: ui.Button):
        self.value = True
        self.stop()
        for item in self.children:
            if isinstance(item, (ui.Button, ui.Select)):
                item.disabled = True
        await interaction.response.edit_message(view=self)

    @ui.button(label='No', style=discord.ButtonStyle.red, custom_id='confirm_no_new_ui')
    async def cancel_button_ui(self, interaction: discord.Interaction, button: ui.Button):
        self.value = False
        self.stop()
        for item in self.children:
            if isinstance(item, (ui.Button, ui.Select)):
                item.disabled = True
        await interaction.response.edit_message(view=self)

    async def on_custom_timeout(self) -> None:
        self.value = None
        if self.message:
            try:
                await self.message.edit(content='Confirmation timed out.', view=self)
            except discord.NotFound:
                pass

class PaginatedSelectView(EnhancedView, Generic[ItemType]):

    def __init__(self, options: List[discord.SelectOption], placeholder: str='Select an option...', items_per_page: int=20, *, timeout: float=180.0, author_id: Optional[int]=None, custom_id_prefix: str='paginated_select'):
        super().__init__(timeout=timeout)
        self.all_options = options
        self.placeholder = placeholder
        self.items_per_page = min(items_per_page, 25)
        self._author_id = author_id
        self.custom_id_prefix = custom_id_prefix
        self.current_page = 0
        self.total_pages = max(1, (len(self.all_options) + self.items_per_page - 1) // self.items_per_page)
        self.selected_values: List[ItemType] = []
        self.message: Optional[discord.Message] = None
        self._update_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._author_id and interaction.user.id != self._author_id:
            await interaction.response.send_message('You cannot interact with this menu.', ephemeral=True)
            return False
        return True

    def _get_options_for_current_page(self) -> List[discord.SelectOption]:
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        return self.all_options[start_index:end_index]

    def _update_components(self):
        self.clear_items()
        current_options = self._get_options_for_current_page()
        select_menu = ui.Select(placeholder=self.placeholder, options=current_options if current_options else [discord.SelectOption(label='No options', value='_no_opt_', default=True)], min_values=1, max_values=1, custom_id=f'{self.custom_id_prefix}:select:{self.current_page}', disabled=not bool(current_options))
        select_menu.callback = self.select_callback
        self.add_item(select_menu)
        if self.total_pages > 1:
            prev_button = ui.Button(label='Previous', style=discord.ButtonStyle.blurple, custom_id=f'{self.custom_id_prefix}:prev', disabled=self.current_page == 0, row=1)
            prev_button.callback = self.prev_page_callback
            page_label = ui.Button(label=f'Page {self.current_page + 1}/{self.total_pages}', style=discord.ButtonStyle.grey, disabled=True, custom_id=f'{self.custom_id_prefix}:pagelabel', row=1)
            next_button = ui.Button(label='Next', style=discord.ButtonStyle.blurple, custom_id=f'{self.custom_id_prefix}:next', disabled=self.current_page >= self.total_pages - 1, row=1)
            next_button.callback = self.next_page_callback
            self.add_item(prev_button)
            self.add_item(page_label)
            self.add_item(next_button)

    async def select_callback(self, interaction: discord.Interaction):
        selected_raw_values = interaction.data.get('values', []) if interaction.data else []
        self.selected_values = [str(val) for val in selected_raw_values]
        for item_in_view in self.children:
            if hasattr(item_in_view, 'disabled'):
                item_in_view.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def prev_page_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_components()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    async def next_page_callback(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_components()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    async def on_custom_timeout(self) -> None:
        if self.message:
            try:
                pass
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass

class SimpleSelectView(EnhancedView, Generic[ItemType]):

    def __init__(self, options: List[discord.SelectOption], placeholder: str='Select an option...', *, timeout: float=180.0, author_id: Optional[int]=None, custom_id_prefix: str='simple_select', min_values: int=1, max_values: int=1):
        super().__init__(timeout=timeout)
        self.all_options = options
        self.placeholder = placeholder
        self._author_id = author_id
        self.custom_id_prefix = custom_id_prefix
        self.min_values = min_values
        self.max_values = max_values
        self.selected_values: List[ItemType] = []
        self.message: Optional[discord.Message] = None
        self._update_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._author_id and interaction.user.id != self._author_id:
            await interaction.response.send_message('You cannot interact with this menu.', ephemeral=True)
            return False
        return True

    def _update_components(self):
        self.clear_items()
        select_menu = ui.Select(placeholder=self.placeholder, options=self.all_options if self.all_options else [discord.SelectOption(label='No options', value='_no_opt_', default=True)], min_values=self.min_values, max_values=self.max_values, custom_id=f'{self.custom_id_prefix}:select', disabled=not bool(self.all_options))
        select_menu.callback = self.select_callback
        self.add_item(select_menu)

    async def select_callback(self, interaction: discord.Interaction):
        selected_raw_values = interaction.data.get('values', []) if interaction.data else []
        self.selected_values = [str(val) for val in selected_raw_values]
        for item_in_view in self.children:
            if hasattr(item_in_view, 'disabled'):
                item_in_view.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_custom_timeout(self) -> None:
        if self.message:
            try:
                pass
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass
__all__ = ['ConfirmationView', 'PaginatedSelectView', 'SimpleSelectView']
