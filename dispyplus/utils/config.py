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
        reload(): Reloads the configuration from the file if it has been modified. Returns True if reloaded.
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
                f.write('[DEFAULT]\n') # DEFAULTセクションを書き込む
            logging.info(f"新規設定ファイルを作成: {self.config_file}")

    def _load_config(self) -> None:
        """設定ファイルを読み込む"""
        try:
            read_ok = self.config.read(self.config_file, encoding='utf-8')
            if not read_ok:
                # ファイルが存在しない、または空、または読み込みに失敗した場合
                # _ensure_config_exists でファイルは作成されているはずなので、空か不正な形式の可能性
                logging.warning(f"設定ファイルが読み込めませんでした: {self.config_file}")
                # 必要であればデフォルト設定をロードする処理をここに追加
        except configparser.Error as e:
            logging.error(f"設定ファイル解析エラー: {self.config_file}, {str(e)}")
            # エラー発生時も続行するが、設定は空になるか、以前の状態のまま
        except Exception as e:
            logging.error(f"設定ファイル読み込み中に予期せぬエラー: {self.config_file}, {str(e)}")
            raise


    def _get_modified_time(self) -> float:
        """ファイルの最終更新時刻を取得"""
        try:
            if os.path.exists(self.config_file):
                return os.path.getmtime(self.config_file)
        except OSError as e:
            logging.error(f"最終更新時刻取得エラー ({self.config_file}): {str(e)}")
        return 0

    def get(self, section: str, key: str, fallback: Optional[Any] = None) -> Any:
        """設定値を取得し、適切な型に変換して返す"""
        if not self.config.has_section(section) and fallback is not None:
            # セクションが存在せず、fallback がある場合は、その値を設定して返す
            # logging.info(f"セクション [{section}] が存在しないため、キー '{key}' にフォールバック値 '{fallback}' を使用します。")
            self.set(section, key, fallback) # これによりセクションも作成される
            return fallback
        elif not self.config.has_section(section):
            # セクションが存在せず、fallback もない場合は None (またはエラー)
            # logging.warning(f"セクション [{section}] が存在しません。キー '{key}' の取得に失敗しました。")
            return None


        if not self.config.has_option(section, key) and fallback is not None:
            # オプションが存在せず、fallback がある場合は、その値を設定して返す
            # logging.info(f"キー '{key}' (セクション [{section}]) が存在しないため、フォールバック値 '{fallback}' を使用します。")
            self.set(section, key, fallback)
            return fallback
        elif not self.config.has_option(section, key):
            # logging.warning(f"キー '{key}' (セクション [{section}]) が存在しません。")
            return None

        value = self.config.get(section, key)
        return self._auto_convert_value(value)

    def _auto_convert_value(self, value: Optional[str]) -> Any:
        """INIファイルの文字列値を適切な型に変換"""
        if value is None:
            return None

        stripped_value = value.strip()
        if not stripped_value: # 空文字列の場合
            return None # もしくは空文字列を返すか、用途に応じて変更

        # JSON文字列として解析を試みる (配列やオブジェクトの場合)
        if (stripped_value.startswith('[') and stripped_value.endswith(']')) or \
           (stripped_value.startswith('{') and stripped_value.endswith('}')):
            try:
                return json.loads(stripped_value)
            except json.JSONDecodeError:
                # JSONとしてパースできなかった場合は、そのまま文字列として扱うか、エラーログを出す
                logging.debug(f"Failed to parse '{stripped_value}' as JSON, treating as string.")
                pass # 文字列として処理を続行

        # 真偽値の判定
        lower_val = stripped_value.lower()
        if lower_val in ('true', 'yes', 'on', '1'):
            return True
        if lower_val in ('false', 'no', 'off', '0'):
            return False

        # 数値への変換
        try:
            return int(stripped_value)
        except ValueError:
            try:
                return float(stripped_value)
            except ValueError:
                # ここまで来たら通常の文字列として返す
                return value # 元の空白を含む可能性のある文字列 or stripped_value

    def set(self, section: str, key: str, value: Any) -> None:
        """設定値をINIファイルに保存可能な形式で設定"""
        if not self.config.has_section(section):
            self.config.add_section(section)
            logging.info(f"新規セクションを作成: [{section}]")

        if value is None:
            str_value = ""  # Noneは空文字列として保存
        elif isinstance(value, bool):
            str_value = "true" if value else "false"
        elif isinstance(value, (list, dict)):
            try:
                str_value = json.dumps(value, ensure_ascii=False)
            except TypeError as e:
                logging.error(f"JSONシリアライズ不可な値 ({type(value)}) をキー '{key}' (セクション [{section}]) に設定しようとしました: {e}")
                str_value = str(value) # フォールバックとして文字列化
        else:
            str_value = str(value)

        self.config.set(section, key, str_value)
        # logging.debug(f"設定値を更新準備: [{section}] {key}={str_value}")
        self.save() # setの度に保存する

    def save(self) -> None:
        """設定変更をファイルに保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            self._last_modified = self._get_modified_time() # 保存後に更新時刻を更新
            logging.info(f"設定ファイルを保存しました: {self.config_file}")
        except Exception as e:
            logging.error(f"設定ファイル保存エラー ({self.config_file}): {str(e)}")
            # raise # 保存エラーはクリティカルな場合があるので再raiseも検討

    def reload(self) -> bool:
        """
        設定ファイルを再読み込みする。
        ファイルが変更されていればリロードし True を返す。変更がなければ False を返す。
        """
        current_modified_time = self._get_modified_time()
        # current_modified_time が 0 (ファイルが存在しないかエラー) の場合も考慮
        if current_modified_time > self._last_modified and current_modified_time != 0:
            logging.info(f"設定ファイルに変更を検知しました ({self.config_file})。再読み込みします。")
            # ConfigParserを新しくインスタンス化するか、clearしてからreadする
            self.config = configparser.ConfigParser() # 新しいインスタンスで初期化
            self._load_config() # 再読み込み
            self._last_modified = current_modified_time
            return True
        # else:
            # logging.debug(f"設定ファイルに変更はありません ({self.config_file})。")
        return False

    def __str__(self) -> str:
        """現在の設定内容を文字列で表現"""
        lines = []
        for section in self.config.sections():
            lines.append(f"[{section}]")
            for key, value in self.config.items(section):
                lines.append(f"{key} = {value}")
            lines.append("") # セクション間の空行
        return "\n".join(lines)