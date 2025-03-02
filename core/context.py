import datetime
from typing import Optional, List, TypeVar
from core.view import ConfirmationView, Paginator
import discord
from discord.ext import commands
T = TypeVar('T')
class EnhancedContext(commands.Context):
    """拡張コンテキストクラス

    標準Contextに各種ユーティリティメソッドを追加。
    """
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
            color=discord.Color.orange()
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
