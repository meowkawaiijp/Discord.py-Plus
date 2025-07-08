# Dispyplus: ライブラリ内で使用される共通の列挙型を定義するモジュール
from enum import Enum, auto

class InteractionType(Enum):
    """インタラクションの種類を示す列挙型です。
    EnhancedContext.interaction_type で使用されます。
    """
    UNKNOWN = auto() #: 不明なインタラクションタイプ。
    SLASH_COMMAND = auto() #: スラッシュコマンドまたはコンテキストメニューコマンド。
    MESSAGE_COMPONENT = auto() #: ボタン、選択メニューなどのメッセージコンポーネント。
    MODAL_SUBMIT = auto() #: モーダル送信。
