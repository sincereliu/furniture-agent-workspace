"""浏览器里打开的房间页。可拖、只读预览、分享都是这一页。

点选一件家具后拖动：靠墙件沿墙滑动（发 `offset_mm`），自由件平面移动（发
`origin_x_mm`/`origin_y_mm`）。选中后家具上方有两个手柄——橙色圆点拖了是旋转
（发 `rotation_z_deg`），蓝色圆点拖了改离地高度（发 `origin_z_mm`）；墙摆的
旋转由 `host_wall` 派生，所以旋转墙摆会在同一个 op 里改成自由摆放。靠墙件往
房间内拖过阈值也会转成自由摆放。

画面、转视角、缩放和点选由 three.js 负责。房间坐标仍是 X 东、Y 南、Z 上。
相机接近水平（pitch 很小）时地面射线求交会退化，所以那种视角下拖动改成在「水平轴 +
高度」这个竖直平面里走，上下拖就是改高度。

选中件的四向净距（到最近的家具/障碍物/墙）直接画在图上：先找同一高度带、垂直
方向有重叠的最近邻，找不到才退到墙。

拖动与旋转**本地就按服务端的摆放检查求解**（见 placement_check.py，脚本在 templates/room_page.js：底面正面积
重叠且高度重叠才算干涉，贴边接触放行；另查越界和遮挡门窗洞口）。过不去就停在
接触处，不会先穿过再回弹。求解在**整数毫米**上进行，
和服务端落盘取整口径一致，预览即落盘值。

拖动期间只做本地预览，松手才发**一个** edit op，由后端重算并校验——失败会显示
原因，不回退本地已画的形状。右侧宽、深、高回车后另发一次 `resize`。沿墙铺满的
宽度、沿墙起点和朝向由空段算出，这一页只改离地高度。

项目预览复用同一块画布，但是只读：不发 edit op，按版本号换上新的包络。
"""

from __future__ import annotations

from html import escape
from pathlib import Path
import json
from typing import Any

from .scene import RoomScene


EDITOR_WIDTH_PX = 960
EDITOR_HEIGHT_PX = 600


def room_page_payload(scene: RoomScene) -> dict[str, Any]:
    """房间页要画的数据。重新打开后还是这个形状。"""
    return {
        "room": scene.room.to_dict(),
        # 与服务端 PlacedItem.to_dict() 同构：编辑后用同一形状替换，不引入第二种结构。
        "items": [item.to_dict() for item in scene.items],
        "obstacles": [
            {
                "label": obstacle.kind,
                "footprint": [list(point) for point in obstacle.footprint],
                "z_start": obstacle.z_mm,
                "z_end": obstacle.z_mm + obstacle.height_mm,
            }
            for obstacle in scene.room.obstacles
        ],
        "openings": [opening.to_dict() for opening in scene.room.openings],
    }


def _json_for_script(payload: object) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


_EDITOR_TIPS = (
    "拖动时干涉、越界或遮挡门窗洞口会停在接触处<br>"
    "选中件：紫线是四向净距，灰线是本体宽/深/高<br>"
    "橙点或旋转环拖了调朝向（Shift 1°）· 蓝点调离地高度<br>"
    "前/后/左/右视里上下拖 = 改高度<br>"
    "右侧的距离 / 朝向 / 离地 / 宽深高可输入，回车保存；也可用 − / ＋ 走整数档<br>"
    "空白处拖拽转视角（保留选中）· 右键/中键/Shift+左键拖拽平移 · 滚轮缩放 · Esc 取消选中<br>"
    "双击切正视图，再双击回原视角；保留缩放与选中"
)

