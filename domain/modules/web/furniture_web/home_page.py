"""Home portal console page for the Furniture Agent workbench."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping


_TEMPLATE = (Path(__file__).parent / "templates" / "home_page.html").read_text(
    encoding="utf-8"
)


def _date(created_at: str) -> str:
    if len(created_at) >= 10 and created_at[4] == "-" and created_at[7] == "-":
        return created_at[:10]
    return "日期未记录"


def _quick_resume_html(projects: list[Mapping[str, Any]]) -> str:
    ready_rows = [p for p in projects if p.get("availability") == "ready"]
    if not ready_rows:
        return (
            '<div class="resume-box">'
            '<div class="resume-header">'
            '<span class="resume-label">工坊就绪 · READY TO DESIGN</span>'
            '<span class="resume-status" style="color:#5f7a70;">等待输入</span>'
            '</div>'
            '<div style="font-size:12px;color:var(--muted);margin:8px 0 12px;line-height:1.5;">'
            '当前无活动方案。在对话中向 Agent 描述房间尺寸与定制需求，即可自动生成并存盘。'
            '</div>'
            '<a class="resume-btn" href="/docs">'
            '<span>查看 API 接口调试</span>'
            '<span>↗</span>'
            '</a>'
            '</div>'
        )

    latest = ready_rows[0]
    project_id = escape(str(latest["id"]), quote=True)
    name = escape(str(latest["name"]))
    confirmed = bool(latest.get("layout_confirmed"))
    stage = "布局已确认" if confirmed else "布局待确认"
    status_color = "#277354" if confirmed else "#9b642e"
    rooms = int(latest.get("room_count", 0))
    items = int(latest.get("item_count", 0))
    revision = int(latest.get("revision_number", 1))

    return (
        '<div class="resume-box">'
        '<div class="resume-header">'
        '<span class="resume-label">最近活动方案 · QUICK RESUME</span>'
        f'<span class="resume-status" style="color:{status_color};">● {stage}</span>'
        '</div>'
        f'<a class="resume-project-name" href="/api/project/{project_id}/preview">{name}</a>'
        '<div class="resume-meta">'
        f'<span><strong>{rooms}</strong> 间房</span>'
        f'<span><strong>{items}</strong> 件家具</span>'
        f'<span>修订 r{revision}</span>'
        '</div>'
        f'<a class="resume-btn" href="/api/project/{project_id}/preview">'
        '<span>继续在 3D 画布中编辑</span>'
        '<span>↗</span>'
        '</a>'
        '</div>'
    )


def render_home_page(
    version: str,
    projects: list[Mapping[str, Any]],
) -> str:
    """Render the studio workbench console home page."""
    ready_rows = [p for p in projects if p.get("availability") == "ready"]
    quick_resume = _quick_resume_html(projects)

    return (
        _TEMPLATE.replace("__API_VERSION__", escape(version))
        .replace("__READY_COUNT__", str(len(ready_rows)))
        .replace("__QUICK_RESUME_BLOCK__", quick_resume)
    )
