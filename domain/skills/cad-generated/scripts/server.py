"""Furniture Agent 服务 — FastAPI 入口

启动: ./.venv/Scripts/python.exe domain/skills/cad-generated/scripts/server.py
打开: http://127.0.0.1:8000/projects 查看已经做过的项目
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import threading
import time
import webbrowser
from html import escape
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_ROOT = WORKSPACE_ROOT / "generated"
STORE_ROOT = WORKSPACE_ROOT / "store"
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from furniture_layout.editor import render_editor, render_project_preview
from furniture_layout.pipeline import generate_room_cad, plan_room_scene
from furniture_layout.scene import RoomScene
from furniture_layout.scene_edit import apply_edit
from furniture_layout.scene_store import (
    list_scene_ids,
    load_scene_source,
    save_scene_source,
)
from furniture_layout.validation import validate_room_scene
from furniture_workflow.project_layout_edit import (
    LAYOUT_EDIT_ENV,
    LayoutEditDisabled,
    VersionConflict,
    edit_project_layout,
    undo_layout_edit,
)
from furniture_workflow.project_preview import (
    preview_server_is_up,
    project_layout_document,
    project_list_url,
)
from furniture_workflow.workflow_lease import (
    LeaseHeld,
    LeaseLost,
    acquire,
    release,
    transfer,
)
from furniture_workflow.workflow_store import JsonProjectStore

API_VERSION = "0.8.0"
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
app.mount("/layout-view", StaticFiles(directory=str(LAYOUT_PAGE)), name="layout_view")


class RoomOpeningRequest(BaseModel):
    id: str = Field(default="", description="门窗标识")
    kind: str = Field(default="opening", description="opening / door / window")
    wall: Literal["south", "east", "north", "west"]
    offset_mm: float = Field(default=0, ge=0, description="沿墙顺时针起点的偏移")
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    sill_height_mm: float = Field(default=0, ge=0)


class RoomObstacleRequest(BaseModel):
    id: str = Field(default="", description="障碍物标识")
    kind: str = Field(default="obstacle", description="column / pipe / obstacle")
    x_mm: float = Field(default=0, ge=0)
    y_mm: float = Field(default=0, ge=0)
    z_mm: float = Field(default=0, ge=0)
    width_mm: float = Field(..., gt=0)
    depth_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)


class RoomRequest(BaseModel):
    id: str = Field(default="room")
    name: str = Field(default="房间")
    width_mm: float = Field(..., gt=0)
    depth_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    openings: list[RoomOpeningRequest] = Field(default_factory=list)
    obstacles: list[RoomObstacleRequest] = Field(default_factory=list)


class ItemPlacementRequest(BaseModel):
    mode: Literal["wall", "free"] = Field(default="wall")
    host_wall: Literal["south", "east", "north", "west"] | None = None
    offset_mm: float | None = Field(default=None, ge=0)
    origin_x_mm: float | None = None
    origin_y_mm: float | None = None
    origin_z_mm: float = Field(default=0, ge=0)
    rotation_z_deg: float | None = None
    fill: bool = False


class SceneItemRequest(BaseModel):
    id: str = Field(default="")
    label: str = Field(default="")
    category: str
    width: float = Field(..., gt=0)
    depth: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    placement: ItemPlacementRequest


class RoomSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room: RoomRequest
    items: list[SceneItemRequest] = Field(..., min_length=1)
    generate_cad: bool = False
    artifact_id: str | None = Field(
        default=None,
        description=(
            "房间 CAD 产物标识；显式提供时仅允许英文字母、数字、'-' 和 '_'"
        ),
    )


class RoomSceneResponse(BaseModel):
    room: dict[str, Any]
    items: list[dict[str, Any]]
    preview: dict[str, Any] | None = None
    viewer: dict[str, Any] | None = None
    cad: dict[str, Any] | None = None


class RoomSceneSaveRequest(BaseModel):
    """保存场景的「源」：房间定义 + 多件包络及其摆放请求。"""

    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(default="", description="场景 id；留空则自动生成")
    room: RoomRequest
    items: list[SceneItemRequest] = Field(..., min_length=1)


class RoomSceneEditRequest(BaseModel):
    """单次编辑：move / rotate / resize 三者之一，只改目标 item。"""

    model_config = ConfigDict(extra="forbid")

    op: Literal["move", "rotate", "resize"]
    item_id: str = Field(..., min_length=1)
    # move：按当前 mode 二选一 —— wall 用 host_wall/offset_mm，free 用 origin_x_mm/origin_y_mm
    mode: Literal["wall", "free"] | None = None
    host_wall: Literal["south", "east", "north", "west"] | None = None
    offset_mm: float | None = Field(default=None, ge=0)
    origin_x_mm: float | None = None
    origin_y_mm: float | None = None
    origin_z_mm: float | None = Field(default=None, ge=0)
    # rotate
    rotation_z_deg: float | None = None
    # resize
    width: float | None = Field(default=None, gt=0)
    depth: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)


class ProjectLayoutEditRequest(RoomSceneEditRequest):
    """页面上改项目布局里的一件：与场景编辑同一套 op，外加并发版本。

    `expected_version` 必填：它是页面最近一次从 `/layout` 看到的 `version`。
    对不上就拒绝——页面上的画面已经过期，不能拿它去覆盖。
    """

    expected_version: str = Field(..., min_length=1, description="页面最近看到的 version")


class ProjectLayoutUndoRequest(BaseModel):
    """撤销工作副本上的最后 N 步（只在没有下游产物时可用）。"""

    model_config = ConfigDict(extra="forbid")

    expected_version: str = Field(..., min_length=1, description="页面最近看到的 version")
    steps: int = Field(default=1, ge=1, le=50)


@app.get("/health")
async def health():
    return {"status": "ok", "version": API_VERSION}


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


def _project_rows() -> list[dict[str, Any]]:
    return JsonProjectStore(STORE_ROOT).list_projects()


def _project_status(confirmed: bool) -> str:
    return "布局已确认" if confirmed else "还没确认"


def _project_date(created_at: str) -> str:
    if len(created_at) >= 10 and created_at[4] == "-" and created_at[7] == "-":
        return created_at[:10]
    return created_at


def _project_list_html(rows: list[dict[str, Any]]) -> str:
    if rows:
        items = []
        for row in rows:
            href = f"/api/project/{escape(row['id'], quote=True)}/preview"
            meta = (
                f"{_project_date(str(row['created_at']))} · "
                f"修订 {int(row['revision_number'])} · "
                f"{_project_status(bool(row['layout_confirmed']))}"
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
        "<p class=\"lead\">点一个项目打开那一版布局。关机后项目还在这一页。</p>"
        + body
        + "<p><a class=\"docs\" href=\"/docs\">API 文档</a></p>"
        "</main></body></html>"
    )


@app.get("/api/projects")
async def project_index_json():
    """Saved projects. Unreadable files are omitted."""
    return {"projects": _project_rows()}


@app.get("/projects", response_class=HTMLResponse)
async def project_index():
    """List of saved projects. Each row opens that project's layout page."""
    return HTMLResponse(content=_project_list_html(_project_rows()))


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
        return JsonProjectStore(STORE_ROOT).load(project_id)
    except ValueError as exc:
        message = str(exc)
        status = 404 if message.startswith("project not found") else 422
        raise HTTPException(status_code=status, detail=message) from exc


