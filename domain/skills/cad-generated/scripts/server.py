"""Furniture Agent 服务 — FastAPI 入口

启动: ./.venv/Scripts/python.exe domain/skills/cad-generated/scripts/server.py
打开: http://localhost:8000/docs 查看 Swagger API 文档
"""

from __future__ import annotations

import asyncio
import re
import sys
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
    LayoutEditDisabled,
    VersionConflict,
    edit_project_layout,
)
from furniture_workflow.project_preview import project_layout_document
from furniture_workflow.workflow_store import JsonProjectStore

API_VERSION = "0.8.0"
SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_LOCAL_HOSTS = {"127.0.0.1", "::1"}
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


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html><body style="font-family:sans-serif;padding:40px;">
    <h1>Furniture Agent API</h1>
    <p><a href="/docs">API 文档 (Swagger)</a></p>
    </body></html>
    """


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
    document = project_layout_document(_load_project(project_id))
    if not document["rooms"]:
        raise HTTPException(status_code=422, detail="project layout has no rooms")
    return document


@app.get("/api/project/{project_id}/layout")
async def project_layout(project_id: str):
    """最新布局：房间和已摆放的包络。不含预览 HTML。"""
    return _project_layout_document(project_id)


@app.get("/api/project/{project_id}/preview", response_class=HTMLResponse)
async def project_preview(project_id: str, mode: str | None = None) -> HTMLResponse:
    """只读布局页。打开后每秒再读 layout，版本变了就换包络并保持相机。

    `?mode=view` 出分享形态（换牌子、去掉「退出」）。**它只是表达，不是权限**：
    参数谁都能改，写权限由 `may_edit()` 判定。
    """
    document = _project_layout_document(project_id)
    try:
        html = render_project_preview(project_id, document, mode=mode)
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
        )
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


def main() -> None:
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    app.state.preview_server = server
    server.run()


if __name__ == "__main__":
    main()
