import os
import configparser
import logging
import json
from typing import Any, Optional

class ConfigManager:

    def __init__(self, config_file: str='config.ini', default_config: Optional[dict]=None):
        self.config_file = os.path.abspath(config_file)
        self.config = configparser.ConfigParser()
        self._ensure_config_exists()
        self._load_config()
        if default_config:
            self._apply_defaults(default_config)
        self._last_modified = self._get_modified_time()

    def _ensure_config_exists(self) -> None:
        config_dir = os.path.dirname(self.config_file)
        os.makedirs(config_dir, exist_ok=True)
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write('[DEFAULT]\n')
            logging.info(f'Created new config file: {self.config_file}')

    def _load_config(self) -> None:
        try:
            read_ok = self.config.read(self.config_file, encoding='utf-8')
            if not read_ok:
                logging.warning(f'Could not read config file: {self.config_file}')
        except configparser.Error as e:
            logging.error(f'Error parsing config file: {self.config_file}, {str(e)}')
        except Exception as e:
            logging.error(f'Unexpected error while reading config file: {self.config_file}, {str(e)}')
            raise

    def _get_modified_time(self) -> float:
        try:
            if os.path.exists(self.config_file):
                return os.path.getmtime(self.config_file)
        except OSError as e:
            logging.error(f'Error getting last modified time ({self.config_file}): {str(e)}')
        return 0

    def _apply_defaults(self, default_config: dict) -> None:
        changes_made = False
        for section, keys in default_config.items():
            for key, value in keys.items():
                if not self.config.has_option(section, key):
                    self.set(section, key, value, autosave=False)
                    logging.info(f'Added default value: [{section}] {key} = {value}')
                    changes_made = True
        if changes_made:
            self.save()

    def get(self, section: str, key: str, fallback: Optional[Any]=None) -> Any:
        if not self.config.has_section(section) and fallback is not None:
            self.set(section, key, fallback)
            return fallback
        elif not self.config.has_section(section):
            return None
        if not self.config.has_option(section, key) and fallback is not None:
            self.set(section, key, fallback)
            return fallback
        elif not self.config.has_option(section, key):
            return None
        value = self.config.get(section, key)
        return self._auto_convert_value(value)

    def _auto_convert_value(self, value: Optional[str]) -> Any:
        if value is None:
            return None
        stripped_value = value.strip()
        if not stripped_value:
            return None
        if stripped_value.startswith('[') and stripped_value.endswith(']') or (stripped_value.startswith('{') and stripped_value.endswith('}')):
            try:
                return json.loads(stripped_value)
            except json.JSONDecodeError:
                logging.debug(f"Failed to parse '{stripped_value}' as JSON, treating as string.")
                pass
        lower_val = stripped_value.lower()
        if lower_val in ('true', 'yes', 'on', '1'):
            return True
        if lower_val in ('false', 'no', 'off', '0'):
            return False
        try:
            return int(stripped_value)
        except ValueError:
            try:
                return float(stripped_value)
            except ValueError:
                return value

    def set(self, section: str, key: str, value: Any, autosave: bool=True) -> None:
        if not self.config.has_section(section):
            self.config.add_section(section)
            logging.info(f'Created new section: [{section}]')
        if value is None:
            str_value = ''
        elif isinstance(value, bool):
            str_value = 'true' if value else 'false'
        elif isinstance(value, (list, dict)):
            try:
                str_value = json.dumps(value, ensure_ascii=False)
            except TypeError as e:
                logging.error(f"Attempted to set a non-serializable value ({type(value)}) for key '{key}' in section [{section}]: {e}")
                str_value = str(value)
        else:
            str_value = str(value)
        self.config.set(section, key, str_value)
        if autosave:
            self.save()

    def save(self) -> None:
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            self._last_modified = self._get_modified_time()
            logging.info(f'Saved config file: {self.config_file}')
        except Exception as e:
            logging.error(f'Error saving config file ({self.config_file}): {str(e)}')

    def reload(self) -> bool:
        current_modified_time = self._get_modified_time()
        if current_modified_time > self._last_modified and current_modified_time != 0:
            logging.info(f'Detected change in config file ({self.config_file}). Reloading.')
            self.config = configparser.ConfigParser()
            self._load_config()
            self._last_modified = current_modified_time
            return True
        return False

    def __str__(self) -> str:
        lines = []
        for section in self.config.sections():
            lines.append(f'[{section}]')
            for key, value in self.config.items(section):
                lines.append(f'{key} = {value}')
            lines.append('')
        return '\n'.join(lines)
