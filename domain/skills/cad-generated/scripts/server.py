"""本机运行时进程。房间场景路由和布局预览在 layout-plan，这里只把它们挂上。

看已经做过的项目，从布局阶段启动，不要把这一进程当成 CAD 阶段：

    .venv/Scripts/python.exe domain/skills/layout-plan/scripts/open_projects.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Literal

SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_ROOT = WORKSPACE_ROOT / "generated"
STORE_ROOT = WORKSPACE_ROOT / "store"
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from furniture_layout.cabinet_entry import (
    CabinetNotExecutable,
    CabinetNotFound,
    cabinet_for_panel_page,
)
from furniture_layout.room_page import render_project_page
from furniture_panel_planning.cabinet_identity import cabinets_from_output
from furniture_panel_planning.cabinet_panel_page import (
    panel_structure_view,
    render_cabinet_panel_page,
)
from furniture_layout.project_list import render_project_list
from furniture_layout.open_preview import (
    panel_version,
    preview_server_is_up,
    preview_page_data,
    project_list_url,
)
from furniture_layout import room_http
from furniture_layout.layout_events import bind_layout_events, router as layout_event_router
from furniture_workflow.project_layout_edit import (
    LAYOUT_EDIT_ENV,
    LayoutEditDisabled,
    VersionConflict,
    edit_project_decisions,
    edit_project_layout,
    save_cabinet_grain,
    undo_layout_edit,
)
from furniture_workflow.workflow_lease import (
    LeaseHeld,
    LeaseLost,
    acquire,
    release,
    transfer,
)
from furniture_workflow.workflow_store import JsonProjectStore, project_preview_status
from furniture_workflow.workflow_state import WorkflowStage
from furniture_workflow.web_agent_chat import (
    WebChatError,
    clear_chat_history,
    get_project_chat_state,
    public_llm_config,
    save_llm_config,
    send_project_chat_message,
)

API_VERSION = "0.8.0"
# 最后一页关掉后，超过这个秒数没有页面报「还在」，预览进程就退出。
#
# 取值理由（两次调大的经过）：
#   · 5 秒 → 30 秒：进程常是"起服务 + 开浏览器"两步，5 秒内浏览器还没发出第一次 presence，
#     服务就自杀了，人看到的现象是"页面打不开"。
#   · 30 秒 → 300 秒：列表页和板件页靠一条开着的 presence 流续上，不再自己定时打卡。
#     浏览器会把后台标签页的定时器限流（Chrome 可降到每分钟一次）。宽限期 30 秒时，
#     页面切到后台超过半分钟就会被判为"页面都关了"，切回来已经连不上。
#     布局页的事件连接由服务端在连接还在时自己续上，不受这个限流影响。
#     5 分钟足以覆盖列表和板件页的后台限流，同时仍然能在真正关掉页面后自动回收进程。
PRESENCE_GRACE_SECONDS = 300.0
SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_LOCAL_HOSTS = {"127.0.0.1", "::1"}
#: 写请求带回编辑租约凭据的头。
_LEASE_HEADER = "X-Edit-Lease"
ACCESS_LOCAL = "local"
ACCESS_DENIED = "denied"


def access_scope(request: Request) -> str:
    """这一次请求从哪儿来。写权限的唯一判据就在这里，别散到各个端点里。

    现在只有两种来源：本机进程（`local`）和其余（`denied`）——服务只监听 `127.0.0.1`，
    所以今天没有第三个来源。将来要给外人只读分享时，在这一处多认一种凭证（`shared`），
    各写端点的门不用动。**URL 参数不是权限**：`?mode=view` 只是页面表达，谁都能改地址栏。
    """
    host = request.client.host if request.client is not None else ""
    return ACCESS_LOCAL if host in _LOCAL_HOSTS else ACCESS_DENIED


def may_edit(request: Request) -> bool:
    """写操作（落盘、停进程）只对本机来源开放。"""
    return access_scope(request) == ACCESS_LOCAL

app = FastAPI(
    title="Furniture Agent — 房间场景布局",
    version=API_VERSION,
    description=(
        "独立房间场景 API：多件包络摆放、摆放检查、SVG 预览、互动 Viewer 与房间 CAD。"
        "项目布局预览只读 store 里的最新布局，对话修订后由页面自己刷新。"
        "家具生成走交互工具面，不提供一次性拆单批处理。"
    ),
)

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(OUTPUT_ROOT)), name="generated")
# 固定的 three.js 0.186.0。页面从这里加载，不放在布局技能里。
THREE_DIST = WORKSPACE_ROOT / "vendor" / "three" / "0.186.0"
LAYOUT_PAGE = (
    WORKSPACE_ROOT
    / "domain"
    / "skills"
    / "layout-plan"
    / "scripts"
    / "furniture_layout"
    / "static"
)
app.mount("/vendor/three/0.186.0", StaticFiles(directory=str(THREE_DIST)), name="three_0_186_0")
class _FreshStaticFiles(StaticFiles):
    """画面脚本每次都重新取，避免改了旋转箭头浏览器还画旧的。"""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


app.mount("/layout-view", _FreshStaticFiles(directory=str(LAYOUT_PAGE)), name="layout_view")

def _room_output_root() -> Path:
    return OUTPUT_ROOT


room_http.bind_room_host(
    workspace_root=WORKSPACE_ROOT,
    output_root=_room_output_root,
    may_edit=may_edit,
)
app.include_router(room_http.router)


def _touch_preview_presence() -> None:
    app.state.preview_presence_at = time.monotonic()


def _preview_pages() -> int:
    return int(getattr(app.state, "preview_page_count", 0) or 0)


def note_preview_page_opened() -> None:
    """一条页面连接打开了。开着的时候进程不因为空闲退出。"""
    app.state.preview_page_count = _preview_pages() + 1
    _touch_preview_presence()


def note_preview_page_closed() -> None:
    """这条连接断了。最后一页关掉，宽限期从这一刻算。"""
    app.state.preview_page_count = max(0, _preview_pages() - 1)
    if app.state.preview_page_count == 0:
        _touch_preview_presence()


bind_layout_events(
    store_root=lambda: STORE_ROOT,
    may_edit=may_edit,
    touch_presence=note_preview_page_opened,
    release_presence=note_preview_page_closed,
)
app.include_router(layout_event_router)

# 测试和项目编辑请求仍用这些名字。实现在布局阶段。
RoomOpeningRequest = room_http.RoomOpeningRequest
RoomObstacleRequest = room_http.RoomObstacleRequest
RoomRequest = room_http.RoomRequest
ItemPlacementRequest = room_http.ItemPlacementRequest
SceneItemRequest = room_http.SceneItemRequest
RoomSceneRequest = room_http.RoomSceneRequest
RoomSceneResponse = room_http.RoomSceneResponse
RoomSceneSaveRequest = room_http.RoomSceneSaveRequest
RoomSceneEditRequest = room_http.RoomSceneEditRequest
plan_room = room_http.plan_room
plan_room_preview = room_http.plan_room_preview
plan_room_viewer = room_http.plan_room_viewer
plan_room_cad = room_http.plan_room_cad
save_room_scene = room_http.save_room_scene
load_room_scene = room_http.load_room_scene
list_room_scenes = room_http.list_room_scenes
edit_room_scene = room_http.edit_room_scene
room_scene_editor = room_http.room_scene_editor


class ProjectLayoutEditRequest(BaseModel):
    """页面上改项目布局：改一件（`move` / `rotate` / `resize`）。

    `expected_version` 必填：它是页面最近一次从 `/layout` 看到的 `version`。
    对不上就拒绝——页面上的画面已经过期，不能拿它去覆盖。
    """

    model_config = ConfigDict(extra="forbid")

    expected_version: str = Field(..., min_length=1, description="页面最近看到的 version")
    op: Literal["move", "rotate", "resize"]
    item_id: str = Field(..., min_length=1)
    mode: Literal["wall", "free"] | None = None
    host_wall: Literal["south", "east", "north", "west"] | None = None
    origin_x_mm: float | None = None
    origin_y_mm: float | None = None
    origin_z_mm: float | None = Field(default=None, ge=0)
    rotation_z_deg: float | None = None
    width: float | None = Field(default=None, gt=0)
    depth: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)


class ProjectLayoutUndoRequest(BaseModel):
    """撤销工作副本上的最后 N 步（只在没有下游产物时可用）。"""

    model_config = ConfigDict(extra="forbid")

    expected_version: str = Field(..., min_length=1, description="页面最近看到的 version")
    steps: int = Field(default=1, ge=1, le=50)


class ProjectDecisionRequest(BaseModel):
    """页面上对**一条待确认的说法**表态：确认它，或者划掉它。

    页面只递"动作 + 目标"：措辞由服务端写死，所以页面上按的按钮**没有原话**——
    也就没有"页面替客户编话"的余地。只追加，被表态的那条一个字不动。
    """

    model_config = ConfigDict(extra="forbid")

    expected_version: str = Field(..., min_length=1, description="页面最近看到的 version")
    action: str = Field(..., pattern="^(confirm|withdraw)$")
    target: str = Field(..., min_length=1, description="要表态的那条 decision id")


class CabinetGrainSaveRequest(BaseModel):
    """页面上改若干块板的**顺纹方向**，然后重新冻结板件。

    `axes` 是「板件 id → 顺纹轴」：`x` 沿宽 / `y` 沿深 / `z` 沿高 / `none` 不限。
    只递板件 id 和轴，其它一律由服务端按冻结结构自己去查——页面递不进自由文本，
    也改不了尺寸位置。一次请求只改这一台柜。
    """

    model_config = ConfigDict(extra="forbid")

    expected_version: str = Field(..., min_length=1, description="页面最近看到的 version")
    axes: dict[str, str] = Field(..., min_length=1, description="板件 id → 顺纹轴")


@app.get("/health")
async def health():
    return {"status": "ok", "version": API_VERSION}


def preview_should_stop(
    last: float | None,
    now: float,
    *,
    grace: float = PRESENCE_GRACE_SECONDS,
    pages: int = 0,
) -> bool:
    """True once every page connection is gone and the grace has elapsed."""
    if pages > 0:
        return False
    return last is not None and now - last >= grace


def stop_preview_server() -> bool:
    """Ask the running preview server to finish and exit."""
    server = getattr(app.state, "preview_server", None)
    if server is None:
        return False
    server.should_exit = True
    return True


@app.post("/api/preview/shutdown")
async def preview_shutdown(request: Request):
    """Stop this local preview process after the response is sent."""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="preview shutdown is local only")
    asyncio.get_running_loop().call_later(0.3, stop_preview_server)
    return {"status": "stopping"}


@app.post("/api/preview/presence")
async def preview_presence(request: Request):
    """A preview page is still open. The last page closing stops this process."""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="preview presence is local only")
    _touch_preview_presence()
    return {"status": "ok"}


async def _until_http_disconnect(request: Request) -> None:
    """等到客户端把这条连接关掉。没有接收通道就立刻返回。"""
    receive = getattr(request, "receive", None)
    if receive is None:
        return
    while True:
        message = await receive()
        if not isinstance(message, dict) or message.get("type") == "http.disconnect":
            return


async def iter_preview_presence(request: Request):
    """打开算还在，断开就不算。中间不发打卡。"""
    note_preview_page_opened()
    try:
        yield ": open\n\n"
        await _until_http_disconnect(request)
    finally:
        note_preview_page_closed()


@app.get("/api/preview/presence/stream")
async def preview_presence_stream(request: Request):
    """列表页和板件页打开这一条。连接不断就表示还在。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="preview presence is local only")
    return StreamingResponse(
        iter_preview_presence(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@app.on_event("startup")
async def watch_preview_presence() -> None:
    """After the first open page, exit once every page has been closed."""
    app.state.preview_presence_at = None

    async def watch() -> None:
        while True:
            await asyncio.sleep(1)
            last = getattr(app.state, "preview_presence_at", None)
            if preview_should_stop(last, time.monotonic(), pages=_preview_pages()):
                stop_preview_server()
                return

    asyncio.create_task(watch())


def _project_rows() -> list[dict[str, Any]]:
    return JsonProjectStore(STORE_ROOT).inspect_projects()


@app.get("/api/projects")
async def project_index_json():
    """Saved projects and whether the current preview can open each one."""
    return {"projects": _project_rows()}


@app.get("/projects", response_class=HTMLResponse)
async def project_index():
    """List saved projects; unavailable ones remain visible without a link."""
    return HTMLResponse(
        content=render_project_list(_project_rows()),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html><body style="font-family:sans-serif;padding:40px;">
    <h1>Furniture Agent</h1>
    <p><a href="/projects">已经做过的项目</a></p>
    <p><a href="/docs">API 文档 (Swagger)</a></p>
    </body></html>
    """


def enable_local_layout_edit() -> None:
    """This process is the local preview. The layout page may save."""
    os.environ[LAYOUT_EDIT_ENV] = "1"


def open_project_list_when_ready() -> None:
    """After the port answers, open the project list. Tests set the browser off."""
    if os.environ.get("FURNITURE_PREVIEW_BROWSER") == "0":
        return
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if preview_server_is_up():
            webbrowser.open(project_list_url(), new=2)
            return
        time.sleep(0.25)


def main() -> None:
    import uvicorn

    enable_local_layout_edit()
    threading.Thread(target=open_project_list_when_ready, daemon=True).start()
    config = uvicorn.Config(app, host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    app.state.preview_server = server
    server.run()


def _lease_held_detail(exc: LeaseHeld) -> dict[str, Any]:
    """423 的说明：谁在写、还有几秒——页面据此显示"另一窗口正在编辑"。"""
    return {"message": str(exc), **exc.lease.snapshot()}


class EditLeaseRequest(BaseModel):
    """申请编辑权：谁在申请 + 一个稳定的自称。"""

    model_config = ConfigDict(extra="forbid")

    holder: Literal["page", "agent"] = "page"
    label: str = Field(default="", description="谁在编辑，给人看的，如「窗口 3f2a」")
    token: str | None = Field(default=None, description="续租时带回上次拿到的 token")


@app.post("/api/project/{project_id}/edit-lease")
async def acquire_edit_lease(
    project_id: str,
    req: EditLeaseRequest,
    request: Request,
):
    """申请或续租编辑权。被别人拿着回 423（带 holder / label / expires_in）。

    写请求要带 `X-Edit-Lease: <token>`；没带、而租约在别人手里时，写也会被 423 挡下。
    """
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="edit lease is local only")
    _load_project(project_id)  # 项目不存在就 404，别把租约发给不存在的项目
    try:
        lease = acquire(
            STORE_ROOT,
            project_id,
            holder=req.holder,
            label=req.label,
            token=req.token,
        )
    except LeaseHeld as exc:
        raise HTTPException(status_code=423, detail=_lease_held_detail(exc)) from exc
    return lease.to_dict()


@app.delete("/api/project/{project_id}/edit-lease")
async def release_edit_lease(project_id: str, request: Request):
    """归还编辑权（页面关掉 / 助手做完）。页面卸载时用 keepalive 发这个。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="edit lease is local only")
    token = request.headers.get(_LEASE_HEADER, "")
    try:
        released = release(STORE_ROOT, project_id, token=token)
    except LeaseLost as exc:
        raise HTTPException(
            status_code=409, detail={"message": str(exc)}
        ) from exc
    return {"released": released}


@app.post("/api/project/{project_id}/edit-lease/takeover")
async def takeover_edit_lease(
    project_id: str,
    req: EditLeaseRequest,
    request: Request,
):
    """强制收回：人永远抢得回来（页面上「收回编辑权」按钮走这里）。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="edit lease is local only")
    _load_project(project_id)
    lease = transfer(
        STORE_ROOT,
        project_id,
        to=req.holder,
        label=req.label,
        reason="takeover",
    )
    return lease.to_dict()


def _load_project(project_id: str):
    if not SAFE_PROJECT_ID.fullmatch(project_id):
        raise HTTPException(
            status_code=422,
            detail="project_id may contain only letters, digits, '-' and '_'",
        )
    try:
        project = JsonProjectStore(STORE_ROOT).load(project_id)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        message = str(exc)
        status = 404 if message.startswith("project not found") else 422
        raise HTTPException(status_code=status, detail=message) from exc
    availability, reason = project_preview_status(project, project_id)
    if availability != "ready":
        raise HTTPException(status_code=422, detail=reason)
    return project


def _preview_page_data(project_id: str) -> dict[str, Any]:
    document = preview_page_data(_load_project(project_id), store_root=STORE_ROOT)
    if not document["rooms"]:
        raise HTTPException(status_code=422, detail="project layout has no rooms")
    return document


@app.get("/api/project/{project_id}/layout")
async def project_layout(project_id: str):
    """最新布局：房间和已摆放的包络。不含预览 HTML。"""
    return _preview_page_data(project_id)


class FrozenPanelsMissing(LookupError):
    """这个项目还没有已确认冻结的板件。"""


def confirmed_panel_structure(
    project,
    cabinet_id: str,
    *,
    store: JsonProjectStore,
) -> dict[str, Any] | None:
    """这一台已确认冻结板件的结构投影；还没有冻结板件返回 `None`。

    只读，而且只认确认过的内容——与制造 / CAD 读同一份事实（`confirmed_panel_sha256`
    指向的那份冻结点）。**没有确认就不显示结构**：页面上宁可只有外形，也不拿运行中的
    候选冒充已经认可的柜体。

    冻结文件里没有这台柜（布局改过、板件还没重跑）时抛 `LookupError`，由页面明说这件事。
    """
    revision = project.latest
    if WorkflowStage.PANELS_PLANNED.value not in revision.approved_stages:
        return None
    digest = revision.confirmed_panel_sha256
    if not digest:
        return None
    path = store.panel_path(project.id, digest)
    if not path.is_file():
        raise FrozenPanelsMissing(
            f"已确认板件文件缺失：panels/{digest}.json"
        )
    try:
        frozen = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrozenPanelsMissing(f"已确认板件文件无法读取：{exc}") from exc
    if not isinstance(frozen, dict):
        raise FrozenPanelsMissing("已确认板件文件不是对象")
    for cabinet in cabinets_from_output(frozen):
        if str(cabinet.get("id")) == cabinet_id:
            return panel_structure_view(cabinet)
    raise LookupError(f"已确认板件里没有 {cabinet_id}")


def _candidate_panel_structure(
    project,
    cabinet_id: str,
) -> dict[str, Any] | None:
    """这一台待确认候选板件的结构投影；还没有生成过板件返回 `None`。"""
    revision = project.latest
    candidate = revision.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
    if not isinstance(candidate, dict):
        return None
    for cabinet in cabinets_from_output(candidate):
        if str(cabinet.get("id")) == cabinet_id:
            return panel_structure_view(cabinet)
    raise LookupError(f"当前板件草稿里没有 {cabinet_id}")


def structure_for_panel_page(
    project,
    cabinet_id: str,
) -> tuple[dict[str, Any] | None, str]:
    """给板件页的 `(结构, 说明)`。

    已确认时读冻结文件；已生成候选但尚未确认时读当前 `stage_outputs.panel_plan` 供三维审查；
    尚未生成板件或找不到该柜时退回外形并说明原因。
    """
    revision = project.latest
    if WorkflowStage.PANELS_PLANNED.value in revision.approved_stages:
        try:
            structure = confirmed_panel_structure(
                project,
                cabinet_id,
                store=JsonProjectStore(STORE_ROOT),
            )
        except FrozenPanelsMissing as exc:
            return None, f"已确认板件读不出来，暂时只能看外形：{exc}。回布局页重跑板件后再看结构。"
        except LookupError:
            return None, "冻结板件里没有这台柜（布局可能改过）。回布局页重新生成板件后再看结构。"
        return structure, ""
    try:
        candidate = _candidate_panel_structure(project, cabinet_id)
    except LookupError:
        return None, "当前板件草稿里没有这台柜（布局可能改过）。回布局页重新生成板件后再看结构。"
    if candidate is not None:
        return (
            candidate,
            "待确认板件草稿 · 点板件看尺寸，透视看内部；确认板件阶段后可改顺纹并冻结",
        )
    return None, ""


@app.get(
    "/api/project/{project_id}/cabinets/{cabinet_id}/panels",
    response_class=HTMLResponse,
)
async def project_cabinet_panels(
    project_id: str,
    cabinet_id: str,
    request: Request,
    mode: str | None = None,
) -> HTMLResponse:
    """这一台的板件页。外形来自最新布局；结构来自已确认冻结板件或待确认候选板件（没有就只画外形）。"""
    project = _load_project(project_id)
    try:
        cabinet = cabinet_for_panel_page(project.latest.layout, cabinet_id)
    except CabinetNotFound as exc:
        raise HTTPException(status_code=404, detail="这一台不在布局里") from exc
    except CabinetNotExecutable as exc:
        raise HTTPException(status_code=422, detail="这件只占位置") from exc
    structure, stage_note = structure_for_panel_page(project, cabinet_id)
    # 「保存并冻结」要带 version 回来，服务端据此拒绝拿过期画面覆盖新内容。
    # 这里给的是**板件**版本（`panel_version`），不是布局版本——改的只有板件，
    # 布局摘要不会动，拿它当版本号这道门等于没有。
    # 只读分享或尚未确认冻结的草稿不给版本号，也不开放顺纹保存入口。
    confirmed = WorkflowStage.PANELS_PLANNED.value in project.latest.approved_stages
    editable = confirmed and may_edit(request) and mode != "view"
    return HTMLResponse(
        content=render_cabinet_panel_page(
            project_id,
            cabinet,
            share=mode == "view",
            structure=structure,
            stage_note=stage_note,
            expected_version=panel_version(project.latest) if editable else "",
        )
    )


@app.get("/api/project/{project_id}/preview", response_class=HTMLResponse)
async def project_preview(project_id: str, request: Request, mode: str | None = None) -> HTMLResponse:
    """布局页。打开后订阅 layout/events，文件变了才换包络并保持相机。

    **能不能编辑由服务端按权限渲染**：本机来源（`may_edit`）给可编辑页，其余给只读页。
    `?mode=view` 在此之上强制只读（分享形态：换牌子、去掉「退出」）——**URL 参数不是权限**：
    参数谁都能改，真正的门是 `may_edit()` 与编辑租约。
    """
    document = _preview_page_data(project_id)
    read_only = mode == "view" or not may_edit(request)
    try:
        html = render_project_page(
            project_id,
            document,
            mode=mode,
            read_only=read_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


@app.post("/api/project/{project_id}/layout/edit")
async def edit_project_layout_endpoint(
    project_id: str,
    req: ProjectLayoutEditRequest,
    request: Request,
):
    """页面上改一件家具的摆放，落成一个新 Revision（草稿）。

    三道门，顺序固定：本机来源 → 灰度开关 → 版本对得上。任何一道不过都不落盘。
    一次只改一件、只改一处；改完布局回到未确认，下游要重新走（见 references/runtime-contract.md
    「页面写项目」段）。
    """
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="editing a project layout is local only")
    payload = req.model_dump(exclude_none=True)
    expected_version = payload.pop("expected_version")
    project = _load_project(project_id)
    try:
        return edit_project_layout(
            project,
            payload,
            expected_version=expected_version,
            workspace_root=WORKSPACE_ROOT,
            store_root=STORE_ROOT,
            lease_token=request.headers.get(_LEASE_HEADER) or None,
        )
    except LeaseHeld as exc:
        raise HTTPException(status_code=423, detail=_lease_held_detail(exc)) from exc
    except LayoutEditDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except VersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "current_version": exc.current_version,
            },
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/project/{project_id}/cabinets/{cabinet_id}/grain")
async def save_cabinet_grain_endpoint(
    project_id: str,
    cabinet_id: str,
    req: CabinetGrainSaveRequest,
    request: Request,
):
    """改一台柜子里若干块板的顺纹方向：落一个新 Revision 并**重新冻结**板件。

    与布局编辑同一套门：本机来源 → 灰度开关 → 编辑租约 → 版本对得上。任何一步不过都不落盘。

    注意它会**作废下游**（制造 / BOM / CAD / 交付）：顺纹方向是板件的属性，改了它，
    依赖板件的那几份产物就不再对应当前板件。这是有意的——页面上的「保存并冻结」
    必须把这件事说清楚。
    """
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="changing panel grain is local only")
    project = _load_project(project_id)
    try:
        return save_cabinet_grain(
            project,
            cabinet_id,
            req.axes,
            expected_version=req.expected_version,
            workspace_root=WORKSPACE_ROOT,
            store_root=STORE_ROOT,
            lease_token=request.headers.get(_LEASE_HEADER) or None,
        )
    except LeaseHeld as exc:
        raise HTTPException(status_code=423, detail=_lease_held_detail(exc)) from exc
    except LayoutEditDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except VersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "current_version": exc.current_version,
            },
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/project/{project_id}/decisions")
async def project_decisions_endpoint(
    project_id: str,
    req: ProjectDecisionRequest,
    request: Request,
):
    """页面上对一条**待确认**的说法表态：确认 / 划掉。

    与布局编辑同一套门：本机来源 → 灰度开关 → 版本对得上 → 编辑租约。只追加：
    这次表态是新的一条，被它确认/撤回的那条一个字不动（见 references/decision-log-design.md）。
    """
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="deciding a project is local only")
    project = _load_project(project_id)
    try:
        return edit_project_decisions(
            project,
            action=req.action,
            target=req.target,
            expected_version=req.expected_version,
            store_root=STORE_ROOT,
            lease_token=request.headers.get(_LEASE_HEADER) or None,
        )
    except LeaseHeld as exc:
        raise HTTPException(status_code=423, detail=_lease_held_detail(exc)) from exc
    except LayoutEditDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except VersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "current_version": exc.current_version,
            },
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/project/{project_id}/layout/undo")
async def undo_project_layout_edit(
    project_id: str,
    req: ProjectLayoutUndoRequest,
    request: Request,
):
    """撤销工作副本上的最后 N 步。只在**还没有下游产物**时可用；失败整体拒绝。

    撤销本身留一条事件：它会让"已经跟人说过"的内容变样，必须看得出来。
    """
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="editing a project layout is local only")
    project = _load_project(project_id)
    try:
        return undo_layout_edit(
            project,
            expected_version=req.expected_version,
            steps=req.steps,
            workspace_root=WORKSPACE_ROOT,
            store_root=STORE_ROOT,
            lease_token=request.headers.get(_LEASE_HEADER) or None,
        )
    except LeaseHeld as exc:
        raise HTTPException(status_code=423, detail=_lease_held_detail(exc)) from exc
    except LayoutEditDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except VersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current_version": exc.current_version},
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class LlmConfigSaveRequest(BaseModel):
    """本机大模型连接配置（保存在本机 `store/_llm_config.json`，不上传仓库）。"""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["codex_cli", "agy_cli", "openai_compatible", "anthropic"] = "codex_cli"
    base_url: str = Field(default="")
    model: str = Field(..., min_length=1)
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] = "high"
    api_key: str | None = None
    clear_api_key: bool = False


class ProjectChatMessageRequest(BaseModel):
    """网页端右侧 AI 对话框发来的一条消息。"""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1)


@app.get("/api/llm/config")
async def get_local_llm_config(request: Request):
    """读取本机大模型脱敏配置（仅本机可用）。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="llm config is local only")
    return public_llm_config(STORE_ROOT)


@app.post("/api/llm/config")
async def save_local_llm_config(req: LlmConfigSaveRequest, request: Request):
    """保存本机大模型配置（仅本机可用）。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="llm config is local only")
    try:
        return save_llm_config(
            STORE_ROOT,
            provider=req.provider,
            base_url=req.base_url,
            model=req.model,
            reasoning_effort=req.reasoning_effort,
            api_key=req.api_key,
            clear_api_key=req.clear_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/project/{project_id}/chat")
async def get_project_chat_endpoint(project_id: str, request: Request):
    """读取项目对话记录、本机模型配置状态与当前阶段快照（仅本机可用）。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="project chat is local only")
    _load_project(project_id)
    try:
        return get_project_chat_state(
            project_id,
            workspace_root=WORKSPACE_ROOT,
            store_root=STORE_ROOT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/project/{project_id}/chat")
async def send_project_chat_endpoint(
    project_id: str,
    req: ProjectChatMessageRequest,
    request: Request,
):
    """向项目 AI 助手发送一条消息并执行工具调用（仅本机可用）。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="project chat is local only")
    _load_project(project_id)
    try:
        return await asyncio.to_thread(
            send_project_chat_message,
            project_id,
            req.message,
            workspace_root=WORKSPACE_ROOT,
            store_root=STORE_ROOT,
        )
    except WebChatError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/project/{project_id}/chat")
async def clear_project_chat_endpoint(project_id: str, request: Request):
    """清空当前项目的对话历史（仅本机可用）。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="project chat is local only")
    _load_project(project_id)
    clear_chat_history(STORE_ROOT, project_id)
    return {"cleared": True}


if __name__ == "__main__":
    main()


