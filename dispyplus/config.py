import os
import configparser
import logging
import json
from typing import Any, Optional

class ConfigManager:
    """
    Manages application configuration using an INI file.

    This class handles reading from and writing to an INI configuration file.
    It supports automatic type conversion for common types (int, float, bool, JSON)
    and can hot-reload the configuration if the file is modified.

    Args:
        config_file (str, optional): The path to the configuration INI file.
            Defaults to 'config.ini'. If the file does not exist, it will be created.

    Attributes:
        config_file (str): Absolute path to the configuration file.
        config (configparser.ConfigParser): The underlying ConfigParser instance.

    Methods:
        get(section, key, fallback=None): Retrieves a configuration value, converting its type.
        set(section, key, value): Sets a configuration value, converting it to a string.
        save(): Saves the current configuration to the file.
        reload(): Reloads the configuration from the file if it has been modified.
    """
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = os.path.abspath(config_file)
        self.config = configparser.ConfigParser()
        self._ensure_config_exists()
        self._load_config()
        self._last_modified = self._get_modified_time()

    def _ensure_config_exists(self) -> None:
        """設定ファイルの存在確認と新規作成"""
        config_dir = os.path.dirname(self.config_file)
        os.makedirs(config_dir, exist_ok=True)
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write('[DEFAULT]\n')
            logging.info(f"新規設定ファイルを作成: {self.config_file}")

    def _load_config(self) -> None:
        """設定ファイルを読み込む"""
        try:
            read_files = self.config.read(self.config_file, encoding='utf-8')
            if not read_files:
                logging.warning("設定ファイルが空または存在しません")
        except Exception as e:
            logging.error(f"設定ファイル読み込みエラー: {str(e)}")
            raise

    def _get_modified_time(self) -> float:
        """ファイルの最終更新時刻を取得"""
        try:
            return os.path.getmtime(self.config_file)
        except OSError as e:
            logging.error(f"最終更新時刻取得エラー: {str(e)}")
            return 0

    def get(self, section: str, key: str, fallback: Optional[Any] = None) -> Any:
        """設定値を取得し、適切な型に変換して返す"""
        if not self.config.has_section(section):
            self.config.add_section(section)
            logging.info(f"新規セクションを作成: [{section}]")
            self.save()
            return

        if not self.config.has_option(section, key):
            # fallbackが指定されていない場合、空の値を設定
            if fallback is None:
                self.set(section, key, "")  # 空の値を設定
                logging.info(f"新規キーを設定（空の値）: [{section}] {key}=")
                return None  # Noneを返す
            else:
                self.set(section, key, fallback)  # fallback値で設定
                logging.info(f"新規キーを設定: [{section}] {key}={fallback}")
                return fallback  # fallback値を返す

        # 値の取得と型変換
        value = self.config.get(section, key)
        return self._auto_convert_value(value)

    def _auto_convert_value(self, value: Optional[str]) -> Any:
        """INIファイルの文字列値を適切な型に変換"""
        # Noneまたは空文字列の場合
        if value is None or value == "":
            return None

        # JSON文字列として解析を試みる
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

        # 真偽値の判定
        lower_val = value.lower()
        if lower_val in ('true', 'yes', 'on', '1'):
            return True
        if lower_val in ('false', 'no', 'off', '0'):
            return False

        # 数値への変換
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    def set(self, section: str, key: str, value: Any) -> None:
        """設定値をINIファイルに保存可能な形式で設定"""
        if not self.config.has_section(section):
            self.config.add_section(section)

        if value is None:
            str_value = ""
        elif isinstance(value, (list, dict)):
            str_value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            str_value = "true" if value else "false"
        else:
            str_value = str(value)

        self.config.set(section, key, str_value)
        logging.debug(f"設定値を更新: [{section}] {key}={str_value}")   
        self.save()

    def save(self) -> None:
        """設定変更をファイルに保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            self._last_modified = self._get_modified_time()
            logging.info(f"設定ファイルを保存しました: {self.config_file}")
        except Exception as e:
            logging.error(f"設定ファイル保存エラー: {str(e)}")
            raise

    def reload(self) -> None:
        """設定ファイルを再読み込みする"""
        current_modified_time = self._get_modified_time()
        if current_modified_time > self._last_modified:
            self._load_config()
            self._last_modified = current_modified_time
            logging.info(f"設定ファイルを再読み込みしました: {self.config_file}")
        else:
            logging.info("設定ファイルに変更はありません")

    def __str__(self) -> str:
        """現在の設定内容を文字列で表現"""
        return "\n".join(
            f"[{section}]\n" + "\n".join(
                f"{key} = {value}" for key, value in self.config.items(section)
            ) for section in self.config.sections()
        )