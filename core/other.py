import asyncio
import datetime
import logging
from typing import Optional, List, Union, Callable, TypeVar, Generic, cast
import discord
from discord.ext import commands
from enum import Enum, auto

T = TypeVar('T')

class InteractionType(Enum):
    """インタラクションの種類を示す列挙型です。
    EnhancedContext.interaction_type で使用されます。
    """
    UNKNOWN = auto() #: 不明なインタラクションタイプ。
    SLASH_COMMAND = auto() #: スラッシュコマンドまたはコンテキストメニューコマンド。
    MESSAGE_COMPONENT = auto() #: ボタン、選択メニューなどのメッセージコンポーネント。
    MODAL_SUBMIT = auto() #: モーダル送信。


class EnhancedView(discord.ui.View):
    def __init__(self, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def on_timeout(self) -> None:
        if self._closed:
            return

        async with self._lock:
            self._closed = True
            await self.disable_all_components()
            await self.on_custom_timeout()

    async def disable_all_components(self) -> None:
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                logging.error(f"View update error: {e}")

    async def on_custom_timeout(self) -> None:
        """タイムアウト時に実行するカスタム処理"""
        pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        """インタラクション処理で発生したエラーのハンドリング

        エラーメッセージをログ出力し、ユーザーにはエラー通知を送信する。
        """
        logging.error(f"View interaction error: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "エラーが発生しました。しばらく経ってからもう一度お試しください。",
                ephemeral=True
            )

class Paginator(EnhancedView, Generic[T]):
    def __init__(
        self,
        data: List[T],
        per_page: int = 10,
        embed_template: Optional[Callable[[List[T], int], discord.Embed]] = None,
        button_style: discord.ButtonStyle = discord.ButtonStyle.primary,
        timeout: float = 120,
        owner_only: bool = False
    ):
        super().__init__(timeout=timeout)
        self.data = data
        self.per_page = max(1, per_page)  # 最低1項目／ページ
        self.current_page = 0
        self.embed_template = embed_template or self.default_embed
        self.total_pages = max(1, (len(data) + per_page - 1) // per_page)
        self.button_style = button_style
        self.owner_id: Optional[int] = None
        self.owner_only = owner_only

        # ページ数が1ページのみの場合、操作用ボタンを非表示にする
        if self.total_pages <= 1:
            self.clear_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """操作権限チェック

        ・所有者限定の場合、操作できるユーザーを制限する
        """
        if self.owner_only and self.owner_id and interaction.user.id != self.owner_id:
            await interaction.response.send_message("このページネーションを操作する権限がありません", ephemeral=True)
            return False
        return True

    def default_embed(self, page_data: List[T], page: int) -> discord.Embed:
        """デフォルトのEmbed生成処理

        ・各ページのデータを文字列として結合し、Embedにセットする
        """
        embed = discord.Embed(
            title=f"ページ {page + 1}/{self.total_pages}",
            description="\n".join(str(item) for item in page_data),
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"全 {len(self.data)} 項目")
        return embed

    def get_page_data(self, page: int) -> List[T]:
        """指定ページのデータを抽出する"""
        start = page * self.per_page
        end = start + self.per_page
        return self.data[start:end]

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """最初のページへ移動するボタンの処理"""
        if self.current_page == 0:
            await interaction.response.defer()
            return
        self.current_page = 0
        await self._update_view(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """前のページへ移動するボタンの処理"""
        if self.current_page == 0:
            await interaction.response.defer()
            return
        self.current_page = max(0, self.current_page - 1)
        await self._update_view(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """次のページへ移動するボタンの処理"""
        if self.current_page >= self.total_pages - 1:
            await interaction.response.defer()
            return
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        await self._update_view(interaction)

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """最後のページへ移動するボタンの処理"""
        if self.current_page >= self.total_pages - 1:
            await interaction.response.defer()
            return
        self.current_page = self.total_pages - 1
        await self._update_view(interaction)

    async def _update_view(self, interaction: discord.Interaction):
        """内部処理：ページ更新時のEmbedおよびボタン状態の更新"""
        try:
            # ボタンの有効/無効状態を更新
            self.first_page.disabled = self.current_page == 0
            self.prev_page.disabled = self.current_page == 0
            self.next_page.disabled = self.current_page >= self.total_pages - 1
            self.last_page.disabled = self.current_page >= self.total_pages - 1

            if interaction.response.is_done():
                await interaction.followup.edit_message(
                    message_id=self.message.id,
                    embed=self.embed_template(self.get_page_data(self.current_page), self.current_page),
                    view=self
                )
            else:
                await interaction.response.edit_message(
                    embed=self.embed_template(self.get_page_data(self.current_page), self.current_page),
                    view=self
                )
        except discord.HTTPException as e:
            logging.error(f"Paginator update error: {e}")

    @classmethod
    async def start(
        cls, 
        destination: Union[commands.Context, discord.Interaction], 
        *args, 
        **kwargs
    ) -> 'Paginator[T]':
        """ページネーターの初期表示を行い、開始する

        ・送信先（ContextまたはInteraction）にEmbedとUIを送信  
        ・送信先のユーザーを所有者として設定
        """
        instance = cls(*args, **kwargs)
        page_data = instance.get_page_data(0)
        embed = instance.embed_template(page_data, 0)

        # 最初のページでは前へ移動ボタンを無効化
        instance.first_page.disabled = True
        instance.prev_page.disabled = True

        # 1ページのみの場合は次へ移動ボタンも無効化
        if instance.total_pages <= 1:
            instance.next_page.disabled = True
            instance.last_page.disabled = True

        # 所有者の設定と送信処理
        if isinstance(destination, commands.Context):
            instance.owner_id = destination.author.id
            instance.message = await destination.send(embed=embed, view=instance)
        elif isinstance(destination, discord.Interaction):
            instance.owner_id = destination.user.id
            if destination.response.is_done():
                instance.message = await destination.followup.send(embed=embed, view=instance)
            else:
                await destination.response.send_message(embed=embed, view=instance)
                instance.message = await destination.original_response()

        return instance
class EnhancedContext(commands.Context):
    """拡張コンテキストクラス

    標準Contextに各種ユーティリティメソッドを追加。
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # The 'interaction' attribute is already provided by discord.py's Context
        # when the context is created from an interaction.
        # We just need to ensure our EnhancedContext correctly utilizes it.
        # self.interaction: Optional[discord.Interaction] = kwargs.get('interaction')

    @property
    def interaction_type(self) -> InteractionType:
        """
        現在のコンテキストがどの種類のインタラクションから生成されたかを返します。
        インタラクションでない場合 (通常のメッセージコマンドなど) は UNKNOWN を返します。

        Returns:
            InteractionType: インタラクションの種類。
        """
        if self.interaction:
            if self.interaction.type == discord.InteractionType.application_command:
                # Further check if it's a slash command or context menu command
                # For now, we'll broadly classify as SLASH_COMMAND
                return InteractionType.SLASH_COMMAND
            elif self.interaction.type == discord.InteractionType.message_component:
                return InteractionType.MESSAGE_COMPONENT
            elif self.interaction.type == discord.InteractionType.modal_submit:
                return InteractionType.MODAL_SUBMIT
            # Add more specific checks if needed, e.g., for autocomplete
            # elif self.interaction.type == discord.InteractionType.application_command_autocomplete:
            #     return InteractionType.AUTOCOMPLETE
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
        """成功メッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"✅ {message}",
            color=discord.Color.green()
        )
        return await self.send(embed=embed, **kwargs)

    async def warning(self, message: str, **kwargs) -> discord.Message:
        """警告メッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"⚠️ {message}",
            color=discord.Color.yellow()
        )
        return await self.send(embed=embed, **kwargs)
    
    async def error(self, message: str, **kwargs) -> discord.Message:
        """エラーメッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"❌ {message}",
            color=discord.Color.red()
        )
        return await self.send(embed=embed, **kwargs)
    async def unknown(self, message: str, **kwargs) -> discord.Message:
        """不明メッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"❓ {message}",
            color=discord.Color.red()
        )
        return await self.send(embed=embed, **kwargs)


    async def info(self, message: str, **kwargs) -> discord.Message:
        """情報メッセージをEmbedで送信する"""
        embed = discord.Embed(
            description=f"ℹ️ {message}",
            color=discord.Color.blue()
        )
        return await self.send(embed=embed, **kwargs)

    async def ask(self, message: str, **kwargs) -> Optional[bool]:
        """確認ダイアログを表示し、ユーザーの選択結果を待機する"""
        view = ConfirmationView(require_original_user=True)
        return await view.ask(self, message, **kwargs)

    async def paginate(self, data: List[T], **kwargs) -> Paginator[T]:
        """ページネーション表示を開始する"""

        return await Paginator.start(self, data, **kwargs)

    # discord.py 2.0+ Context.from_interaction is a staticmethod
    # We don't need to override from_interaction if the base class already sets .interaction
    # If we needed to customize context creation from an interaction, we would do it here.
    # For now, the default behavior of commands.Context.from_interaction should suffice
    # as it correctly populates the `interaction` attribute.

    # @classmethod
    # async def from_interaction(cls, interaction: discord.Interaction) -> 'EnhancedContext':
    #     """Interactionからコンテキストを生成"""
    #     # Call the superclass's from_interaction
    #     # ctx = await super().from_interaction(interaction) # This is not how it works.
    #     # The bot calls Bot.get_context, which then might call super().get_context
    #     # or directly commands.Context(interaction=interaction, ...)
    #     # For hybrid commands, ctx.interaction is automatically populated.
    #
    #     # We need to ensure that when the bot creates a context from an interaction,
    #     # it uses EnhancedContext. If it does, self.interaction will be set.
    #     # The bot's get_context method is already overridden to use EnhancedContext.
    #     # So, this explicit from_interaction might not be necessary unless we want to
    #     # add more custom logic during the creation from an interaction object directly.
    #
    #     # If this method were to be used, it should be:
    #     # context = await commands.Context.from_interaction(interaction) # Get a base context
    #     # enhanced_context = cls(message=context.message, bot=context.bot, view=context.view, interaction=interaction)
    #     # return enhanced_context
    #     # However, this is not the standard way. Bot.get_context is the main entry point.
    #     # Let's assume the base class or bot.get_context handles interaction assignment.
    #     pass


    async def respond(self, *args, **kwargs) -> Optional[discord.Message]:
        """インタラクション対応の応答メソッド"""
        if self.interaction and not self.interaction.response.is_done():
            await self.interaction.response.send_message(*args, **kwargs)
            return await self.interaction.original_response()
        return await super().send(*args, **kwargs)

class ConfirmationView(EnhancedView):
    """拡張確認ダイアログ

    ユーザーに対し、確認（はい/いいえ）の選択を促すUIを提供する。
    """
    def __init__(self, **kwargs):
        super().__init__(timeout=kwargs.get('timeout', 30))
        self.require_original_user = kwargs.get('require_original_user', True)
        self.original_user: Optional[discord.User] = None
        self.value: Optional[bool] = None
        self.custom_labels = kwargs.get('custom_labels', {})
        # ボタンラベルのカスタマイズ
        self.confirm_label = self.custom_labels.get('confirm', "はい")
        self.cancel_label = self.custom_labels.get('cancel', "いいえ")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """確認ダイアログの操作権限チェック

        ・オリジナルユーザー以外の操作を拒否する
        """
        if self.require_original_user and interaction.user != self.original_user:
            await interaction.response.send_message("この操作は実行できません", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認ボタンの処理"""
        button.label = self.confirm_label
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """キャンセルボタンの処理"""
        button.label = self.cancel_label
        self.value = False
        await interaction.response.defer()
        self.stop()

    async def ask(self, ctx: EnhancedContext, message: str, **kwargs) -> Optional[bool]:
        """確認ダイアログを表示し、ユーザーの選択結果を返す"""
        self.original_user = ctx.author
        # ボタンラベルの再設定（必要な場合）
        self.confirm_button.label = self.confirm_label
        self.cancel_button.label = self.cancel_label
        embed = discord.Embed(
            description=f"❓ {message}",
            color=discord.Color.gold()
        )
        self.message = await ctx.send(embed=embed, view=self, **kwargs)
        await self.wait()
        try:
            if self.message:
                await self.message.edit(view=None)
        except discord.NotFound:
            pass
        return self.value


class TimeoutSelect(discord.ui.Select):
    """タイムアウト付きセレクトメニュー

    指定された選択肢からユーザーに選択させ、タイムアウトを設定する
    """
    def __init__(self, options: List[discord.SelectOption], placeholder: str = "選択してください...", **kwargs):
        min_values = kwargs.pop('min_values', 1)
        max_values = kwargs.pop('max_values', 1)
        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """ユーザー選択後の処理"""
        view = cast(InteractiveSelect, self.view)
        view.selected_value = self.values[0] if len(self.values) == 1 else self.values
        view.interaction = interaction
        view.stop()
        await interaction.response.defer()


class InteractiveSelect(EnhancedView):
    """インタラクティブな選択UI

    ユーザーに対して選択メニューを提示し、その結果を返す
    """
    def __init__(
        self, 
        options: List[discord.SelectOption], 
        placeholder: str = "選択してください...", 
        timeout: float = 30,
        **kwargs
    ):
        super().__init__(timeout=timeout)
        self.selected_value: Optional[Union[str, List[str]]] = None
        self.interaction: Optional[discord.Interaction] = None
        self.original_user: Optional[discord.User] = None
        self.require_original_user = kwargs.pop('require_original_user', True)
        self.add_item(TimeoutSelect(options, placeholder, **kwargs))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """選択UIの操作権限チェック"""
        if self.require_original_user and self.original_user and interaction.user != self.original_user:
            await interaction.response.send_message("この操作は実行できません", ephemeral=True)
            return False
        return True

    async def prompt(self, ctx: EnhancedContext, message: str, **kwargs) -> Optional[Union[str, List[str]]]:
        """選択メニューを表示し、結果を待機する"""
        self.original_user = ctx.author
        embed = discord.Embed(
            description=message,
            color=discord.Color.blue()
        )
        self.message = await ctx.send(embed=embed, view=self, **kwargs)
        await self.wait()
        try:
            if self.message:
                await self.message.edit(view=None)
        except discord.NotFound:
            pass
        return self.selected_value

    async def send_webhook(self, url: str, *args, **kwargs) -> Optional[discord.Message]:
        """
        このコンテキストに関連するBotインスタンスを使用してWebhookを送信します。
        引数は EnhancedBot.send_webhook と同じです。
        """
        if not hasattr(self.bot, 'send_webhook'):
            raise AttributeError("The bot instance does not have a 'send_webhook' method. Ensure you are using EnhancedBot.")
        return await self.bot.send_webhook(url, *args, **kwargs) # type: ignore


class AdvancedSelect(EnhancedView):
    """拡張セレクトメニュー（ページネーション対応）

    ・選択肢が多い場合に複数ページでの表示をサポートする
    """
    def __init__(
        self,
        options: List[discord.SelectOption],
        *,
        page_size: int = 25,
        placeholder: str = "選択してください...",
        timeout: float = 30,
        **kwargs
    ):
        super().__init__(timeout=timeout)
        self.current_page = 0
        self.options = options
        self.page_size = page_size
        self.placeholder = placeholder
        self.selected_values = []
        self.original_user: Optional[discord.User] = None
        self.require_original_user = kwargs.pop('require_original_user', True)
        self._update_components()

    def _update_components(self):
        """内部処理：UIコンポーネント（選択メニューとページ切替ボタン）の更新"""
        self.clear_items()
        page_options = self._current_page_options()
        self.add_item(AdvancedSelectMenu(
            options=page_options,
            placeholder=self.placeholder,
            max_values=len(page_options)
        ))
        if len(self.options) > self.page_size:
            self._add_pagination_buttons()

    def _current_page_options(self) -> List[discord.SelectOption]:
        """内部処理：現在のページに表示する選択肢の抽出"""
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.options[start:end]

    def _add_pagination_buttons(self):
        """内部処理：ページ移動用のボタンを追加する"""
        self.add_item(PageButton(
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            callback=self._prev_page
        ))
        self.add_item(PageButton(
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            callback=self._next_page
        ))

    async def _prev_page(self, interaction: discord.Interaction):
        """内部処理：前のページへ移動する"""
        self.current_page = max(0, self.current_page - 1)
        self._update_components()
        await interaction.response.edit_message(view=self)

    async def _next_page(self, interaction: discord.Interaction):
        """内部処理：次のページへ移動する"""
        self.current_page = min((len(self.options) // self.page_size), self.current_page + 1)
        self._update_components()
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """選択UIの操作権限チェック"""
        if self.require_original_user and self.original_user and interaction.user != self.original_user:
            await interaction.response.send_message("この操作は実行できません", ephemeral=True)
            return False
        return True

    async def prompt(self, ctx: EnhancedContext, message: str, **kwargs) -> Optional[List[str]]:
        """選択メニューを表示し、選択結果を待機する"""
        self.original_user = ctx.author
        embed = discord.Embed(
            description=message,
            color=discord.Color.blue()
        )
        self.message = await ctx.send(embed=embed, view=self, **kwargs)
        await self.wait()
        try:
            if self.message:
                await self.message.edit(view=None)
        except discord.NotFound:
            pass
        return self.selected_values


class AdvancedSelectMenu(discord.ui.Select):
    """拡張セレクトメニュー用の内部クラス

    選択後に指定のコールバック処理を実行する
    """
    def __init__(self, *, callback=None, **kwargs):
        super().__init__(**kwargs)
        self._callback_func = callback

    async def callback(self, interaction: discord.Interaction):
        """ユーザー選択後の処理"""
        if self._callback_func:
            await self._callback_func(interaction, self.values)
        view = cast(AdvancedSelect, self.view)
        view.selected_values = self.values
        view.stop()
        await interaction.response.defer()


class PageButton(discord.ui.Button):
    """ページ移動用ボタン

    押下時に内部で設定されたコールバックを実行する
    """
    def __init__(self, *, callback=None, **kwargs):
        super().__init__(**kwargs)
        self._callback_func = callback

    async def callback(self, interaction: discord.Interaction):
        """ボタン押下時の処理"""
        if self._callback_func:
            await self._callback_func(interaction)

