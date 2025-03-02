import os
import configparser
import logging
from typing import Any, Optional
import json

class ConfigManager:
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = os.path.abspath(config_file)
        self.config = configparser.ConfigParser()
        self._ensure_config_exists()
        self._load_config()
        self._last_modified = self._get_modified_time()

    def _ensure_config_exists(self) -> None:
        """設定ファイルの存在確認と新規作成"""
        config_dir = os.path.dirname(self.config_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            logging.info(f"Created config directory: {config_dir}")
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write('# Auto-generated configuration file\n')
            logging.info(f"Created new config file: {self.config_file}")

    def _load_config(self) -> None:
        """設定ファイルを読み込む"""
        try:
            read_files = self.config.read(self.config_file, encoding='utf-8')
            if not read_files:
                logging.warning(f"Config file not found or empty: {self.config_file}")
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

    def reload(self) -> bool:
        """設定ファイルの動的再読み込み。変更があった場合はTrueを返す"""
        current_time = self._get_modified_time()
        if current_time > self._last_modified:
            self._load_config()
            self._last_modified = current_time
            return True
        return False

    def get(self, section: str, key: str, fallback: Optional[Any] = None) -> Any:
        """型推論付き設定値取得"""
        if not self.config.has_section(section):
            return fallback
            
        if not self.config.has_option(section, key):
            return fallback
            
        value = self.config.get(section, key, fallback=fallback)
        if not isinstance(value, str):
            return value
            
        # 型変換の試行
        if value.lower() in ('true', 'yes', 'on', '1'):
            return True
        if value.lower() in ('false', 'no', 'off', '0'):
            return False
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                # JSON形式の値の場合
                if value.startswith(('[', '{')):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        pass
        return value

    def set(self, section: str, key: str, value: Any) -> None:
        """設定値の保存"""
        if not self.config.has_section(section):
            self.config.add_section(section)
            
        # 複雑な型はJSON形式で保存
        if isinstance(value, (list, dict, bool)):
            value = json.dumps(value, ensure_ascii=False)
            
        self.config.set(section, key, str(value))

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

    def __str__(self) -> str:
        """現在の設定内容を文字列で表現"""
        return "\n".join(
            f"[{section}]\n" + "\n".join(
                f"{key} = {value}" for key, value in self.config.items(section)
            ) for section in self.config.sections()
        )