def _project_layout_document(project_id: str) -> dict[str, Any]:
    document = project_layout_document(_load_project(project_id), store_root=STORE_ROOT)
    if not document["rooms"]:
        raise HTTPException(status_code=422, detail="project layout has no rooms")
    return document


@app.get("/api/project/{project_id}/layout")
async def project_layout(project_id: str):
    """最新布局：房间和已摆放的包络。不含预览 HTML。"""
    return _project_layout_document(project_id)


@app.get("/api/project/{project_id}/preview", response_class=HTMLResponse)
async def project_preview(project_id: str, request: Request, mode: str | None = None) -> HTMLResponse:
    """布局页。打开后每秒再读 layout，版本变了就换包络并保持相机。

    **能不能编辑由服务端按权限渲染**：本机来源（`may_edit`）给可编辑页，其余给只读页。
    `?mode=view` 在此之上强制只读（分享形态：换牌子、去掉「退出」）——**URL 参数不是权限**：
    参数谁都能改，真正的门是 `may_edit()` 与编辑租约。
    """
    document = _project_layout_document(project_id)
    read_only = mode == "view" or not may_edit(request)
    try:
        html = render_project_preview(
            project_id,
            document,
            mode=mode,
            read_only=read_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HTMLResponse(content=html)


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


def _plan_scene(req: RoomSceneRequest) -> dict[str, Any]:
    payload = req.model_dump(exclude_none=True)
    try:
        output = plan_room_scene(payload["room"], payload["items"])
        report = validate_room_scene(output)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not report.passed:
        raise HTTPException(
            status_code=422,
            detail="; ".join(issue.message for issue in report.issues),
        )
    if req.generate_cad:
        try:
            output = generate_room_cad(
                output,
                workspace_root=WORKSPACE_ROOT,
                output_root=OUTPUT_ROOT,
                artifact_id=req.artifact_id,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return output


@app.post("/api/plan-room", response_model=RoomSceneResponse)
async def plan_room(req: RoomSceneRequest):
    """独立规划房间多件包络摆放；不进入家具生成的串联阶段。"""
    return RoomSceneResponse(**_plan_scene(req))


@app.post(
    "/api/plan-room/preview",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}},
)
async def plan_room_preview(req: RoomSceneRequest) -> Response:
    result = await plan_room(req)
    if result.preview is None:
        raise HTTPException(status_code=422, detail="layout preview was not generated")
    return Response(
        content=str(result.preview["svg"]),
        media_type="image/svg+xml",
    )


