"""
Dispyplus - A Discord.py Bot Enhancement Library
"""

__version__ = "0.1.1"  # ライブラリのバージョン (リファクタリングに伴い更新)

# 主要なクラスや関数をインポートして、ライブラリのルートからアクセスできるようにする
from .Dispyplus import DispyplusBot
from .config import ConfigManager
from .context import EnhancedContext
from .enums import InteractionType

# event_manager と event_decorators からインポート
from .event_manager import CustomEventManager
from .event_decorators import (
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
    on_config_reload, # 追加
)
from .decorators import (
    hybrid_group,
    permission_check,
    log_execution,
)
# ui と ui_components からインポート
from .ui import (
    ConfirmationView,
    PaginatedSelectView,
    SimpleSelectView,
)
from .ui_components import (
    EnhancedView,
    InteractiveSelect, # InteractiveSelect は ui_components に移動した
    AdvancedSelect,   # AdvancedSelect は ui_components に移動した
    TimeoutSelect,
    PageButton,
    AdvancedSelectMenu,
)

# logging_utils, tasks, webhook, utils は直接公開せず、
# DispyplusBotクラスのメソッド経由での利用を想定（必要であれば公開も検討）

__all__ = [
    "DispyplusBot",
    "ConfigManager",
    "EnhancedContext",
    "InteractionType",
    "CustomEventManager",
    # Event decorators
    "on_message_contains", "on_message_matches",
    "on_reaction_add", "on_reaction_remove",
    "on_typing_in", "on_user_typing",
    "on_user_voice_join", "on_user_voice_leave", "on_user_voice_move",
    "on_member_nickname_update", "on_member_role_add", "on_member_role_remove", "on_member_status_update",
    "on_guild_name_change", "on_guild_owner_change", "on_config_reload",
    # General decorators
    "hybrid_group", "permission_check", "log_execution",
    # UI elements
    "ConfirmationView", "PaginatedSelectView", "SimpleSelectView",
    "EnhancedView", "InteractiveSelect", "AdvancedSelect",
    "TimeoutSelect", "PageButton", "AdvancedSelectMenu",
    # "Paginator" は other.py から削除され、ui.py にも明確な定義がないため、一旦 __all__ から削除
    # 必要であれば ui.py に Paginator を再実装し、ここに追加
]
