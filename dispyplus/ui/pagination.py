from typing import List, Any, Optional, Union, Callable, AsyncIterator, Tuple, Literal
import discord
import math
from .components import EnhancedView, JumpToPageModal

class PaginatorView(EnhancedView):

    def __init__(self, data_source: Union[List[Any], AsyncIterator[Any]], items_per_page: int=10, *, formatter_func: Optional[Callable[[List[Any], int, 'PaginatorView'], Union[str, discord.Embed, Tuple[Optional[str], Optional[discord.Embed]]]]]=None, content_type: Literal['embeds', 'text_lines', 'generic']='generic', show_page_buttons: bool=True, show_page_select: bool=False, show_jump_button: bool=False, timeout: Optional[float]=180.0, author_id: Optional[int]=None):
        super().__init__(timeout=timeout)
        if items_per_page <= 0:
            raise ValueError('items_per_page must be greater than 0.')
        self.data_source = data_source
        self.items_per_page = items_per_page
        self.formatter_func = formatter_func
        self.content_type = content_type
        self.show_page_buttons = show_page_buttons
        self.show_page_select = show_page_select
        self.show_jump_button = show_jump_button
        self.author_id = author_id
        self.current_page_number: int = 0
        self.total_pages: Optional[int] = None
        self._is_async_iterator = not isinstance(self.data_source, list)
        self._async_buffer: List[Any] = []
        self._async_iterator_exhausted: bool = False
        if isinstance(self.data_source, list):
            self.total_pages = math.ceil(len(self.data_source) / self.items_per_page)
            if self.total_pages == 0:
                self.total_pages = 1
        self.current_page_content: Optional[str] = None
        self.current_page_embed: Optional[discord.Embed] = None
        self.message: Optional[discord.Message] = None
        self.first_page_button: Optional[discord.ui.Button] = None
        self.prev_page_button: Optional[discord.ui.Button] = None
        self.current_page_label_button: Optional[discord.ui.Button] = None
        self.next_page_button: Optional[discord.ui.Button] = None
        self.last_page_button: Optional[discord.ui.Button] = None
        self.stop_button: Optional[discord.ui.Button] = None
        self.jump_to_page_button: Optional[discord.ui.Button] = None
        self.page_select_menu: Optional[discord.ui.Select] = None
        current_row_for_controls = 0
        if self.show_page_buttons:
            self._setup_buttons(row=current_row_for_controls)
            current_row_for_controls += 1
        if self.show_jump_button:
            self._setup_jump_button(row=current_row_for_controls)
        if self.show_page_select:
            select_menu_row = current_row_for_controls if not self.show_jump_button else current_row_for_controls
            if self.show_page_buttons and self.show_jump_button:
                select_menu_row = 1
                if self.stop_button:
                    self.stop_button.row = 2
            elif self.show_page_buttons:
                select_menu_row = 1
                if self.stop_button:
                    self.stop_button.row = 2
            elif self.show_jump_button:
                select_menu_row = 0
            else:
                select_menu_row = 0
            self._setup_page_select_menu(row=select_menu_row)

    def _setup_buttons(self, row: int=0):
        self.first_page_button = discord.ui.Button(label='|< First', style=discord.ButtonStyle.secondary, custom_id='paginator_first', row=row)
        self.first_page_button.callback = self.go_to_first_page
        self.add_item(self.first_page_button)
        self.prev_page_button = discord.ui.Button(label='< Prev', style=discord.ButtonStyle.primary, custom_id='paginator_prev', row=0)
        self.prev_page_button.callback = self.go_to_previous_page
        self.add_item(self.prev_page_button)
        self.current_page_label_button = discord.ui.Button(label=f'Page ...', style=discord.ButtonStyle.grey, disabled=True, custom_id='paginator_current_page_label', row=0)
        self.add_item(self.current_page_label_button)
        self.next_page_button = discord.ui.Button(label='Next >', style=discord.ButtonStyle.primary, custom_id='paginator_next', row=0)
        self.next_page_button.callback = self.go_to_next_page
        self.add_item(self.next_page_button)
        self.last_page_button = discord.ui.Button(label='Last >|', style=discord.ButtonStyle.secondary, custom_id='paginator_last', row=0)
        self.last_page_button.callback = self.go_to_last_page
        self.add_item(self.last_page_button)
        stop_button_row_candidate = 0
        if self.show_page_buttons:
            stop_button_row_candidate = 1
        if self.show_jump_button or self.show_page_select:
            stop_button_row_candidate = (1 if self.show_page_buttons else 0) + 1
        if self.show_page_buttons or self.show_jump_button or self.show_page_select:
            self.stop_button = discord.ui.Button(label='Stop', style=discord.ButtonStyle.danger, custom_id='paginator_stop', row=stop_button_row_candidate)
            self.stop_button.callback = self.stop_pagination
            self.add_item(self.stop_button)

    def _setup_jump_button(self, row: int=1):
        actual_row = 0 if not self.show_page_buttons else 1
        self.jump_to_page_button = discord.ui.Button(label='Jump to Page...', style=discord.ButtonStyle.grey, custom_id='paginator_jump', row=actual_row)
        self.jump_to_page_button.callback = self.prompt_jump_to_page
        self.add_item(self.jump_to_page_button)

    def _setup_page_select_menu(self, row: int=1):
        actual_row = 0
        if self.show_page_buttons:
            actual_row = 1
        self.page_select_menu = discord.ui.Select(placeholder='Select a page...', custom_id='paginator_page_select', row=actual_row, options=[discord.SelectOption(label='Page 1', value='0')])
        self.page_select_menu.callback = self.select_page_from_menu
        self.add_item(self.page_select_menu)

    async def prompt_jump_to_page(self, interaction: discord.Interaction):
        modal = JumpToPageModal(title='Jump to Page', paginator_view=self)
        await interaction.response.send_modal(modal)

    async def select_page_from_menu(self, interaction: discord.Interaction):
        if not self.page_select_menu or not self.page_select_menu.values:
            await interaction.response.defer()
            return
        selected_page_str = self.page_select_menu.values[0]
        try:
            page_to_jump = int(selected_page_str)
            if self.total_pages is not None and (not 0 <= page_to_jump < self.total_pages):
                await interaction.response.send_message(f'Invalid page number. Please choose between 1 and {self.total_pages}.', ephemeral=True)
                return
            elif self.total_pages is None and page_to_jump < 0:
                await interaction.response.send_message(f'Invalid page number.', ephemeral=True)
                return
            self.current_page_number = page_to_jump
            await self._navigate(interaction)
        except ValueError:
            await interaction.response.send_message('Invalid selection.', ephemeral=True)

    async def _update_button_states(self):
        if self.show_page_buttons and self.first_page_button and self.prev_page_button and self.current_page_label_button and self.next_page_button and self.last_page_button:
            is_first_page = self.current_page_number == 0
            self.first_page_button.disabled = is_first_page
            self.prev_page_button.disabled = is_first_page
            page_label_text = f'Page {self.current_page_number + 1}'
            if self.total_pages is not None:
                page_label_text += f'/{self.total_pages}'
            elif self._async_iterator_exhausted:
                if self.total_pages is None:
                    self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page) if len(self._async_buffer) > 0 else 1
                page_label_text = f'Page {self.current_page_number + 1}/{self.total_pages}'
            else:
                page_label_text += '/?'
            self.current_page_label_button.label = page_label_text
            is_last_page = False
            if self.total_pages is not None:
                is_last_page = self.current_page_number >= self.total_pages - 1
            elif self._async_iterator_exhausted:
                is_last_page = self.current_page_number >= (self.total_pages or float('inf')) - 1
            self.next_page_button.disabled = is_last_page
            self.last_page_button.disabled = is_last_page or (self.total_pages is None and (not self._async_iterator_exhausted))
        if self.show_jump_button and self.jump_to_page_button:
            jump_disabled = self.total_pages is not None and self.total_pages <= 1 or (self.total_pages is None and (not self._async_iterator_exhausted))
            self.jump_to_page_button.disabled = jump_disabled
        if self.show_page_select and self.page_select_menu:
            current_select_value = str(self.current_page_number)
            new_options: List[discord.SelectOption] = []
            select_disabled = self.total_pages is None and (not self._async_iterator_exhausted) and (not self._async_buffer) or (self.total_pages is not None and self.total_pages <= 1)
            self.page_select_menu.disabled = select_disabled
            self.page_select_menu.placeholder = 'Select a page...'
            if select_disabled and (self.total_pages is None and (not self._async_iterator_exhausted)):
                self.page_select_menu.placeholder = 'Page count determining...'
            elif select_disabled and (self.total_pages is not None and self.total_pages <= 1):
                self.page_select_menu.placeholder = 'Only one page'
            if not select_disabled and self.total_pages is not None and (self.total_pages > 0):
                if self.total_pages <= 25:
                    for i in range(self.total_pages):
                        new_options.append(discord.SelectOption(label=f'Page {i + 1}', value=str(i), default=str(i) == current_select_value))
                else:
                    pages_to_show_indices = set([0, self.total_pages - 1])
                    for i in range(max(0, self.current_page_number - 2), min(self.total_pages, self.current_page_number + 3)):
                        pages_to_show_indices.add(i)
                    num_steps = 5
                    if self.total_pages > 50:
                        num_steps = 10
                    if len(pages_to_show_indices) < 25:
                        for i in range(min(5, self.total_pages)):
                            pages_to_show_indices.add(i)
                    if len(pages_to_show_indices) < 25:
                        for i in range(max(0, self.total_pages - 5), self.total_pages):
                            pages_to_show_indices.add(i)
                    sorted_pages = sorted(list(pages_to_show_indices))
                    if len(sorted_pages) > 25:
                        try:
                            current_idx = sorted_pages.index(self.current_page_number)
                            start = max(0, current_idx - 12)
                            end = min(len(sorted_pages), start + 25)
                            if end - start < 25:
                                start = max(0, end - 25)
                            sorted_pages = sorted_pages[start:end]
                        except ValueError:
                            sorted_pages = sorted_pages[:25]
                    for i in sorted_pages:
                        new_options.append(discord.SelectOption(label=f'Page {i + 1}', value=str(i), default=str(i) == current_select_value))
            elif not select_disabled and self._async_buffer:
                max_buffered_page = math.ceil(len(self._async_buffer) / self.items_per_page)
                for i in range(min(max_buffered_page, 25)):
                    new_options.append(discord.SelectOption(label=f'Page {i + 1}', value=str(i), default=str(i) == current_select_value))
                if max_buffered_page > 25:
                    new_options[-1] = discord.SelectOption(label=f"Page {new_options[-1].label.split(' ')[1]} (more buffered...)", value=new_options[-1].value, default=new_options[-1].value == current_select_value)
            if not new_options:
                self.page_select_menu.disabled = True
                new_options.append(discord.SelectOption(label='N/A', value='-1'))
            self.page_select_menu.options = new_options
        elif self.show_page_select and (not self.page_select_menu):
            pass

    async def _get_page_data(self, page_number: int) -> List[Any]:
        """
        Retrieves the data for the given page number.
        Handles both list and async iterator data sources.
        Page number is 0-indexed.
        """
        if page_number < 0:
            return []
        if isinstance(self.data_source, list):
            if self.total_pages is not None and page_number >= self.total_pages:
                return []
            start_index = page_number * self.items_per_page
            end_index = start_index + self.items_per_page
            return self.data_source[start_index:end_index]
        elif hasattr(self.data_source, '__aiter__'):
            target_end_index = (page_number + 1) * self.items_per_page
            while len(self._async_buffer) < target_end_index and (not self._async_iterator_exhausted):
                try:
                    if hasattr(self.data_source, '__anext__'):
                        item = await self.data_source.__anext__()
                        self._async_buffer.append(item)
                    else:
                        self._async_iterator_exhausted = True
                        break
                except StopAsyncIteration:
                    self._async_iterator_exhausted = True
                    break
            if self._async_iterator_exhausted:
                self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page)
                if self.total_pages == 0:
                    self.total_pages = 1
            start_index = page_number * self.items_per_page
            end_index = min(target_end_index, len(self._async_buffer))
            if start_index >= len(self._async_buffer) and self._async_iterator_exhausted:
                return []
            return self._async_buffer[start_index:end_index]
        else:
            raise TypeError('Unsupported data_source type. Must be a list or an async iterator.')

    async def format_page(self) -> Tuple[Optional[str], Optional[discord.Embed]]:
        """
        Formats the current page data into content and/or embed.
        This method should be overridden by subclasses or a formatter_func should be provided.
        Returns a tuple (content, embed).
        """
        page_data = await self._get_page_data(self.current_page_number)
        page_title = f'Page {self.current_page_number + 1}'
        if self.total_pages is not None:
            page_title += f'/{self.total_pages}'
        elif self._async_iterator_exhausted and self.total_pages is None:
            self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page)
            if self.total_pages == 0:
                self.total_pages = 1
            page_title = f'Page {self.current_page_number + 1}/{self.total_pages}'
        if not page_data and self.current_page_number > 0:
            if isinstance(self.data_source, list) or (self._async_iterator_exhausted and self.current_page_number >= (self.total_pages or 0)):
                return ('This page is empty or out of bounds.', discord.Embed(description='No content on this page.', color=discord.Color.orange()))
        if self.content_type == 'embeds':
            if not page_data:
                return (None, discord.Embed(title=page_title, description='No embeds on this page.', color=discord.Color.blue()))
            if isinstance(page_data[0], discord.Embed):
                embed_to_show = page_data[0]
                if embed_to_show.footer.text is None or not f'Page {self.current_page_number + 1}' in embed_to_show.footer.text:
                    new_footer_text = f'Page {self.current_page_number + 1}'
                    if self.total_pages is not None:
                        new_footer_text += f'/{self.total_pages}'
                    if embed_to_show.footer.text:
                        new_footer_text = f'{embed_to_show.footer.text} - {new_footer_text}'
                    embed_to_show.set_footer(text=new_footer_text, icon_url=embed_to_show.footer.icon_url)
                return (None, embed_to_show)
            else:
                return (None, discord.Embed(title=page_title, description="Invalid data for 'embeds' content type. Expected discord.Embed.", color=discord.Color.red()))
        elif self.content_type == 'text_lines':
            embed = discord.Embed(title=page_title, color=discord.Color.blue())
            if not page_data:
                embed.description = 'No text lines on this page.'
            else:
                processed_lines = [str(item) for item in page_data]
                embed.description = '\n'.join(processed_lines)
            if len(embed.description) > 4096:
                embed.description = embed.description[:4093] + '...'
            return (None, embed)
        elif self.content_type == 'generic':
            if self.formatter_func:
                try:
                    formatted_output = self.formatter_func(page_data, self.current_page_number, self)
                    if isinstance(formatted_output, tuple):
                        return (formatted_output[0], formatted_output[1])
                    elif isinstance(formatted_output, discord.Embed):
                        return (None, formatted_output)
                    elif isinstance(formatted_output, str):
                        return (formatted_output, None)
                    else:
                        return (f'Invalid format from formatter_func: {type(formatted_output)}', None)
                except Exception as e:
                    print(f'Error in custom formatter_func: {e}')
                    return (f'Error formatting page: {e}', discord.Embed(title='Formatting Error', description=str(e), color=discord.Color.red()))
            else:
                embed = discord.Embed(title=page_title, color=discord.Color.greyple())
                description = '\n'.join((str(item) for item in page_data))
                if not description:
                    description = 'No items on this page.'
                embed.description = description[:4096]
                return (None, embed)
        return ('Invalid content_type specified.', None)

    async def _update_view_internals(self):
        """
        Called after page data is fetched and formatted.
        Updates internal state like current_page_content/embed and button states.
        """
        self.current_page_content, self.current_page_embed = await self.format_page()
        await self._update_button_states()

    async def _navigate(self, interaction: discord.Interaction):
        """Common navigation logic after page number changes."""
        await self._update_view_internals()
        await interaction.response.edit_message(content=self.current_page_content, embed=self.current_page_embed, view=self)

    async def go_to_first_page(self, interaction: discord.Interaction):
        if self.current_page_number > 0:
            self.current_page_number = 0
            await self._navigate(interaction)
        else:
            await interaction.response.defer()

    async def go_to_previous_page(self, interaction: discord.Interaction):
        if self.current_page_number > 0:
            self.current_page_number -= 1
            await self._navigate(interaction)
        else:
            await interaction.response.defer()

    async def go_to_next_page(self, interaction: discord.Interaction):
        can_go_next = True
        if self.total_pages is not None:
            can_go_next = self.current_page_number < self.total_pages - 1
        elif self._async_iterator_exhausted:
            can_go_next = False
        if can_go_next:
            next_page_data_peek = await self._get_page_data(self.current_page_number + 1)
            if next_page_data_peek:
                self.current_page_number += 1
                await self._navigate(interaction)
            elif self._async_iterator_exhausted:
                await self._update_button_states()
                await interaction.response.edit_message(view=self)
            else:
                await interaction.response.defer()
        else:
            await interaction.response.defer()

    async def go_to_last_page(self, interaction: discord.Interaction):
        if self.total_pages is None and (not self._async_iterator_exhausted):
            deferred = False
            if not interaction.response.is_done():
                if len(self._async_buffer) < 5 * self.items_per_page:
                    await interaction.response.defer()
                    deferred = True
            while not self._async_iterator_exhausted:
                if hasattr(self.data_source, '__anext__'):
                    try:
                        await self._get_page_data(len(self._async_buffer) // self.items_per_page + 10)
                        if not self._async_buffer:
                            break
                    except StopAsyncIteration:
                        self._async_iterator_exhausted = True
                        break
                else:
                    self._async_iterator_exhausted = True
                    break
            if self.total_pages is None:
                self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page) if len(self._async_buffer) > 0 else 1
        if self.total_pages is not None and self.current_page_number < self.total_pages - 1:
            self.current_page_number = self.total_pages - 1
            if deferred and interaction.response.is_done():
                await self._update_view_internals()
                await interaction.followup.send(content=self.current_page_content, embed=self.current_page_embed, view=self)
                try:
                    await interaction.edit_original_response(content=self.current_page_content, embed=self.current_page_embed, view=self)
                except discord.NotFound:
                    pass
                return
            if not interaction.response.is_done():
                await self._navigate(interaction)
            else:
                await self._update_view_internals()
                await interaction.edit_original_response(content=self.current_page_content, embed=self.current_page_embed, view=self)
        elif not interaction.response.is_done():
            await interaction.response.defer()

    async def stop_pagination(self, interaction: discord.Interaction):
        self.stop()
        if self.show_page_buttons:
            buttons_to_disable = [self.first_page_button, self.prev_page_button, self.next_page_button, self.last_page_button, self.stop_button]
            for button in buttons_to_disable:
                if button:
                    button.disabled = True
        try:
            await interaction.response.edit_message(content=self.current_page_content, embed=self.current_page_embed, view=self)
        except discord.InteractionResponded:
            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.HTTPException:
                    pass
        except discord.HTTPException:
            pass

    async def send_initial_message(self, interaction_or_ctx: Union[discord.Interaction, discord.abc.Messageable]) -> discord.Message:
        """
        Sends the first page of the paginator.
        Can be called with an Interaction (for slash commands) or a Context/Channel (for message commands).
        """
        await self._update_view_internals()
        if isinstance(interaction_or_ctx, discord.Interaction):
            if not interaction_or_ctx.response.is_done():
                await interaction_or_ctx.response.send_message(content=self.current_page_content, embed=self.current_page_embed, view=self)
                self.message = await interaction_or_ctx.original_response()
            else:
                self.message = await interaction_or_ctx.followup.send(content=self.current_page_content, embed=self.current_page_embed, view=self, wait=True)
        elif hasattr(interaction_or_ctx, 'send'):
            self.message = await interaction_or_ctx.send(content=self.current_page_content, embed=self.current_page_embed, view=self)
        else:
            raise TypeError('interaction_or_ctx must be discord.Interaction or a messageable object.')
        return self.message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id:
            if interaction.user.id != self.author_id:
                await interaction.response.send_message('You are not allowed to interact with this.', ephemeral=True)
                return False
        return True

    async def on_timeout(self) -> None:
        if self.message and (not self.is_finished()):
            pass
        await super().on_timeout()

async def main_test():
    list_data = [f'Item {i}' for i in range(25)]

    async def async_gen():
        for i in range(13):
            await asyncio.sleep(0.01)
            yield f'Async Item {i}'
if __name__ == '__main__':
    import asyncio
    pass
