import os
import asyncio
import logging
import datetime
from datetime import timezone
from pathlib import Path
from functools import wraps
from typing import Optional, List, Union, Callable, Coroutine, Dict, TypeVar, Generic, cast
from core.context import EnhancedContext
import discord
from discord.ext import commands
T = TypeVar('T')
class EnhancedView(discord.ui.View):
    """タイムアウト処理を改善したView基底クラス

    UIコンポーネント全体の無効化や、タイムアウト時のカスタム処理を実装。
    """
    def __init__(self, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def on_timeout(self) -> None:
        """タイムアウト発生時の処理

        ・内部ロックを用いて重複処理を防止  
        ・全UIコンポーネントの無効化とカスタムタイムアウト処理の実行
        """
        if self._closed:
            return

        async with self._lock:
            self._closed = True
            await self.disable_all_components()
            await self.on_custom_timeout()

    async def disable_all_components(self) -> None:
        """すべてのUIコンポーネントを無効化する

        ・ボタンなどのインタラクション部品の操作を無効にする  
        ・メッセージが存在する場合は更新を試みる
        """
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
    """型安全かつ柔軟なページネーションシステム

    指定データリストを複数ページに分割し、各ページをEmbedとして表示する。
    """
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

