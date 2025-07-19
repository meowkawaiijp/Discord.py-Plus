import asyncio
import discord
from discord import ui
from typing import Optional, List, Union, cast, TYPE_CHECKING, TypeVar, Generic, Any
if TYPE_CHECKING:
    from ..core.context import EnhancedContext
T = TypeVar('T')

class EnhancedView(ui.View):

    def __init__(self, timeout: Optional[float]=180.0):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def on_timeout(self) -> None:
        if self._closed:
            return
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            await self.disable_all_components()
            await self.on_custom_timeout()
            self.stop()

    async def disable_all_components(self) -> None:
        for item in self.children:
            if hasattr(item, 'disabled') and isinstance(item, (ui.Button, ui.Select, ui.TextInput)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                pass

    async def on_custom_timeout(self) -> None:
        """タイムアウト時にサブクラスでオーバーライドされるカスタム処理。"""
        pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item[Any]) -> None:
        """インタラクション処理中にエラーが発生した際のデフォルトハンドラ。"""
        if interaction.response.is_done():
            await interaction.followup.send('エラーが発生しました。しばらくしてからもう一度お試しください。', ephemeral=True)
        else:
            await interaction.response.send_message('エラーが発生しました。しばらくしてからもう一度お試しください。', ephemeral=True)
        self.stop()

