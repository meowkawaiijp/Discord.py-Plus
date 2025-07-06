"""
Dispyplus - A Discord.py Bot Enhancement Library
"""

__version__ = "0.1.0"  # ライブラリのバージョン

# 主要なクラスや関数をインポートして、ライブラリのルートからアクセスできるようにする
from .Dispyplus import DispyplusBot
from .config import ConfigManager
from .custom_events import (
    CustomEventManager,
    on_message_contains,
    on_message_matches,
    on_reaction_add,
    on_reaction_remove,
    on_typing_in,
    on_user_typing,
    on_user_voice_join,
    on_user_voice_leave,
    on_user_voice_move,
    on_member_nickname_update,
    on_member_role_add,
    on_member_role_remove,
    on_member_status_update,
    on_guild_name_change,
    on_guild_owner_change,
)
from .decorators import (
    hybrid_group,
    permission_check,
    log_execution,
)
from .other import (
    EnhancedContext,
    EnhancedView,
    InteractiveSelect,
    AdvancedSelect,
    InteractionType,
)
from .ui import ConfirmationView # Added import from .ui

__all__ = [
    "DispyplusBot",
    "ConfigManager",
    "CustomEventManager",
    "on_message_contains",
    "on_message_matches",
    "on_reaction_add",
    "on_reaction_remove",
    "on_typing_in",
    "on_user_typing",
    "on_user_voice_join",
    "on_user_voice_leave",
    "on_user_voice_move",
    "on_member_nickname_update",
    "on_member_role_add",
    "on_member_role_remove",
    "on_member_status_update",
    "on_guild_name_change",
    "on_guild_owner_change",
    "hybrid_group",
    "permission_check",
    "log_execution",
    "EnhancedContext",
    "EnhancedView",
    "Paginator",
    "ConfirmationView",
    "InteractiveSelect",
    "AdvancedSelect",
    "InteractionType",
]
