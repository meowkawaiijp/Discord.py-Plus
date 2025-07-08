# Dispyplus: Discord UIキットの基本的な拡張コンポーネントを提供するモジュール
# EnhancedView や、それをベースとした汎用的なUI部品が含まれます。
import asyncio
import discord
from discord import ui # uiをインポート
from typing import Optional, List, Union, cast, TYPE_CHECKING, TypeVar, Generic

if TYPE_CHECKING:
    from .context import EnhancedContext # EnhancedContextのインポートパスを修正

# 型エイリアスをここに移動またはここで定義
T = TypeVar('T') # other.py から移動

class EnhancedView(ui.View): # discord.ui.View を継承
    def __init__(self, timeout: Optional[float] = 180.0): #デフォルト値を修正
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self._lock = asyncio.Lock() # Lockを追加
        self._closed = False # クローズ状態を管理

    async def on_timeout(self) -> None:
        if self._closed: # 既に処理済みなら何もしない
            return

        async with self._lock: # ロックを取得して排他制御
            if self._closed: # ダブルチェック
                return
            self._closed = True # クローズ状態に設定

            await self.disable_all_components()
            await self.on_custom_timeout() # カスタムタイムアウト処理を呼び出し
            self.stop() # Viewを停止させる

    async def disable_all_components(self) -> None:
        for item in self.children:
            if hasattr(item, 'disabled') and isinstance(item, (ui.Button, ui.Select, ui.TextInput)): #型チェックを強化
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass # メッセージが既に削除されている場合は無視
            except discord.HTTPException as e:
                # ここでloggerを使いたいが、直接botインスタンスにアクセスできない
                # print(f"EnhancedView: Failed to edit message on timeout: {e}")
                pass # HTTPエラーも一旦無視

    async def on_custom_timeout(self) -> None:
        """タイムアウト時にサブクラスでオーバーライドされるカスタム処理。"""
        pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item[Any]) -> None: # itemの型を修正
        """インタラクション処理中にエラーが発生した際のデフォルトハンドラ。"""
        # print(f"Error in EnhancedView item {str(item)}: {error}") # ログ出力は呼び出し元で行うことを推奨
        if interaction.response.is_done():
            await interaction.followup.send("エラーが発生しました。しばらくしてからもう一度お試しください。", ephemeral=True)
        else:
            await interaction.response.send_message("エラーが発生しました。しばらくしてからもう一度お試しください。", ephemeral=True)
        self.stop()


class TimeoutSelect(ui.Select): # discord.ui.Select を継承
    """タイムアウト付きセレクトメニュー (InteractiveSelectの内部コンポーネント)"""
    def __init__(self, options: List[discord.SelectOption], placeholder: str = "選択してください...", **kwargs):
        min_values = kwargs.pop('min_values', 1)
        max_values = kwargs.pop('max_values', 1)
        # custom_id が渡されていない場合はデフォルト値を設定
        custom_id = kwargs.pop('custom_id', f"timeout_select_{discord.utils.generate_snowflake()}")
        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
            custom_id=custom_id # custom_id を渡す
        )

    async def callback(self, interaction: discord.Interaction):
        # self.view が InteractiveSelect のインスタンスであることを期待
        if isinstance(self.view, InteractiveSelect):
            view = cast(InteractiveSelect, self.view)
            view.selected_value = self.values[0] if len(self.values) == 1 and self.max_values == 1 else self.values
            view.interaction = interaction # interactionを保存
            view.stop() # 親Viewを停止
            # ボタンを無効化する処理は親Viewのon_timeoutやstop時に任せる
            # ここでinteraction.response.edit_messageを呼ぶと、親Viewの処理と競合する可能性
            await interaction.response.defer() # deferして応答を保留
        else:
            # 予期しないViewの型の場合
            # print(f"Warning: TimeoutSelect used with an unexpected view type: {type(self.view)}")
            await interaction.response.send_message("内部エラーが発生しました。", ephemeral=True)


