from enum import Enum, auto

class InteractionType(Enum):
    UNKNOWN = auto()
    SLASH_COMMAND = auto()
    MESSAGE_COMPONENT = auto()
    MODAL_SUBMIT = auto()