@app.post(
    "/api/plan-room/viewer",
    response_class=HTMLResponse,
    responses={200: {"content": {"text/html": {}}}},
)
async def plan_room_viewer(req: RoomSceneRequest) -> HTMLResponse:
    result = await plan_room(req)
    if result.viewer is None:
        raise HTTPException(
            status_code=422,
            detail="interactive layout viewer was not generated",
        )
    return HTMLResponse(content=str(result.viewer["html"]))


@app.post("/api/plan-room/cad", response_model=RoomSceneResponse)
async def plan_room_cad(req: RoomSceneRequest, request: Request):
    """出房间 CAD：会往磁盘写源文件与 STEP，所以和落盘一样要求本机来源。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="generating room CAD is local only")
    payload = req.model_copy(update={"generate_cad": True})
    return RoomSceneResponse(**_plan_scene(payload))


@app.post("/api/room-scene/save")
async def save_room_scene(req: RoomSceneSaveRequest, request: Request):
    """保存场景的源；派生结果（摆放/预览）不落盘，读取时重算。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="saving scenes is local only")
    scene_id = req.scene_id or f"scene-{uuid4().hex[:12]}"
    payload = req.model_dump(exclude_none=True)
    try:
        path = save_scene_source(
            scene_id,
            payload["room"],
            payload["items"],
            root=OUTPUT_ROOT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"scene_id": scene_id, "path": str(path)}


@app.get("/api/room-scene/{scene_id}", response_model=RoomSceneResponse)
async def load_room_scene(scene_id: str):
    """读取场景的源并重算摆放、预览与 Viewer。"""
    try:
        source = load_scene_source(scene_id, root=OUTPUT_ROOT)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RoomSceneResponse(**plan_room_scene(source["room"], source["items"]))


@app.get("/api/room-scenes")
async def list_room_scenes():
    return {"scene_ids": list_scene_ids(root=OUTPUT_ROOT)}


@app.post("/api/room-scene/{scene_id}/edit", response_model=RoomSceneResponse)
async def edit_room_scene(scene_id: str, req: RoomSceneEditRequest, request: Request):
    """应用一次编辑：重算并校验通过才落盘，失败即整体拒绝（不留半成品）。"""
    if not may_edit(request):
        raise HTTPException(status_code=403, detail="editing scenes is local only")
    try:
        source = load_scene_source(scene_id, root=OUTPUT_ROOT)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    op = req.model_dump(exclude_none=True)
    try:
        edited = apply_edit(source, op)
        scene = plan_room_scene(edited["room"], edited["items"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    report = validate_room_scene(scene)
    if not report.passed:
        raise HTTPException(
            status_code=422,
            detail="; ".join(issue.message for issue in report.issues),
        )

    save_scene_source(
        scene_id,
        edited["room"],
        edited["items"],
        root=OUTPUT_ROOT,
    )
    return RoomSceneResponse(**scene)


@app.get("/api/room-scene/{scene_id}/editor", response_class=HTMLResponse)
async def room_scene_editor(scene_id: str) -> HTMLResponse:
    """可编辑视图：点选家具拖动，松手发一个 edit op。"""
    try:
        source = load_scene_source(scene_id, root=OUTPUT_ROOT)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        planned = plan_room_scene(source["room"], source["items"])
        scene = RoomScene.from_dict(
            {"room": planned["room"], "items": planned["items"]}
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    editor = render_editor(scene_id, scene)
    return HTMLResponse(content=str(editor["html"]))


if __name__ == "__main__":
    main()
