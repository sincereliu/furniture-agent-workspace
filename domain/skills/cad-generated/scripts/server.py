"""Furniture Agent 服务 — FastAPI 入口

启动: ./.venv/Scripts/python.exe domain/skills/cad-generated/scripts/server.py
打开: http://localhost:8000/docs 查看 Swagger API 文档
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_ROOT = WORKSPACE_ROOT / "generated"
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from furniture_layout.pipeline import generate_room_cad, plan_room_scene
from furniture_layout.validation import validate_room_scene

API_VERSION = "0.7.0"

app = FastAPI(
    title="Furniture Agent — 房间场景布局",
    version=API_VERSION,
    description=(
        "独立房间场景 API：多件包络摆放、碰撞检查、SVG 预览、互动 Viewer 与房间 CAD。"
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
    artifact_id: str | None = None


class RoomSceneResponse(BaseModel):
    room: dict[str, Any]
    items: list[dict[str, Any]]
    preview: dict[str, Any] | None = None
    viewer: dict[str, Any] | None = None
    cad: dict[str, Any] | None = None


@app.get("/health")
async def health():
    return {"status": "ok", "version": API_VERSION}


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html><body style="font-family:sans-serif;padding:40px;">
    <h1>Furniture Agent API</h1>
    <p><a href="/docs">API 文档 (Swagger)</a></p>
    </body></html>
    """


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
async def plan_room_cad(req: RoomSceneRequest):
    payload = req.model_copy(update={"generate_cad": True})
    return RoomSceneResponse(**_plan_scene(payload))


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
