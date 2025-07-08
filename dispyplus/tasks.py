# Dispyplus: DispyplusBot のバックグラウンドタスクスケジューリング機能を提供するモジュール
import asyncio
import datetime
from datetime import timezone
from typing import Coroutine, Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .Dispyplus import DispyplusBot


def schedule_task(
    bot: "DispyplusBot",
    coro: Coroutine,
    *,
    name: str = None,
    interval: float = None,
    daily: bool = False,
    time: datetime.time = None
) -> asyncio.Task:
    """タスクをスケジュールする

    ・名前重複を防止し、指定間隔または毎日の指定時刻で実行
    ・エラー発生時は適切な待機後に再試行する
    """
    if not name:
        name = f"task_{len(bot._task_registry) + 1}"

    if name in bot._task_registry:
        raise ValueError(f"タスク '{name}' は既に存在します")

    async def _task_wrapper():
        try:
            bot.logger.info(f"タスク '{name}' を開始しました")
            if daily and time:
                while not bot.is_closed():
                    now = datetime.datetime.now(time.tzinfo or timezone.utc)
                    target_dt = datetime.datetime.combine(now.date(), time) # target_dt の型を明示
                    # 今日の指定時刻を過ぎている場合は翌日に設定
                    if now.time() >= time:
                        target_dt += datetime.timedelta(days=1)
                    wait_seconds = (target_dt - now).total_seconds()
                    bot.logger.debug(f"タスク '{name}' は {wait_seconds:.1f} 秒後に実行されます")
                    try:
                        await asyncio.sleep(wait_seconds)
                        await coro
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        bot.logger.error(f"タスク '{name}' でエラーが発生しました: {e}", exc_info=True)
                        # エラー後は15分待機
                        await asyncio.sleep(900)
            elif interval:
                while not bot.is_closed():
                    try:
                        start_time_task = datetime.datetime.now(timezone.utc) # start_time だと DispyplusBot の属性と被る可能性
                        await coro
                        # 実行時間を差し引いた待機
                        elapsed = (datetime.datetime.now(timezone.utc) - start_time_task).total_seconds()
                        wait_time = max(0.1, interval - elapsed)
                        await asyncio.sleep(wait_time)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        bot.logger.error(f"タスク '{name}' でエラーが発生しました: {e}", exc_info=True)
                        # エラー後は待機時間を設定
                        await asyncio.sleep(min(interval, 60))
            else:
                await coro
        except asyncio.CancelledError:
            bot.logger.info(f"タスク '{name}' がキャンセルされました")
        except Exception as e:
            bot.logger.error(f"タスク '{name}' が予期せぬエラーで終了しました: {e}", exc_info=True)
        finally:
            # タスクレジストリから削除
            bot._task_registry.pop(name, None)

    task = bot.loop.create_task(_task_wrapper(), name=name)
    bot._task_registry[name] = task
    return task

def cancel_task(bot: "DispyplusBot", name: str) -> bool:
    """指定したタスクをキャンセルする

    成功した場合はTrueを返す
    """
    if task := bot._task_registry.get(name):
        task.cancel()
        bot._task_registry.pop(name, None)
        bot.logger.info(f"タスク '{name}' をキャンセルしました。")
        return True
    bot.logger.warning(f"タスク '{name}' のキャンセル試行: 見つかりませんでした。")
    return False

def get_task(bot: "DispyplusBot", name: str) -> Optional[asyncio.Task]:
    """タスク名から該当するタスクを取得する"""
    return bot._task_registry.get(name)

def get_all_tasks(bot: "DispyplusBot") -> Dict[str, asyncio.Task]:
    """全登録タスクの辞書を返す"""
    return bot._task_registry.copy()
