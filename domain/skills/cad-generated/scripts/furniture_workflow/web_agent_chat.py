"""Compatibility imports for the optional page assistant.

Core furniture workflow modules do not import this adapter. New callers use
furniture_chat.conversation directly.
"""
from furniture_chat.conversation import (
    WebChatError,
    build_system_prompt,
    clear_chat_history,
    get_project_chat_state,
    load_chat_history,
    save_chat_history,
    send_project_chat_message,
)

__all__ = [
    "WebChatError", "build_system_prompt", "clear_chat_history",
    "get_project_chat_state", "load_chat_history", "save_chat_history",
    "send_project_chat_message",
]
