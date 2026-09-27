"""项目名单页。布局画面属于这一阶段，不写在 CAD 阶段里。"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping


_PRESENCE_SCRIPT = (
    "<script>function pulsePreview(){fetch(\"/api/preview/presence\","
    "{method:\"POST\",cache:\"no-store\",keepalive:true}).catch(function(){})}"
    "pulsePreview();setInterval(pulsePreview,1000);</script>"
)


def _status(confirmed: bool) -> str:
    return "布局已确认" if confirmed else "还没确认"


def _date(created_at: str) -> str:
    if len(created_at) >= 10 and created_at[4] == "-" and created_at[7] == "-":
        return created_at[:10]
    return created_at


def render_project_list(rows: list[Mapping[str, Any]]) -> str:
    """HTML for the saved-project list. Each row opens that layout."""
    if rows:
        items = []
        for row in rows:
            href = f"/api/project/{escape(str(row['id']), quote=True)}/preview"
            meta = (
                f"{_date(str(row['created_at']))} · "
                f"修订 {int(row['revision_number'])} · "
                f"{_status(bool(row['layout_confirmed']))}"
            )
            items.append(
                "<li><a class=\"row\" href=\""
                + href
                + "\"><span class=\"name\">"
                + escape(str(row["name"]))
                + "</span><span class=\"meta\">"
                + escape(meta)
                + "</span></a></li>"
            )
        body = "<ul class=\"projects\">" + "".join(items) + "</ul>"
    else:
        body = (
            "<p class=\"empty\">还没有项目。先在对话里做完一版布局；"
            "关机后再打开这一页，它还在。</p>"
        )
    return (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>已经做过的项目</title><style>"
        "body{margin:0;font-family:sans-serif;color:#0f172a;background:#f8fafc}"
        "main{max-width:640px;margin:0 auto;padding:40px 20px}"
        "h1{font-size:28px;margin:0 0 8px}"
        "p.lead,p.empty{color:#64748b;line-height:1.6}"
        "ul.projects{list-style:none;margin:24px 0;padding:0;display:flex;flex-direction:column;gap:10px}"
        "a.row{display:flex;justify-content:space-between;gap:16px;align-items:baseline;"
        "text-decoration:none;color:inherit;background:#fff;border:1px solid #e2e8f0;"
        "border-radius:12px;padding:14px 16px}"
        "a.row:hover{border-color:#4f46e5}"
        "span.name{font-weight:700}"
        "span.meta{color:#64748b;font-size:13px;white-space:nowrap}"
        "a.docs{color:#4f46e5;font-size:13px}"
        "</style></head><body><main>"
        "<h1>已经做过的项目</h1>"
        "<p class=\"lead\">点一个项目打开那一版布局。关机后项目还在。"
        "关掉最后一页后，预览服务会自己停。</p>"
        + body
        + "<p><a class=\"docs\" href=\"/docs\">API 文档</a></p>"
        "</main>"
        + _PRESENCE_SCRIPT
        + "</body></html>"
    )