_PREVIEW_TIPS = (
    "只读预览，位置由对话更新。<br>"
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放<br>"
    "双击切正视图，再双击回原视角；保留缩放与选中 · Esc 取消选中<br>"
    "有多间房时点上方房间名切换，地址栏 ?room= 直接指向某间房<br>"
    "关掉这一页后预览服务会自己停；点「退出」则马上停"
)
_SHARE_TIPS = (
    "这是只读分享链接：只看不改，位置由房主那边更新。<br>"
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放<br>"
    "双击切正视图，再双击回原视角；保留缩放与选中 · Esc 取消选中<br>"
    "有多间房时点上方房间名切换，地址栏 ?room= 直接指向某间房"
)
_STORED_VIEWER_TIPS = (
    "只读布局预览。<br>"
    "点击家具查看尺寸与净距；标注可切换为全部、选中或关闭。<br>"
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放<br>"
    "双击切正视图，再双击回原视角；保留缩放与选中 · Esc 取消选中"
)
#: 可编辑的项目页（本机来源）——提示语要说清"什么时候要审、什么时候算数"。
_PROJECT_EDITOR_TIPS = (
    "拖动改位置（与别的家具或障碍物干涉、越出房间或遮挡门窗洞口时停在接触处）<br>"
    "选中件：橙点或旋转环改朝向 · 蓝点改离地高度 · 右侧宽/深/高回车后保存<br>"
    "还没跑下游时，改动就落在**这一版**上（版号不变）；改到哪一间，哪一间就要重看一眼<br>"
    "空白处拖拽转视角 · 双击吸到最近的正视图 · 滚轮缩放<br>"
    "多间房时点上方房间名切换，地址栏 ?room= 直接指向某间房"
)
_SHUTDOWN_BUTTON = (
    '<button type="button" id="shutdown-preview">退出</button>'
)
# 页面身份的牌子：一眼说清「这一页能不能改、改了算不算数」。
# 预览页=只读投影，草稿页=可改但不进项目；两者都不写项目，写项目只走对话或确认流程。
# 分享形态（预览页带 ?mode=view）另加一块牌子：这页是给外人看的，转发链接即可。
# 注意：`?mode=view` 只是"表达"，不是权限——地址栏谁都能改，真正的门在服务端
# （`server.access_scope()`，见 runtime-contract「写权限」段）。
_PREVIEW_BADGE = "只读预览 · 由对话更新"
_DRAFT_BADGE = "草稿 · 不影响项目"
_SHARE_BADGE = "只读分享 · 链接可转发"
_PROJECT_EDIT_BADGE = "可直接拖动 · 无下游产物时改的是同一版"


def _render_canvas_html(
    *,
    scene_id: str,
    scene_payload: dict[str, Any],
    rooms: list[dict[str, Any]],
    version: str,
    read_only: bool,
    poll_url: str,
    heading_suffix: str,
    tips: str,
    app_label: str,
    mode_badge: str,
    shutdown_button: str,
    share_form: bool = False,
    edit_url: str = "",
    undo_url: str = "",
    presence: bool = True,
) -> str:
    room_name = str(scene_payload["room"]["name"])
    heading = f"{room_name} · {heading_suffix}"
    body_class = " ".join(
        name for name in ("readonly" if read_only else "", "share" if share_form else "") if name
    )
    return (
        _EDITOR_HTML.replace("__SCENE_JSON__", _json_for_script(scene_payload))
        .replace("__SCENE_ID__", escape(scene_id, quote=True))
        .replace("__HEADING__", escape(heading, quote=True))
        .replace("__HEADING_SUFFIX__", _json_for_script(heading_suffix))
        .replace("__MODE_BADGE__", escape(mode_badge, quote=True))
        .replace("__READ_ONLY__", "true" if read_only else "false")
        .replace("__SHARE_FORM__", "true" if share_form else "false")
        .replace("__PRESENCE__", "true" if presence else "false")
        .replace("__POLL_URL__", _json_for_script(poll_url))
        .replace("__EDIT_URL__", _json_for_script(edit_url))
        .replace("__UNDO_URL__", _json_for_script(undo_url))
        .replace("__ROOMS_JSON__", _json_for_script(rooms))
        .replace("__VERSION_JSON__", _json_for_script(version))
        .replace("__BODY_CLASS__", body_class)
        .replace("__APP_LABEL__", escape(app_label, quote=True))
        .replace("__TIPS__", tips)
        .replace("__SHUTDOWN_BUTTON__", shutdown_button)
    )