class InteractiveSelect(EnhancedView):
    """ユーザーに選択メニューを提示し、その結果を返すインタラクティブなUI。"""
    def __init__(
        self,
        options: List[discord.SelectOption],
        placeholder: str = "選択してください...",
        timeout: float = 30.0, #デフォルト値を修正
        *, # これ以降はキーワード専用引数
        require_original_user: bool = True,
        min_values: int = 1, # TimeoutSelectに渡す引数を追加
        max_values: int = 1  # TimeoutSelectに渡す引数を追加
    ):
        super().__init__(timeout=timeout)
        self.selected_value: Optional[Union[str, List[str]]] = None
        self.interaction: Optional[discord.Interaction] = None # 最後に成功したインタラクション
        self.original_user_id: Optional[int] = None # 操作を許可するユーザーのID
        self.require_original_user = require_original_user

        # TimeoutSelectにmin_valuesとmax_valuesを渡す
        self.add_item(TimeoutSelect(options, placeholder, min_values=min_values, max_values=max_values))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.require_original_user and self.original_user_id is not None:
            if interaction.user.id != self.original_user_id:
                await interaction.response.send_message("この操作は元のコマンド実行者のみが行えます。", ephemeral=True)
                return False
        return True # カスタムチェックがない場合は常にTrue（誰でも操作可能）

    async def prompt(self, ctx: "EnhancedContext", message_content: str, **kwargs) -> Optional[Union[str, List[str]]]:
        """選択メニューを含むメッセージを送信し、ユーザーの選択を待つ。"""
        if ctx.author:
            self.original_user_id = ctx.author.id

        embed = discord.Embed(description=message_content, color=discord.Color.blue())

        # ephemeralはkwargsから取得
        ephemeral = kwargs.pop('ephemeral', False)

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.send_message(embed=embed, view=self, ephemeral=ephemeral, **kwargs)
            self.message = await ctx.interaction.original_response()
        else:
            self.message = await ctx.send(embed=embed, view=self, ephemeral=ephemeral, **kwargs) # ctx.sendはephemeralを直接取らないが、InteractionからのContextなら使える

        await self.wait() # ユーザーの操作またはタイムアウトまで待機

        # タイムアウト後や操作完了後にビューをメッセージから削除するか、コンポーネントを無効化するかは
        # EnhancedViewのon_timeoutや、このクラスのcallback後の処理で制御される。
        # ここでは明示的にメッセージを編集しない。
        return self.selected_value


# AdvancedSelect とその関連クラス (AdvancedSelectMenu, PageButton)
class PageButton(ui.Button['AdvancedSelect']): # Viewの型ヒントを追加
    def __init__(self, *, emoji: Optional[Union[str, discord.Emoji, discord.PartialEmoji]], style: discord.ButtonStyle, row: Optional[int] = None, callback_action: str):
        super().__init__(style=style, emoji=emoji, row=row, custom_id=f"page_button_{callback_action}_{discord.utils.generate_snowflake()}")
        self.callback_action = callback_action # 'prev' or 'next'

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None # Viewが存在することを確認
        view = self.view
        if self.callback_action == "prev":
            await view.go_to_previous_page(interaction)
        elif self.callback_action == "next":
            await view.go_to_next_page(interaction)


class AdvancedSelectMenu(ui.Select['AdvancedSelect']): # Viewの型ヒントを追加
    def __init__(self, *, options: List[discord.SelectOption], placeholder: str, max_values: int, custom_id_suffix: str):
        # custom_idが一意になるようにSnowflakeを追加
        super().__init__(options=options, placeholder=placeholder, max_values=max_values, min_values=1, custom_id=f"advanced_select_menu_{custom_id_suffix}_{discord.utils.generate_snowflake()}")

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view = self.view
        view.selected_values = self.values # 選択された値を保存
        # すべてのコンポーネントを無効化
        for item_in_view in view.children:
            if hasattr(item_in_view, 'disabled'):
                item_in_view.disabled = True # type: ignore
        await interaction.response.edit_message(view=view) # viewを更新して無効化を反映
        view.stop() # Viewを停止


