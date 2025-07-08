# Dispyplus: EnhancedContextを提供するモジュール
import discord
from discord.ext import commands
import datetime
from typing import Optional, Callable, Awaitable

# InteractionTypeを新しいenumsモジュールからインポート
from .enums import InteractionType
# uiモジュールからのインポート (循環参照を避けるためTYPE_CHECKINGを使用)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .ui import ConfirmationView # ConfirmationViewの具体的なパスはui.pyの構造による

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
        from .ui import ConfirmationView as DispyplusConfirmationView

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