class TimeoutSelect(ui.Select):

    def __init__(self, options: List[discord.SelectOption], placeholder: str='選択してください...', **kwargs):
        min_values = kwargs.pop('min_values', 1)
        max_values = kwargs.pop('max_values', 1)
        custom_id = kwargs.pop('custom_id', f'timeout_select_{discord.utils.generate_snowflake()}')
        super().__init__(placeholder=placeholder, min_values=min_values, max_values=max_values, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        if isinstance(self.view, InteractiveSelect):
            view = cast(InteractiveSelect, self.view)
            view.selected_value = self.values[0] if len(self.values) == 1 and self.max_values == 1 else self.values
            view.interaction = interaction
            view.stop()
            await interaction.response.defer()
        else:
            await interaction.response.send_message('内部エラーが発生しました。', ephemeral=True)

class InteractiveSelect(EnhancedView):

    def __init__(self, options: List[discord.SelectOption], placeholder: str='選択してください...', timeout: float=30.0, *, require_original_user: bool=True, min_values: int=1, max_values: int=1):
        super().__init__(timeout=timeout)
        self.selected_value: Optional[Union[str, List[str]]] = None
        self.interaction: Optional[discord.Interaction] = None
        self.original_user_id: Optional[int] = None
        self.require_original_user = require_original_user
        self.add_item(TimeoutSelect(options, placeholder, min_values=min_values, max_values=max_values))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.require_original_user and self.original_user_id is not None:
            if interaction.user.id != self.original_user_id:
                await interaction.response.send_message('この操作は元のコマンド実行者のみが行えます。', ephemeral=True)
                return False
        return True

    async def prompt(self, ctx: 'EnhancedContext', message_content: str, **kwargs) -> Optional[Union[str, List[str]]]:
        """選択メニューを含むメッセージを送信し、ユーザーの選択を待つ。"""
        if ctx.author:
            self.original_user_id = ctx.author.id
        embed = discord.Embed(description=message_content, color=discord.Color.blue())
        ephemeral = kwargs.pop('ephemeral', False)
        if ctx.interaction and (not ctx.interaction.response.is_done()):
            await ctx.interaction.response.send_message(embed=embed, view=self, ephemeral=ephemeral, **kwargs)
            self.message = await ctx.interaction.original_response()
        else:
            self.message = await ctx.send(embed=embed, view=self, ephemeral=ephemeral, **kwargs)
        await self.wait()
        return self.selected_value

class PageButton(ui.Button['AdvancedSelect']):

    def __init__(self, *, emoji: Optional[Union[str, discord.Emoji, discord.PartialEmoji]], style: discord.ButtonStyle, row: Optional[int]=None, callback_action: str):
        super().__init__(style=style, emoji=emoji, row=row, custom_id=f'page_button_{callback_action}_{discord.utils.generate_snowflake()}')
        self.callback_action = callback_action

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view = self.view
        if self.callback_action == 'prev':
            await view.go_to_previous_page(interaction)
        elif self.callback_action == 'next':
            await view.go_to_next_page(interaction)

class AdvancedSelectMenu(ui.Select['AdvancedSelect']):

    def __init__(self, *, options: List[discord.SelectOption], placeholder: str, max_values: int, custom_id_suffix: str):
        super().__init__(options=options, placeholder=placeholder, max_values=max_values, min_values=1, custom_id=f'advanced_select_menu_{custom_id_suffix}_{discord.utils.generate_snowflake()}')

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view = self.view
        view.selected_values = self.values
        for item_in_view in view.children:
            if hasattr(item_in_view, 'disabled'):
                item_in_view.disabled = True
        await interaction.response.edit_message(view=view)
        view.stop()

class AdvancedSelect(EnhancedView):

    def __init__(self, options: List[discord.SelectOption], *, page_size: int=20, placeholder: str='選択してください...', timeout: float=180.0, require_original_user: bool=True, max_selectable_values: int=1):
        super().__init__(timeout=timeout)
        self.current_page = 0
        self.all_options = options
        self.page_size = min(page_size, 25)
        self.placeholder = placeholder
        self.selected_values: List[str] = []
        self.original_user_id: Optional[int] = None
        self.require_original_user = require_original_user
        self.max_selectable_values = max_selectable_values
        self.total_pages = (len(self.all_options) + self.page_size - 1) // self.page_size
        self._update_components()

    def _get_current_page_options(self) -> List[discord.SelectOption]:
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.all_options[start:end]

    def _update_components(self):
        self.clear_items()
        current_options = self._get_current_page_options()
        if not current_options:
            pass
        else:
            select_menu_max_values = min(len(current_options), self.max_selectable_values)
            self.add_item(AdvancedSelectMenu(options=current_options, placeholder=f'{self.placeholder} (Page {self.current_page + 1}/{self.total_pages})', max_values=select_menu_max_values, custom_id_suffix=f'p{self.current_page}'))
        if self.total_pages > 1:
            prev_button = PageButton(emoji='◀️', style=discord.ButtonStyle.secondary, callback_action='prev', row=1)
            next_button = PageButton(emoji='▶️', style=discord.ButtonStyle.secondary, callback_action='next', row=1)
            prev_button.disabled = self.current_page == 0
            next_button.disabled = self.current_page >= self.total_pages - 1
            self.add_item(prev_button)
            self.add_item(next_button)

    async def go_to_previous_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_components()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    async def go_to_next_page(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_components()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.require_original_user and self.original_user_id is not None:
            if interaction.user.id != self.original_user_id:
                await interaction.response.send_message('この操作は元のコマンド実行者のみが行えます。', ephemeral=True)
                return False
        return True

    async def prompt(self, ctx: 'EnhancedContext', message_content: str, **kwargs) -> Optional[List[str]]:
        if ctx.author:
            self.original_user_id = ctx.author.id
        embed = discord.Embed(description=message_content, color=discord.Color.blue())
        ephemeral = kwargs.pop('ephemeral', False)
        if ctx.interaction and (not ctx.interaction.response.is_done()):
            await ctx.interaction.response.send_message(embed=embed, view=self, ephemeral=ephemeral, **kwargs)
            self.message = await ctx.interaction.original_response()
        else:
            self.message = await ctx.send(embed=embed, view=self, ephemeral=ephemeral, **kwargs)
        await self.wait()
        return self.selected_values

class JumpToPageModal(discord.ui.Modal):

    def __init__(self, title: str='Jump to Page', paginator_view: Any=None):
        super().__init__(title=title)
        self.paginator_view = paginator_view
        self.page_number_input = discord.ui.TextInput(label='Page Number', placeholder=f"Enter page (1-{(self.paginator_view.total_pages if hasattr(self.paginator_view, 'total_pages') and self.paginator_view.total_pages is not None else '?')})", required=True, min_length=1, max_length=len(str(self.paginator_view.total_pages)) + 2 if hasattr(self.paginator_view, 'total_pages') and self.paginator_view.total_pages is not None else 7)
        self.add_item(self.page_number_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.paginator_view:
            await interaction.response.send_message('Error: Paginator context lost.', ephemeral=True)
            return
        try:
            page_num_str = self.page_number_input.value
            page_num_target = int(page_num_str) - 1
            total_pages = getattr(self.paginator_view, 'total_pages', None)
            is_exhausted = getattr(self.paginator_view, '_async_iterator_exhausted', False)
            min_page = 0
            if total_pages is None and (not is_exhausted):
                if page_num_target < min_page:
                    await interaction.response.send_message(f'Page number must be positive.', ephemeral=True)
                    return
            elif total_pages is not None:
                if not min_page <= page_num_target < total_pages:
                    await interaction.response.send_message(f'Invalid page number. Please enter a number between 1 and {total_pages}.', ephemeral=True)
                    return
            elif is_exhausted and total_pages is None:
                await interaction.response.send_message(f'Cannot determine total pages yet.', ephemeral=True)
                return
            self.paginator_view.current_page_number = page_num_target
            if hasattr(self.paginator_view, '_navigate'):
                await self.paginator_view._navigate(interaction)
            else:
                await interaction.response.send_message('Error: Navigation function not found in paginator.', ephemeral=True)
        except ValueError:
            await interaction.response.send_message('Invalid input. Please enter a valid page number.', ephemeral=True)
        except Exception as e:
            print(f'Error in JumpToPageModal on_submit: {e}')
            if not interaction.response.is_done():
                await interaction.response.send_message('An error occurred while processing the page number.', ephemeral=True)
            else:
                await interaction.followup.send('An error occurred while processing the page number.', ephemeral=True)
__all__ = ['EnhancedView', 'InteractiveSelect', 'AdvancedSelect', 'TimeoutSelect', 'PageButton', 'AdvancedSelectMenu', 'JumpToPageModal']
