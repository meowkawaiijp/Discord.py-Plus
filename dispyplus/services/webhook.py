import discord
import aiohttp
from typing import Optional, List, TYPE_CHECKING
if TYPE_CHECKING:
    from ..bot import DispyplusBot

async def send_webhook_message(bot: 'DispyplusBot', url: str, content: Optional[str]=None, *, username: Optional[str]=None, avatar_url: Optional[str]=None, tts: bool=False, file: Optional[discord.File]=None, files: Optional[List[discord.File]]=None, embed: Optional[discord.Embed]=None, embeds: Optional[List[discord.Embed]]=None, allowed_mentions: Optional[discord.AllowedMentions]=None, wait: bool=False) -> Optional[discord.WebhookMessage]:
    """
    指定されたWebhook URLにメッセージを送信します。
    この関数は DispyplusBot インスタンスのメソッドとして呼び出されることを意図しています。
    """
    if file and files:
        raise ValueError('Cannot mix file and files keyword arguments.')
    if embed and embeds:
        raise ValueError('Cannot mix embed and embeds keyword arguments.')
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url, session=session)
        try:
            actual_files: List[discord.File] = []
            if files:
                actual_files.extend(files)
            if file:
                actual_files.append(file)
            final_file: Optional[discord.File] = None
            final_files: Optional[List[discord.File]] = None
            if actual_files:
                if len(actual_files) == 1 and (not files):
                    final_file = actual_files[0]
                else:
                    final_files = actual_files
            actual_embeds: List[discord.Embed] = []
            if embeds:
                actual_embeds.extend(embeds)
            if embed and embed not in actual_embeds:
                actual_embeds.append(embed)
            sent_message = await webhook.send(content=content, username=username or bot.user.name if bot.user else None, avatar_url=avatar_url or bot.user.display_avatar.url if bot.user else None, tts=tts, file=final_file, files=final_files, embeds=actual_embeds if actual_embeds else None, allowed_mentions=allowed_mentions or bot.allowed_mentions, wait=wait)
            return sent_message
        except discord.HTTPException as e:
            bot.logger.error(f'Webhook send failed to {url}: {e}', exc_info=True)
            raise
        except ValueError as e:
            bot.logger.error(f'Webhook parameter error: {e}', exc_info=True)
            raise
        except Exception as e:
            bot.logger.error(f'An unexpected error occurred during webhook send to {url}: {e}', exc_info=True)
            raise
