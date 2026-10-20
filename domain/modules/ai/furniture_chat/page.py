"""Own the assistant's markup, assets, and its two explicit layout hooks."""

from __future__ import annotations

import json
from pathlib import Path

from furniture_web.room_page import PageExtension

ROOT = Path(__file__).resolve().parent


def page_extension(project_id: str) -> PageExtension:
    config = json.dumps({
        "chatUrl": f"/api/project/{project_id}/chat",
        "llmConfigUrl": "/api/llm/config",
    }, ensure_ascii=False).replace("<", "\\u003c")
    script_version = (ROOT / "static" / "layout_chat.js").stat().st_mtime_ns
    return PageExtension(
        styles="<style>" + (ROOT / "templates" / "chat.css").read_text(encoding="utf-8") + "</style>",
        toolbar=(ROOT / "templates" / "toolbar.html").read_text(encoding="utf-8"),
        panel=(ROOT / "templates" / "panel.html").read_text(encoding="utf-8"),
        dialogs=(ROOT / "templates" / "dialog.html").read_text(encoding="utf-8"),
        script=(
            f'import {{ mountProjectChat }} from "/web-chat/layout_chat.js?v={script_version}";\n'
            f'mountProjectChat({{...{config}, '
            'onProjectUpdated:pageHost.onProjectUpdated, '
            'onStatusToast:pageHost.onStatusToast});'
        ),
    )
