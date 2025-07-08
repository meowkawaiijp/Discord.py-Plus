# Dispyplus: その他のユーティリティ関数を提供するモジュール
import asyncio
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..bot import DispyplusBot


async def start_config_watcher(bot: "DispyplusBot") -> Optional[asyncio.Task]:
    """設定ファイルの変更を監視するタスクを開始する"""
    if bot._config_watcher and not bot._config_watcher.done(): # 既に実行中の場合は何もしない
        bot.logger.debug("Config watcher task is already running.")
        return bot._config_watcher

    async def _watch_task():
        while not bot.is_closed():
            try:
                # 設定ファイルに変更があればリロードし、イベントを発火
                if bot.config.reload(): # reload()がbool値を返すように変更または確認が必要
                    bot.logger.info("設定ファイルが更新されました")
                    bot.dispatch('config_reload')
            except Exception as e:
                bot.logger.error(f"Config watcher error: {str(e)}", exc_info=True)
            await asyncio.sleep(10) # 監視間隔

    # _config_watcherがNoneまたは完了済みの場合のみ新しいタスクを作成
    bot._config_watcher = bot.loop.create_task(_watch_task())
    bot.logger.info("設定ファイル監視タスクを開始しました")
    return bot._config_watcher
