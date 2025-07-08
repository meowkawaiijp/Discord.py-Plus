import asyncio
import logging
from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands, ui # discord.ui をインポート

from dispyplus import DispyplusBot, EnhancedContext, ConfigManager
# dispyplus.ui.ConfirmationView は EnhancedContext.ask 経由で使われる。
# from dispyplus import ConfirmationView # 必要なら直接インポートも可能

# --- ボットの基本的なセットアップ ---
CONFIG_FILE = 'config.ini' # 必要に応じてパスを調整
config = ConfigManager(CONFIG_FILE)

# ロギング設定 (simple_example.py から流用)
logging.basicConfig(
    level=config.get('Logging', 'level', fallback='INFO'),
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    handlers=[
        logging.FileHandler(
            filename=config.get('Logging', 'file', fallback='bot.log'),
            encoding='utf-8', mode='w' # 毎回クリアするために 'w' に変更 (テスト用)
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = DispyplusBot(
    command_prefix=config.get('Bot', 'prefix', fallback='!ui'), # プレフィックスを変更して他の例と区別
    intents=intents,
    config_path=CONFIG_FILE
)

# --- UIサンプル用のCog ---
class UISampleCog(commands.Cog):
    def __init__(self, bot: DispyplusBot):
        self.bot = bot

    @commands.hybrid_command(name="confirm_test", description="新しい確認ビューのテスト")
    async def confirm_test_command(self, ctx: EnhancedContext, *, message: str = "本当に実行しますか？"):
        """EnhancedContext.ask を使った確認コマンドのサンプル (新しい ConfirmationView を使用)"""
        if ctx.interaction and not ctx.interaction.response.is_done():
            # ask メソッド内でよしなに ephemeral を扱えるように修正されているか、
            # ここで defer するのが適切かを確認。
            # 現状の ask の実装では、ephemeral は kwargs で渡せる。
            pass # ask メソッドに ephemeral を渡すことで対応

        confirmed = await ctx.ask(message, timeout=30.0, ephemeral=True) # ephemeral を ask に渡す

        # ctx.ask の後の ctx.respond は、ask がメッセージを送信・編集するため、
        # 通常は不要になるか、followup を使う必要がある。
        # ask の中で応答が完結するようにするか、ask がメッセージオブジェクトを返すようにして編集する。
        # 現状の ask は bool? を返すので、応答はここで行う。
        if confirmed is None:
            # ask の中でタイムアウトメッセージを編集するか、ここで followup で送る
            # 現状の ConfirmationView はタイムアウト時にメッセージを編集するため、ここでは不要かもしれない
            await ctx.send("確認がタイムアウトしました。", ephemeral=True) # followup を使用
        elif confirmed:
            await ctx.send("操作が確認されました！", ephemeral=True) # followup を使用
        else:
            await ctx.send("操作はキャンセルされました。", ephemeral=True) # followup を使用


    # --- discord.ui.Select を使ったサンプル ---
    class SimpleSelectView(discord.ui.View):
        def __init__(self, author_id: int, *, timeout: Optional[float] = 180.0):
            super().__init__(timeout=timeout)
            self.author_id = author_id
            self.selected_value: Optional[str] = None

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("あなたはこのメニューを操作できません。", ephemeral=True)
                return False
            return True

        @ui.select(
            placeholder="オプションを選んでください...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="りんご", description="甘くてシャキシャキ", value="apple", emoji="🍎"),
                discord.SelectOption(label="バナナ", description="栄養満点", value="banana", emoji="🍌"),
                discord.SelectOption(label="オレンジ", description="ビタミンCたっぷり", value="orange", emoji="🍊"),
            ]
        )
        async def color_select(self, interaction: discord.Interaction, select: ui.Select):
            self.selected_value = select.values[0]
            for option in select.options: # 選択されたものを太字に
                option.default = option.value == self.selected_value

            # ボタンを無効化
            for child in self.children:
                if isinstance(child, (ui.Button, ui.Select)):
                    child.disabled = True

            await interaction.response.edit_message(content=f"「{self.selected_value}」が選択されました！", view=self)
            self.stop()

        async def on_timeout(self) -> None:
            for child in self.children:
                if isinstance(child, (ui.Button, ui.Select)):
                    child.disabled = True
            if hasattr(self, 'message') and self.message: # message属性があるか確認
                 try:
                    await self.message.edit(content="選択がタイムアウトしました。", view=self)
                 except discord.NotFound:
                    pass
            self.stop()


    @commands.hybrid_command(name="select_test", description="簡単なセレクトメニューのテスト")
    async def select_test_command(self, ctx: EnhancedContext):
        """簡単なセレクトメニューを表示するコマンドのサンプル"""
        view = UISampleCog.SimpleSelectView(author_id=ctx.author.id, timeout=30.0)
        # EnhancedContext.send は interaction 時によしなに ephemeral を扱えないので、
        # interaction かどうかで分岐する
        if ctx.interaction:
            if not ctx.interaction.response.is_done():
                 await ctx.interaction.response.send_message("好きな果物を選んでください:", view=view, ephemeral=True)
            else: # defer されている場合
                view.message = await ctx.interaction.followup.send("好きな果物を選んでください:", view=view, ephemeral=True)
        else:
            view.message = await ctx.send("好きな果物を選んでください:", view=view)

        await view.wait()
        # view.selected_value に結果が入っている
        # このサンプルではビュー内で応答を完結させている


    # --- discord.ui.Modal を使ったサンプル ---
    class SimpleModal(ui.Modal, title="簡単なアンケート"):
        name = ui.TextInput(
            label="お名前",
            placeholder="あなたの名前を入力してください...",
            style=discord.TextStyle.short,
            required=True,
            max_length=50
        )
        feedback = ui.TextInput(
            label="ご意見・ご感想",
            placeholder="何か一言お願いします！",
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.send_message(
                f"{self.name.value}さん、フィードバックありがとうございます！\n"
                f"内容: ```{self.feedback.value or '(なし)'}```",
                ephemeral=True
            )
            self.stop()

        async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
            logger.error(f"Modal error: {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("モーダルの処理中にエラーが発生しました。", ephemeral=True)
            self.stop()

        # on_timeout は Modal にはデフォルトで存在しないが、必要なら View のように実装できる
        # async def on_timeout(self) -> None:
        #     # モーダルがタイムアウトした場合の処理 (通常はあまりない)
        #     logger.info(f"Modal '{self.title}' timed out for user {self.user_id_who_opened_it}")
        #     self.stop()


    @commands.hybrid_command(name="modal_test", description="簡単なモーダルのテスト")
    async def modal_test_command(self, ctx: EnhancedContext):
        """簡単なモーダルを表示するコマンドのサンプル"""
        if not ctx.interaction:
            await ctx.send("このコマンドはスラッシュコマンドとしてのみ実行できます（モーダル表示のため）。")
            return

        modal = UISampleCog.SimpleModal(timeout=120.0) # モーダルのタイムアウトは長めに設定可能
        await ctx.interaction.response.send_modal(modal)
        # モーダルの結果は on_submit で処理される

    # --- PaginatedSelectView のサンプル ---
    @commands.hybrid_command(name="paginated_select_test", description="ページネーション付きセレクトメニューのテスト")
    async def paginated_select_test_command(self, ctx: EnhancedContext):
        """PaginatedSelectView を使ったコマンドのサンプル"""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer(ephemeral=True)

        # たくさんの選択肢を生成
        num_options = 50
        options = [
            discord.SelectOption(label=f"アイテム {i+1}", value=f"item_{i+1}", description=f"これはアイテム {i+1} の説明です。")
            for i in range(num_options)
        ]

        # dispyplus.ui.PaginatedSelectView をインポート
        # EnhancedContext にヘルパーメソッドを追加するのも良い
        from dispyplus.ui import PaginatedSelectView # dispyplus から直接インポート

        view = PaginatedSelectView(
            options=options,
            placeholder="アイテムを選んでください...",
            items_per_page=5, # 1ページあたり5アイテム
            author_id=ctx.author.id,
            timeout=120.0
        )

        message_content = "以下のリストからアイテムを選択してください:"

        if ctx.interaction:
            # followup.send は ephemeral を取らないので、最初の defer で ephemeral=True を設定しておく
            view.message = await ctx.followup.send(message_content, view=view, ephemeral=True)
        else:
            view.message = await ctx.send(message_content, view=view)

        await view.wait()

        if view.selected_values:
            await ctx.respond(f"最終的に「{', '.join(view.selected_values)}」が選択されました。", ephemeral=True)
        else:
            await ctx.respond("何も選択されませんでした（またはタイムアウト）。", ephemeral=True, delete_after=10)

    # --- SimpleSelectView のサンプル ---
    @commands.hybrid_command(name="simple_select_test", description="シンプルなセレクトメニューのテスト")
    async def simple_select_test_command(self, ctx: EnhancedContext):
        """SimpleSelectView を使ったコマンドのサンプル"""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer(ephemeral=True)

        options = [
            discord.SelectOption(label="赤", value="red", emoji="🔴"),
            discord.SelectOption(label="緑", value="green", emoji="🟢"),
            discord.SelectOption(label="青", value="blue", emoji="🔵"),
            discord.SelectOption(label="黄色", value="yellow", emoji="🟡"),
        ]

        from dispyplus.ui import SimpleSelectView # dispyplus から直接インポート

        view = SimpleSelectView(
            options=options,
            placeholder="好きな色を選んでね！",
            author_id=ctx.author.id,
            timeout=60.0,
            max_values=2 # 例として複数選択を許可
        )

        message_content = "好きな色を教えてください（複数選択可）:"
        if ctx.interaction:
            view.message = await ctx.followup.send(message_content, view=view, ephemeral=True)
        else:
            view.message = await ctx.send(message_content, view=view)

        await view.wait()

        if view.selected_values:
            selected_colors = ", ".join(view.selected_values)
            await ctx.respond(f"あなたは {selected_colors} を選びました！", ephemeral=True)
        else:
            await ctx.respond("何も選択されませんでした（またはタイムアウト）。", ephemeral=True, delete_after=10)


async def setup(bot: DispyplusBot):
    await bot.add_cog(UISampleCog(bot))

# --- ボットの起動 ---
async def main():
    await setup(bot) # Cogを登録
    await bot.start(config.get('Bot', 'token'))

if __name__ == "__main__":
    # simple_example.py と同時に起動するとトークンエラーになるため、
    # こちらを単独で実行する場合は、simple_example.py の実行を止めるか、
    # 別のボットトークンを使用してください。
    asyncio.run(main())
# --- DispyplusForm Prototype Test ---
from dispyplus.ui.forms import DispyplusForm, text_field # Use new text_field helper
from typing import Dict, Any, Tuple, Union # For type hinting

# Example custom validator
def is_valid_age(value: Any, interaction: discord.Interaction) -> Union[bool, Tuple[bool, str]]:
    try:
        age = int(value) # Already converted by target_type=int, but good practice if used raw
        if 1 <= age <= 120:
            return True
        return False, "Age must be between 1 and 120."
    except ValueError:
        return False, "Age must be a valid number."

class PrototypeTestForm(DispyplusForm):
    form_title = "Enhanced Form Test"

    full_name: str = text_field(label="Full Name", placeholder="Enter your full name", required=True, target_type=str)
    email: str = text_field(
        label="Email Address",
        placeholder="user@example.com",
        target_type=str,
        validator=lambda v, i: ("@" in v and "." in v.split("@")[-1], "Please enter a valid email address.")
    )
    age: Optional[int] = text_field(
        label="Age (1-120, Optional)",
        required=False,
        target_type=int, # Will attempt to convert to int
        validator=is_valid_age
    )
    subscribe: bool = text_field(
        label="Subscribe to newsletter? (yes/no)",
        required=True,
        target_type=bool # Will convert 'yes', 'true', '1' to True, etc.
    )
    feedback: str = text_field(
        label="Your Feedback (min 10 chars)",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10,
        target_type=str
    )

    async def process_form_data(self, interaction: discord.Interaction, data: Dict[str, Any]):
        # data dictionary now contains type-converted and validated values
        # For the prototype, we'll just send the data back to the user.
        response_message = f"Prototype form submitted by {interaction.user.mention}!\n"
        response_message += "Data received:\n"
        for key, value in data.items():
            response_message += f"- **{key}**: {value} (Type: {type(value).__name__})\n" # Show type

        # Since this is called by DispyplusForm.on_submit, interaction is already responded to (deferred by Modal).
        # We MUST use followup.
        await interaction.followup.send(response_message, ephemeral=True)

        # For EnhancedContext.ask_form, we need to set the future.
        if hasattr(self, 'future') and not self.future.done():
            self.future.set_result(data)


@bot.hybrid_command(name="form_proto_test", description="Test for DispyplusForm prototype with EnhancedContext.ask_form.")
async def form_proto_test_command(ctx: EnhancedContext):
    """Displays the prototype test form using ctx.ask_form."""
    if not ctx.interaction: # ask_form helper also checks this, but good to have guard
        await ctx.send("This command must be used as a slash command to test modals.")
        return

    try:
        # Using the new EnhancedContext.ask_form helper
        # PrototypeTestForm constructor might take `ctx` if we modify it, for now it doesn't.
        # If PrototypeTestForm's __init__ was `def __init__(self, ctx, title=None, timeout=None):`
        # then `ctx=ctx` would be passed automatically by ask_form if `ctx` kwarg is not in `**kwargs_for_form_init`
        form_data = await ctx.ask_form(PrototypeTestForm, title="Submit Your Info (ctx.ask_form)")

        if form_data:
            # process_form_data already sent a followup.
            # This is just to confirm ask_form returned the data.
            await ctx.followup.send(f"ask_form successfully received data: {list(form_data.keys())}", ephemeral=True)
        else:
            # This means the form timed out, or validation failed and future was set to None.
            # The form itself (handle_validation_errors or on_timeout) should have informed the user.
            await ctx.followup.send("Form was not successfully submitted (timeout or validation issue).", ephemeral=True)

    except Exception as e:
        # If process_form_data or something in ask_form raised an error that was set on the future
        logger.error(f"Error during form_proto_test_command: {e}", exc_info=True)
        await ctx.followup.send(f"An unexpected error occurred with the form: {e}", ephemeral=True)
