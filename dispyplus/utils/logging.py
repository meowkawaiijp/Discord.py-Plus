# Dispyplus: ロギング関連のユーティリティを提供するモジュール
import os
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bot import DispyplusBot
    from .config import ConfigManager


def setup_logger(bot_name: str, config: "ConfigManager") -> logging.Logger:
    """ロガーを初期化し、ファイルおよびコンソール出力を設定する"""
    logger = logging.getLogger(bot_name)
    log_level_str = config.get('Logging', 'level', fallback='INFO')
    # getattrの前に、log_level_strがloggingモジュールの有効な属性であることを確認する方が安全
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # ログファイル設定
    log_file = config.get('Logging', 'file', fallback='bot.log')
    log_file_path = os.path.abspath(log_file) # 絶対パスに変換
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    file_handler = logging.FileHandler(
        filename=log_file_path,
        encoding='utf-8',
        mode='a'
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 既存ハンドラを一旦削除
    if logger.hasHandlers():
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info(f"Logger '{bot_name}' initialized with level {logging.getLevelName(log_level)} and output to {log_file_path}")
    return logger
