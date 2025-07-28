"""
Dispyplus - Discord.py Enhancement Library

A utility library to enhance discord.py bot development with advanced pagination, 
forms, configuration management, and UI components.
"""

__version__ = "0.2.0"
__author__ = "meow"
__license__ = "MIT"

from .config import Config, ConfigManager
from .events import EventHandler, CustomEvent
from .ui import Paginator, ConfirmDialog, EmbedPaginator
from .forms import Form, FormField, FormModal
from .utils import get_user_avatar, format_timestamp, safe_send

__all__ = [
    "Config",
    "ConfigManager", 
    "EventHandler",
    "CustomEvent",
    "Paginator",
    "ConfirmDialog",
    "EmbedPaginator",
    "Form",
    "FormField", 
    "FormModal",
    "get_user_avatar",
    "format_timestamp",
    "safe_send"
]