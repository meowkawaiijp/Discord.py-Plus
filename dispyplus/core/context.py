import discord
from discord.ext import commands
import datetime
from typing import Optional, Callable, Awaitable, Type, List, Any, Union, AsyncIterator, Tuple, Literal, TYPE_CHECKING, Dict
from .enums import InteractionType
if TYPE_CHECKING:
    from ..ui.views import ConfirmationView
    from ..ui.pagination import PaginatorView
    from ..ui.forms import DispyplusForm

class EnhancedContext(commands.Context):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def interaction_type(self) -> InteractionType:
        if self.interaction:
            if self.interaction.type == discord.InteractionType.application_command:
                return InteractionType.SLASH_COMMAND
            elif self.interaction.type == discord.InteractionType.message_component:
                return InteractionType.MESSAGE_COMPONENT
            elif self.interaction.type == discord.InteractionType.modal_submit:
                return InteractionType.MODAL_SUBMIT
        return InteractionType.UNKNOWN

    @property
    def created_at(self) -> datetime.datetime:
        return self.message.created_at

    @property
    def is_dm(self) -> bool:
        return self.guild is None

    async def success(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f'✅ {message}', color=discord.Color.green())
        return await self.send(embed=embed, **kwargs)

    async def warning(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f'⚠️ {message}', color=discord.Color.yellow())
        return await self.send(embed=embed, **kwargs)

    async def error(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f'❌ {message}', color=discord.Color.red())
        return await self.send(embed=embed, **kwargs)

    async def unknown(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f'❓ {message}', color=discord.Color.dark_grey())
        return await self.send(embed=embed, **kwargs)

    async def info(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f'ℹ️ {message}', color=discord.Color.blue())
        return await self.send(embed=embed, **kwargs)

    async def ask(self, message: str, *, timeout: float=180.0, interaction_check: Optional[Callable[[discord.Interaction], Awaitable[bool]]]=None, embed_color: discord.Color=discord.Color.gold(), **kwargs) -> Optional[bool]:
        from ..ui.views import ConfirmationView as DispyplusConfirmationView
        view = DispyplusConfirmationView(timeout=timeout, interaction_check=interaction_check)
        if self.author:
            view.set_original_user_id(self.author.id)
        else:
            pass
        embed = discord.Embed(description=f'❓ {message}', color=embed_color)
        ephemeral = kwargs.pop('ephemeral', False)
        sent_message: Optional[discord.Message] = None
        if self.interaction and (not self.interaction.response.is_done()):
            await self.interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral, **kwargs)
            sent_message = await self.interaction.original_response()
        else:
            sent_message = await self.send(embed=embed, view=view, **kwargs)
        if sent_message:
            view.message = sent_message
        await view.wait()
        return view.value

    async def respond(self, *args, **kwargs) -> Optional[discord.Message]:
        """インタラクション対応の応答メソッド"""
        if self.interaction and (not self.interaction.response.is_done()):
            await self.interaction.response.send_message(*args, **kwargs)
            try:
                return await self.interaction.original_response()
            except discord.NotFound:
                return None
        if self.interaction and self.interaction.response.is_done() and kwargs.get('ephemeral'):
            if hasattr(self.interaction, 'followup'):
                return await self.interaction.followup.send(*args, **kwargs)
            else:
                kwargs.pop('ephemeral', None)
                return await super().send(*args, **kwargs)
        return await super().send(*args, **kwargs)

    async def send_webhook(self, url: str, *args, **kwargs) -> Optional[discord.Message]:
        """
        このコンテキストに関連するBotインスタンスを使用してWebhookを送信します。
        引数は DispyplusBot.send_webhook と同じです。
        """
        if not hasattr(self.bot, 'send_webhook'):
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error("Bot instance does not have 'send_webhook'. Are you using DispyplusBot?")
            raise AttributeError("The bot instance does not have a 'send_webhook' method. Ensure you are using DispyplusBot.")
        return await self.bot.send_webhook(url, *args, **kwargs)

    async def paginate(self, data_source: Union[List[Any], AsyncIterator[Any]], items_per_page: int=10, *, content_type: Literal['embeds', 'text_lines', 'generic']='generic', formatter_func: Optional[Callable[[List[Any], int, 'PaginatorView'], Union[str, discord.Embed, Tuple[Optional[str], Optional[discord.Embed]]]]]=None, show_page_buttons: bool=True, timeout: Optional[float]=180.0, initial_message_content: Optional[str]=None) -> Optional[discord.Message]:
        """
        Sends a paginated message using AdvancedPaginatorView.

        Args:
            data_source: The data to paginate (list or async iterator).
            items_per_page: Number of items per page.
            content_type: Type of content ('embeds', 'text_lines', 'generic').
            formatter_func: Custom function to format pages for 'generic' type.
                           Signature: (items_on_page, page_num, view_instance) -> Union[str, discord.Embed, Tuple[Optional[str], Optional[discord.Embed]]]
            show_page_buttons: Whether to show navigation buttons.
            timeout: Timeout for the view in seconds.
            initial_message_content: Optional text to send before the paginator (e.g., "Here are your results:").

        Returns:
            The discord.Message object for the paginator, or None if sending failed.
        """
        from ..ui.pagination import PaginatorView
        import inspect
        if self.interaction and initial_message_content and (not self.interaction.response.is_done()):
            pass
        view = PaginatorView(data_source=data_source, items_per_page=items_per_page, formatter_func=formatter_func, content_type=content_type, show_page_buttons=show_page_buttons, timeout=timeout, author_id=self.author.id if self.author else None)
        try:
            if self.interaction and initial_message_content and (not self.interaction.response.is_done()):
                await self.interaction.response.send_message(initial_message_content)
                message = await view.send_initial_message(self.interaction.followup)
            else:
                message = await view.send_initial_message(self)
            return message
        except Exception as e:
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error(f'Error sending paginated message: {e}', exc_info=True)
            return None

    async def ask_form(self, form_class: Type['DispyplusForm'], *, title: Optional[str]=None, timeout: Optional[float]=180.0, **kwargs_for_form_init: Any) -> Optional[Dict[str, Any]]:
        """
        Displays a DispyplusForm modal to the user and waits for submission.

        Args:
            form_class: The subclass of DispyplusForm to display.
            title: Optional title for the modal, overrides form_class.form_title.
            timeout: Optional timeout for the modal.
            **kwargs_for_form_init: Additional keyword arguments to pass to the form's constructor.
                                   (Note: ctx is automatically passed if form_class.__init__ accepts it)

        Returns:
            A dictionaryตำรวจof submitted data if the form was successfully submitted,
            None if the form timed out or was cancelled (e.g., due to validation error feedback
            not leading to a resubmit, or an internal error before future is set).
            May raise an exception if an error occurred within process_form_data and was set on the future.
        """
        if not self.interaction:
            if hasattr(self.bot, 'logger'):
                self.bot.logger.warning('ask_form called without an active interaction. Modals require interactions.')
            pass
        form_init_params = inspect.signature(form_class.__init__).parameters
        if 'ctx' in form_init_params:
            kwargs_for_form_init['ctx'] = self
        form_instance = form_class(title=title, timeout=timeout, **kwargs_for_form_init)
        if not self.interaction:
            await self.send('Forms can only be used with slash commands or component interactions.')
            return None
        await self.interaction.response.send_modal(form_instance)
        try:
            result = await form_instance.future
            return result
        except Exception as e:
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error(f"Exception caught while waiting for form '{form_class.__name__}': {e}", exc_info=True)
            raise