def render_draft_page(scene_id: str, scene: RoomScene) -> dict[str, object]:
    """单间草稿页。"""
    payload = room_page_payload(scene)
    html = _render_canvas_html(
        scene_id=scene_id,
        scene_payload=payload,
        rooms=[],
        version="",
        read_only=False,
        poll_url="",
        heading_suffix="布局编辑",
        tips=_EDITOR_TIPS,
        app_label="可编辑家具布局",
        mode_badge=_DRAFT_BADGE,
        shutdown_button="",
    )
    return {
        "media_type": "text/html",
        "view_kind": "editable_envelope",
        "scene_id": scene_id,
        "width_px": EDITOR_WIDTH_PX,
        "height_px": EDITOR_HEIGHT_PX,
        "controls": [
            "select_item",
            "drag_item",
            "drag_rotate_handle",
            "drag_height_handle",
            "front_orientation",
            "manual_distance_input",
            "manual_rotation_input",
            "view_transition",
            "dimension_readout",
            "item_size_readout",
            "view_elevation",
            "orthographic_view_select",
            "double_click_snap",
            "drag_orbit",
            "drag_pan",
            "wheel_zoom",
            "placement_stop",
        ],
        "alt_text": (
            f"{scene.room.name}的可编辑外形尺寸视图；点击家具外形尺寸任意位置可选中，"
            "拖动改位置（与别的家具或障碍物干涉、越出房间或遮挡门窗洞口时停在接触处），"
            "拖橙点或旋转环改朝向、拖蓝点改离地高度；"
            "每件的正面用绿色描边标出（约定：局部 +Y 为正面），选中件还有指向正面的箭头；"
            "选中件四周显示到最近邻的净距，并沿自身局部轴标出宽/深/高；"
            "净距、朝向、离地高度都能在右侧直接输入；"
            "视角从下拉里选正视图（俯视/仰视/前/后/左/右），「复位」回默认视角，"
            "双击画面吸到最近的正视图、再双击回到自由视角；"
            "空白处拖动转视角、右键或 Shift+左键拖动平移、滚轮缩放"
        ),
        "html": html,
    }


def render_viewer(scene: RoomScene) -> dict[str, object]:
    """Stored read-only preview, rendered with the same room template as live pages."""
    return {
        "media_type": "text/html",
        "view_kind": "interactive_orbit_envelope",
        "width_px": EDITOR_WIDTH_PX,
        "height_px": EDITOR_HEIGHT_PX,
        "controls": [
            "drag_orbit", "drag_pan", "wheel_zoom", "orthographic_view_select",
            "double_click_snap", "reset",
        ],
        "alt_text": f"{scene.room.name}的只读三维布局；拖拽旋转、平移、滚轮缩放并切换正视图",
        "html": _render_canvas_html(
            scene_id=scene.room.id,
            scene_payload=room_page_payload(scene),
            rooms=[],
            version="",
            read_only=True,
            poll_url="",
            heading_suffix="布局预览",
            tips=_STORED_VIEWER_TIPS,
            app_label="只读家具布局",
            mode_badge="只读布局",
            shutdown_button="",
            presence=False,
        ),
    }


def render_project_page(
    project_id: str,
    document: dict[str, Any],
    *,
    mode: str | None = None,
    read_only: bool = True,
) -> str:
    """项目里打开的房间页。页面按 `document` 里的版本换包络。

    `read_only` 由**服务端按权限**决定（本机来源可编辑；其余只读），`mode="view"` 再强制只读。
    之所以不靠 URL 参数判权限：参数谁都能改（见 runtime-contract「写权限」段）。
    可编辑时页面还要自己拿到**编辑租约**才算真的能写——那是页面的事，见 workflow_lease.py。
    """
    rooms = list(document["rooms"])
    if not rooms:
        raise ValueError("project layout has no rooms")
    first = rooms[0]["scene"]
    if not isinstance(first, dict):
        raise ValueError("project room scene must be an object")
    share_form = mode == "view"
    if share_form:
        read_only = True
    return _render_canvas_html(
        scene_id=project_id,
        scene_payload=first,
        rooms=rooms,
        version=str(document["version"]),
        read_only=read_only,
        poll_url=f"/api/project/{project_id}/layout",
        edit_url=f"/api/project/{project_id}/layout/edit",
        undo_url=f"/api/project/{project_id}/layout/undo",
        heading_suffix="布局预览",
        tips=_SHARE_TIPS if share_form else (
            _PREVIEW_TIPS if read_only else _PROJECT_EDITOR_TIPS
        ),
        app_label="只读布局分享" if share_form else (
            "只读布局预览" if read_only else "可编辑家具布局"
        ),
        mode_badge=(
            _SHARE_BADGE if share_form
            else _PREVIEW_BADGE if read_only
            else _PROJECT_EDIT_BADGE
        ),
        shutdown_button="" if share_form else _SHUTDOWN_BUTTON,
        share_form=share_form,
    )


_TEMPLATES = Path(__file__).resolve().parent / "templates"
_EDITOR_HTML = (_TEMPLATES / "room_page.html").read_text(encoding="utf-8").replace(
    "__ROOM_SCRIPT__", (_TEMPLATES / "room_page.js").read_text(encoding="utf-8")
)