class AdvancedSelect(EnhancedView):
    """ページネーション対応の拡張セレクトメニュー。"""
    def __init__(
        self,
        options: List[discord.SelectOption],
        *,
        page_size: int = 20, # discordのSelectの最大オプション数は25なので調整
        placeholder: str = "選択してください...",
        timeout: float = 180.0, # デフォルトタイムアウトを長くする
        require_original_user: bool = True,
        max_selectable_values: int = 1 # ユーザーが選択できる最大数
    ):
        super().__init__(timeout=timeout)
        self.current_page = 0
        self.all_options = options # optionsからall_optionsに名前変更
        self.page_size = min(page_size, 25) # Discordの制限に合わせる
        self.placeholder = placeholder
        self.selected_values: List[str] = [] # 型をList[str]に明示
        self.original_user_id: Optional[int] = None
        self.require_original_user = require_original_user
        self.max_selectable_values = max_selectable_values # 選択可能な最大数を保持

        self.total_pages = (len(self.all_options) + self.page_size - 1) // self.page_size
        self._update_components()

    def _get_current_page_options(self) -> List[discord.SelectOption]: # 名前変更
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.all_options[start:end]

    def _update_components(self):
        self.clear_items()
        current_options = self._get_current_page_options()

        if not current_options: # 現在のページにオプションがない場合（通常は発生しないはず）
            # ダミーの選択不可オプションを表示するか、エラーメッセージを出す
            # ここではSelect自体を追加しないか、disableにする
            pass
        else:
            # AdvancedSelectMenuに渡すmax_valuesは、ページ内のオプション数とユーザーが選択できる最大数の小さい方
            # ただし、Selectのmax_valuesは選択肢の数以下である必要がある。
            # ここでは、ユーザーがこのSelectMenuで選択できる最大数を指定する。
            # ページネーション全体での選択数はこのビューのselected_valuesで管理する。
            # このSelectMenuでの選択は、max_selectable_values に従う。
            select_menu_max_values = min(len(current_options), self.max_selectable_values)

            self.add_item(AdvancedSelectMenu(
                options=current_options,
                placeholder=f"{self.placeholder} (Page {self.current_page + 1}/{self.total_pages})",
                max_values=select_menu_max_values, # ページごとではなく、全体の選択上限
                custom_id_suffix=f"p{self.current_page}" # ページごとにIDを変える
            ))

        if self.total_pages > 1:
            prev_button = PageButton(emoji="◀️", style=discord.ButtonStyle.secondary, callback_action="prev", row=1)
            next_button = PageButton(emoji="▶️", style=discord.ButtonStyle.secondary, callback_action="next", row=1)
            prev_button.disabled = self.current_page == 0
            next_button.disabled = self.current_page >= self.total_pages - 1
            self.add_item(prev_button)
            self.add_item(next_button)

    async def go_to_previous_page(self, interaction: discord.Interaction): # interactionを引数に追加
        if self.current_page > 0:
            self.current_page -= 1
            self._update_components()
            await interaction.response.edit_message(view=self)
        else: # 既に最初のページなら何もしない
            await interaction.response.defer()


    async def go_to_next_page(self, interaction: discord.Interaction): # interactionを引数に追加
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_components()
            await interaction.response.edit_message(view=self)
        else: # 既に最後のページなら何もしない
            await interaction.response.defer()


    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.require_original_user and self.original_user_id is not None:
            if interaction.user.id != self.original_user_id:
                await interaction.response.send_message("この操作は元のコマンド実行者のみが行えます。", ephemeral=True)
                return False
        return True

    async def prompt(self, ctx: "EnhancedContext", message_content: str, **kwargs) -> Optional[List[str]]:
        if ctx.author:
            self.original_user_id = ctx.author.id

        embed = discord.Embed(description=message_content, color=discord.Color.blue())
        ephemeral = kwargs.pop('ephemeral', False)

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.send_message(embed=embed, view=self, ephemeral=ephemeral, **kwargs)
            self.message = await ctx.interaction.original_response()
        else:
            self.message = await ctx.send(embed=embed, view=self, ephemeral=ephemeral, **kwargs)

        await self.wait()
        return self.selected_values

__all__ = ["EnhancedView", "InteractiveSelect", "AdvancedSelect", "TimeoutSelect", "PageButton", "AdvancedSelectMenu"]
