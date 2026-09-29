"""Saved-project index for the layout preview."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping


_TEMPLATE = (Path(__file__).parent / "templates" / "project_list.html").read_text(
    encoding="utf-8"
)


def _date(created_at: str) -> str:
    if len(created_at) >= 10 and created_at[4] == "-" and created_at[7] == "-":
        return created_at[:10]
    return "日期未记录"


def _card(row: Mapping[str, Any]) -> str:
    project_id = escape(str(row["id"]), quote=True)
    name = escape(str(row["name"]))
    search = escape(f"{row['name']} {row['id']}", quote=True)
    availability = str(row["availability"])
    date = escape(_date(str(row["created_at"])))
    if availability == "ready":
        confirmed = bool(row["layout_confirmed"])
        stage = "布局已确认" if confirmed else "布局待确认"
        stage_class = "confirmed" if confirmed else "pending"
        revision = int(row["revision_number"])
        rooms = int(row["room_count"])
        items = int(row["item_count"])
        return (
            f'<a class="project-card" data-search="{search}" '
            f'href="/api/project/{project_id}/preview" '
            f'aria-label="打开工程 {name}">'
            '<span class="card-top"><span class="project-icon" aria-hidden="true">'
            '<span></span><span></span><span></span></span>'
            '<span class="availability ready"><i></i>可打开</span></span>'
            f'<span class="card-name">{name}</span>'
            f'<span class="card-id">{project_id}</span>'
            f'<span class="card-data"><span><strong>{rooms}</strong> 间房</span>'
            f'<span><strong>{items}</strong> 件家具</span>'
            f'<span>修订 {revision}</span></span>'
            '<span class="card-bottom">'
            f'<span class="stage {stage_class}">{stage}</span>'
            f'<span class="date">创建于 {date}</span>'
            '<span class="open-arrow" aria-hidden="true">↗</span>'
            '</span></a>'
        )
    label = "格式不兼容" if availability == "incompatible" else "暂不可打开"
    reason = escape(str(row["reason"]))
    return (
        f'<article class="archive-row project-card unavailable" data-search="{search}" '
        f'aria-label="工程 {name}，{label}">'
        '<span class="archive-row-main">'
        f'<span class="card-name">{name}</span><span class="card-id">{project_id}</span>'
        '</span>'
        f'<span class="archive-reason">{reason}</span>'
        f'<span class="date">{date}</span>'
        f'<span class="availability issue"><i></i>{label}</span>'
        '</article>'
    )


def render_project_list(rows: list[Mapping[str, Any]]) -> str:
    """Render openable projects and explain why other saved projects cannot open."""
    ready_rows = [row for row in rows if row["availability"] == "ready"]
    issue_rows = [row for row in rows if row["availability"] != "ready"]
    cards = "".join(_card(row) for row in ready_rows)
    if not ready_rows:
        cards = (
            '<div class="empty-state"><span class="empty-icon" aria-hidden="true">◇</span>'
            '<h2>还没有可打开的工程</h2>'
            '<p>在对话中创建第一版布局后，工程会出现在这里。</p></div>'
        )
    issues = ""
    if issue_rows:
        issues = (
            '<details class="archive" id="unavailable-projects">'
            f'<summary><span>当前布局页暂不可打开</span><strong>{len(issue_rows)}</strong>'
            '<span class="summary-arrow" aria-hidden="true">⌄</span></summary>'
            '<div class="archive-list">'
            + "".join(_card(row) for row in issue_rows)
            + '</div></details>'
        )
    return (
        _TEMPLATE.replace("__READY_CARDS__", cards)
        .replace("__ISSUE_SECTION__", issues)
        .replace("__TOTAL_COUNT__", str(len(rows)))
        .replace("__READY_COUNT__", str(len(ready_rows)))
        .replace("__ISSUE_COUNT__", str(len(issue_rows)))
    )
