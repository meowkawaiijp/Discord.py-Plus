# Dispyplus: EnhancedContextを提供するモジュール
import discord
from discord.ext import commands
import datetime
from typing import Optional, Callable, Awaitable, Type, List, Any, Union, AsyncIterator, Tuple, Literal, TYPE_CHECKING, Dict # Ensure Type and Dict is imported at the top level

# InteractionTypeを新しいenumsモジュールからインポート
from .enums import InteractionType
# uiモジュールからのインポート (循環参照を避けるためTYPE_CHECKINGを使用)
# from typing import TYPE_CHECKING, List, Any, Union, AsyncIterator, Tuple, Literal # Moved Type to main import

if TYPE_CHECKING:
    from ..ui.views import ConfirmationView # ConfirmationViewの具体的なパスはui.pyの構造による
    from ..ui.pagination import AdvancedPaginatorView # For type hinting in paginate method arguments
    from ..ui.forms import DispyplusForm # Direct import in TYPE_CHECKING is fine

class EnhancedContext(commands.Context):
    """
    An enhanced version of `discord.ext.commands.Context`.

    This class provides additional utility methods and properties to simplify
    common bot interactions and responses. It is intended to be used as the
    default context type by `DispyplusBot`.

    Properties:
        interaction_type (InteractionType): Determines how the command was invoked
            (e.g., slash command, message component).
        created_at (datetime.datetime): The creation time of the original message.
        is_dm (bool): True if the context is in a DM channel, False otherwise.

    Methods:
        success(message, **kwargs): Sends an embed-styled success message.
        warning(message, **kwargs): Sends an embed-styled warning message.
        error(message, **kwargs): Sends an embed-styled error message.
        info(message, **kwargs): Sends an embed-styled informational message.
        unknown(message, **kwargs): Sends an embed-styled message for unknown states.
        ask(message, **kwargs): Prompts the user with a yes/no confirmation dialog.
        # paginate(data, **kwargs): Starts a paginator UI for the given data. (Paginatorの移動先によって調整)
        respond(*args, **kwargs): Sends a response, handling interactions appropriately.
        send_webhook(url, *args, **kwargs): Sends a message via webhook using the bot instance.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.interaction は discord.py の Context で適切に設定される

    @property
    def interaction_type(self) -> InteractionType:
        """
        現在のコンテキストがどの種類のインタラクションから生成されたかを返します。
        インタラクションでない場合 (通常のメッセージコマンドなど) は UNKNOWN を返します。
        """
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
        """メッセージの作成日時を返す"""
        return self.message.created_at

    @property
    def is_dm(self) -> bool:
        """DMかどうかを判定する"""
        return self.guild is None

    async def success(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f"✅ {message}", color=discord.Color.green())
        return await self.send(embed=embed, **kwargs)

    async def warning(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f"⚠️ {message}", color=discord.Color.yellow())
        return await self.send(embed=embed, **kwargs)

    async def error(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f"❌ {message}", color=discord.Color.red())
        return await self.send(embed=embed, **kwargs)

    async def unknown(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f"❓ {message}", color=discord.Color.dark_grey()) # Color変更
        return await self.send(embed=embed, **kwargs)

    async def info(self, message: str, **kwargs) -> discord.Message:
        embed = discord.Embed(description=f"ℹ️ {message}", color=discord.Color.blue())
        return await self.send(embed=embed, **kwargs)

    async def ask(self, message: str, *, timeout: float = 180.0, interaction_check: Optional[Callable[[discord.Interaction], Awaitable[bool]]] = None, embed_color: discord.Color = discord.Color.gold(), **kwargs) -> Optional[bool]:
        # .ui から ConfirmationView をインポート (循環参照を避けるため遅延インポート)
        from ..ui.views import ConfirmationView as DispyplusConfirmationView

        view = DispyplusConfirmationView(timeout=timeout, interaction_check=interaction_check)
        if self.author: # authorが存在することを確認
            view.set_original_user_id(self.author.id)
        else:
            # authorがいない場合（例：Webhook経由のインタラクションなど特殊ケース）の処理
            # interaction_checkが設定されていなければ、操作不能になる可能性がある
            # logging.warning("EnhancedContext.ask called without a valid author.")
            pass


        embed = discord.Embed(description=f"❓ {message}", color=embed_color)
        ephemeral = kwargs.pop('ephemeral', False)

        sent_message: Optional[discord.Message] = None
        if self.interaction and not self.interaction.response.is_done():
            await self.interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral, **kwargs)
            sent_message = await self.interaction.original_response()
        else:
            sent_message = await self.send(embed=embed, view=view, **kwargs)

        if sent_message: # viewにmessageオブジェクトをセット
            view.message = sent_message


        await view.wait()
        return view.value

    async def respond(self, *args, **kwargs) -> Optional[discord.Message]:
        """インタラクション対応の応答メソッド"""
        if self.interaction and not self.interaction.response.is_done():
            await self.interaction.response.send_message(*args, **kwargs)
            try:
                return await self.interaction.original_response()
            except discord.NotFound: # フォローアップメッセージの場合など
                return None
        # interactionがないか、既にレスポンス済みの場合
        # ephemeralなメッセージを編集しようとするとエラーになるため、try-exceptを追加
        if self.interaction and self.interaction.response.is_done() and kwargs.get('ephemeral'):
             # ephemeralなインタラクションへのフォローアップは interaction.followup.send を使う
            if hasattr(self.interaction, 'followup'):
                return await self.interaction.followup.send(*args, **kwargs)
            else: # フォローアップがない古いバージョンの可能性（または特殊なケース）
                  # この場合は通常のsendにフォールバックするが、ephemeralは無視される
                  kwargs.pop('ephemeral', None) # ephemeral引数を除去
                  return await super().send(*args, **kwargs)

        return await super().send(*args, **kwargs)


    async def send_webhook(self, url: str, *args, **kwargs) -> Optional[discord.Message]:
        """
        このコンテキストに関連するBotインスタンスを使用してWebhookを送信します。
        引数は DispyplusBot.send_webhook と同じです。
        """
        if not hasattr(self.bot, 'send_webhook'):
            # loggerが使えるようにbotの型をチェック
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error("Bot instance does not have 'send_webhook'. Are you using DispyplusBot?") # type: ignore
            raise AttributeError("The bot instance does not have a 'send_webhook' method. Ensure you are using DispyplusBot.")
        return await self.bot.send_webhook(url, *args, **kwargs) # type: ignore


    async def paginate(
        self,
        data_source: Union[List[Any], AsyncIterator[Any]],
        items_per_page: int = 10,
        *,
        content_type: Literal["embeds", "text_lines", "generic"] = "generic",
        formatter_func: Optional[Callable[[List[Any], int, "AdvancedPaginatorView"], Union[str, discord.Embed, Tuple[Optional[str], Optional[discord.Embed]]]]] = None,
        show_page_buttons: bool = True,
        # show_page_select: bool = False, # Future options
        # show_jump_button: bool = False, # Future options
        timeout: Optional[float] = 180.0,
        initial_message_content: Optional[str] = None # Optional text to send with the first page
    ) -> Optional[discord.Message]:
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
        # Defer import to avoid circular dependencies at module load time
        from ..ui.pagination import AdvancedPaginatorView
        # For type hinting ask_form
        # from typing import Dict, Any, Type # Already imported at top level
        import inspect # For checking form_class.__init__ signature
        # TYPE_CHECKING block for DispyplusForm is already at the top of the file.


        if self.interaction and initial_message_content and not self.interaction.response.is_done():
            # If there's initial content and we haven't responded to interaction yet,
            # send the initial content first, then the paginator as a followup.
            # This is one way to handle it; another is to pass initial_message_content to the view.
            # For simplicity, let's assume initial_message_content is part of the first page if not handled here.
            # However, AdvancedPaginatorView doesn't directly support initial_message_content for the *first* message.
            # It expects to send its own content/embed.
            # A simple solution: if initial_message_content, send it, then paginator.
            # This requires the paginator to be sent as a new message or followup.

            # If we need to send a message BEFORE the paginator view itself (e.g. as a header):
            # This approach means the paginator will be a *separate* message or a followup.
            # For now, this example will integrate initial_message_content into the first page of the paginator
            # if the formatter or content type allows. The current AdvancedPaginatorView's format_page
            # would need to be aware of this or the helper here would pre-format.
            # Let's assume initial_message_content is for the message *containing* the paginator.
            pass


        view = AdvancedPaginatorView(
            data_source=data_source,
            items_per_page=items_per_page,
            formatter_func=formatter_func,
            content_type=content_type,
            show_page_buttons=show_page_buttons,
            timeout=timeout,
            author_id=self.author.id if self.author else None
        )

        # The AdvancedPaginatorView's send_initial_message will handle interaction vs regular context.
        # If initial_message_content is provided, and we are in an interaction that hasn't been responded to,
        # we might need to send the initial_message_content as part of the first response.
        # This is a bit complex due to how interactions expect a single initial response.

        # Simplification: AdvancedPaginatorView's first page content/embed IS the initial message.
        # If `initial_message_content` is provided, it will be IGNORED by this basic helper,
        # unless the user's `formatter_func` incorporates it.
        # A more advanced helper might send `initial_message_content` first if `ctx.send` is used,
        # and then send the paginator. For interactions, it's trickier.

        try:
            # If there's an interaction and initial_message_content, and we haven't responded:
            if self.interaction and initial_message_content and not self.interaction.response.is_done():
                 await self.interaction.response.send_message(initial_message_content)
                 # Now the paginator must be a followup
                 message = await view.send_initial_message(self.interaction.followup) # type: ignore
            else:
                 message = await view.send_initial_message(self) # Pass context/interaction to view's sender
            return message
        except Exception as e:
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error(f"Error sending paginated message: {e}", exc_info=True) # type: ignore
            return None

    async def ask_form(
        self,
        form_class: Type['DispyplusForm'], # Use string literal for forward reference
        *,
        title: Optional[str] = None,
        timeout: Optional[float] = 180.0,
        **kwargs_for_form_init: Any
    ) -> Optional[Dict[str, Any]]:
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
            # Modals can only be sent in response to an interaction.
            # Consider raising an error or logging a warning.
            if hasattr(self.bot, 'logger'):
                self.bot.logger.warning("ask_form called without an active interaction. Modals require interactions.") # type: ignore
            # For now, let's allow it to proceed; send_modal will fail if not an interaction context.
            # A better approach might be to check self.interaction_type.
            # if self.interaction_type == InteractionType.UNKNOWN:
            #     raise TypeError("Cannot send a modal from a non-interaction context.")
            # However, this check might be too restrictive if used in hybrid commands responding to messages.
            # The discord.py library itself will raise if send_modal is misused.
            # For now, let it pass to discord.py's handling.
            pass

        # Check if 'ctx' is an expected argument in the form's __init__
        form_init_params = inspect.signature(form_class.__init__).parameters
        if 'ctx' in form_init_params:
            kwargs_for_form_init['ctx'] = self

        form_instance = form_class(title=title, timeout=timeout, **kwargs_for_form_init)

        if not self.interaction: # Should have been caught by discord.py before this
            await self.send("Forms can only be used with slash commands or component interactions.")
            return None

        await self.interaction.response.send_modal(form_instance)

        try:
            # Wait for the future to be resolved by on_submit, on_error, or on_timeout
            result = await form_instance.future
            return result
        except Exception as e:
            # If future had an exception set (e.g., from process_form_data error)
            if hasattr(self.bot, 'logger'):
                self.bot.logger.error(f"Exception caught while waiting for form '{form_class.__name__}': {e}", exc_info=True) # type: ignore
            # Optionally re-raise or return None/error indicator
            # For now, re-raising to make errors visible.
            raise
        # Timeout or other non-exception future results (like None from validation fail leading to no data) handled by 'result'
