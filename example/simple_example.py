import asyncio
import logging
from dispyplus import DispyplusBot
from dispyplus import ConfigManager # core.configから変更
from dispyplus import log_execution, permission_check # core.decoratorsから変更
from dispyplus import EnhancedContext # core.otherから変更
import discord
from discord.ext import commands
from discord import app_commands
import discord
CONFIG_FILE = 'config.ini'

config = ConfigManager(CONFIG_FILE)

logging.basicConfig(
    level=config.get('Logging', 'level', fallback='INFO'),
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    handlers=[
        logging.FileHandler(
            filename=config.get('Logging', 'file', fallback='bot.log'),
            encoding='utf-8', mode='a'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = DispyplusBot(
    command_prefix=config.get('Bot', 'prefix', fallback='!'),
    intents=intents,
    config_path=CONFIG_FILE # EnhancedBotのコンストラクタに合わせてconfigオブジェクトではなくパスを渡す
)

@bot.hybrid_command(name="ping", description="pong")
@log_execution()
async def ping(ctx: EnhancedContext):
    await ctx.success(f"pong")

@bot.hybrid_command(name="purge") # commands.hybrid_command から bot.hybrid_command へ変更 (EnhancedBotが継承しているため)
@app_commands.describe(limit="削除するメッセージ数")
@permission_check(permissions=['manage_messages']) # core.decorators から
async def purge_messages(
        ctx: EnhancedContext,
        limit: int = 10
    ):
        """メッセージを一括削除します"""
        # インタラクションの場合、応答が遅れる可能性があるため defer する
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer(ephemeral=True) # 処理が見えないように ephemeral も検討

        confirm = await ctx.ask(f"本当に直近 {limit}件 のメッセージを削除しますか？")
        if confirm is None: # タイムアウトなどの場合
            await ctx.respond("タイムアウトしました。", ephemeral=True, delete_after=10)
            return
        if not confirm:
            await ctx.respond("キャンセルしました。", ephemeral=True, delete_after=10)
            return
        
        try:
            # メッセージコマンドの場合、コマンド自体も削除対象に含まれるため +1 する
            # スラッシュコマンドの場合は不要だが、安全のためそのままに
            deleted_messages = await ctx.channel.purge(limit=limit + (1 if not ctx.interaction else 0))
            await ctx.success(f"{len(deleted_messages)-(1 if not ctx.interaction else 0)}件のメッセージを削除しました", delete_after=5)
        except discord.Forbidden:
            await ctx.error("メッセージを削除する権限がありません。", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.error(f"メッセージの削除中にエラーが発生しました: {e}", ephemeral=True)

# --- 新機能のサンプルコード ---
# サンプルCogクラス
from dispyplus import on_message_contains, on_reaction_add, on_user_voice_join # core.custom_eventsから変更

class ExampleCog(commands.Cog):
    def __init__(self, bot: DispyplusBot): # EnhancedBot を DispyplusBot に変更
        self.bot = bot
        self.logger = bot.logger

    @on_message_contains("hello example", ignore_bot=True)
    async def on_hello_example(self, ctx: EnhancedContext, message: discord.Message):
        self.logger.info(f"ExampleCog: Detected 'hello example' from {message.author.name} in {message.channel.name}")
        await message.reply(f"Hello from ExampleCog, {message.author.mention}!")

    @on_reaction_add(emoji="👍")
    async def on_thumbs_up(self, ctx: EnhancedContext, reaction: discord.Reaction, user: discord.User):
        self.logger.info(f"ExampleCog: User {user.name} added 👍 to message {reaction.message.id} by {reaction.message.author.name}")
        await reaction.message.channel.send(f"{user.mention} gave a thumbs up to {reaction.message.author.mention}'s message!", reference=reaction.message, mention_author=False)

    @on_user_voice_join()
    async def user_joined_vc_example(self, member: discord.Member, channel: discord.VoiceChannel):
        self.logger.info(f"ExampleCog: {member.display_name} joined voice channel {channel.name} in {member.guild.name}")
        # 適切なテキストチャンネルに通知を送る (例: ギルドのシステムチャンネルや設定されたログチャンネル)
        # この例では、ボットが参加しているギルドの最初のテキストチャンネルに送信しようと試みる
        target_channel = member.guild.system_channel
        if not target_channel and member.guild.text_channels:
            target_channel = member.guild.text_channels[0]

        if target_channel and target_channel.permissions_for(member.guild.me).send_messages:
            try:
                await target_channel.send(f"{member.mention} just joined the voice channel: {channel.mention}!")
            except discord.HTTPException:
                self.logger.warning(f"Could not send voice join notification to {target_channel.name} in {member.guild.name}")

    @commands.hybrid_command(name="webhooktest", description="Sends a test message via webhook.")
    @app_commands.describe(webhook_url="The URL of the webhook to send to.", message="The message to send.")
    async def webhook_test_command(self, ctx: EnhancedContext, webhook_url: str, *, message: str):
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            await ctx.error("無効なWebhook URL形式です。`https://discord.com/api/webhooks/` で始まる必要があります。", ephemeral=True)
            return

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer(ephemeral=False) # 結果を全員に見せる

        try:
            embed = discord.Embed(title="Webhook Test via Discord.py-Plus", description=message, color=discord.Color.blue())
            embed.set_footer(text=f"Sent by: {ctx.author.display_name}")
            embed.timestamp = discord.utils.utcnow()

            sent_message = await ctx.send_webhook(
                webhook_url,
                embed=embed,
                username=f"{self.bot.user.name} (Test)",
                avatar_url=self.bot.user.display_avatar.url,
                wait=True
            )
            if sent_message:
                await ctx.success(f"Webhookメッセージを送信しました！ (ID: {sent_message.id})", ephemeral=False)
            else:
                # wait=False の場合や、何らかの理由でメッセージが取得できなかった場合
                await ctx.success("Webhookメッセージを送信しました（応答待機なし）。", ephemeral=False)
        except discord.HTTPException as e:
            self.logger.error(f"Webhook send HTTP error: {e}", exc_info=True)
            await ctx.error(f"Webhook送信エラー: {e.status} - {e.text}", ephemeral=True)
        except ValueError as e: # e.g. file/files or embed/embeds mixed
            self.logger.error(f"Webhook parameter error: {e}", exc_info=True)
            await ctx.error(f"Webhookパラメータエラー: {e}", ephemeral=True)
        except Exception as e:
            self.logger.error(f"Unexpected webhook error: {e}", exc_info=True)
            await ctx.error(f"予期せぬWebhookエラーが発生しました。ログを確認してください。", ephemeral=True)

    @commands.hybrid_command(name="invoketype", description="Shows how the command was invoked.")
    async def invoke_type_command(self, ctx: EnhancedContext):
        if ctx.interaction:
            await ctx.success(f"このコマンドはインタラクション ({ctx.interaction_type.name}) として呼び出されました。")
        else:
            await ctx.info("このコマンドは通常のメッセージとして呼び出されました。")


async def main():
    # CogをBotに登録
    await bot.add_cog(ExampleCog(bot))
    await bot.start(config.get('Bot', 'token'))

if __name__ == "__main__":
    asyncio.run(main())