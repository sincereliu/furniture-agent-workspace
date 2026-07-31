"""Furniture Agent 服务 — FastAPI 入口

启动: ./.venv/Scripts/python.exe skills/furniture-cad/scripts/server.py
打开: http://localhost:8000/docs 查看 Swagger API 文档
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

# skill 自带运行包，服务入口与它位于同一个 scripts 目录。
SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = WORKSPACE_ROOT / "generated"
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage

API_VERSION = "0.3.0"

app = FastAPI(
    title="Furniture Agent — 板式家具拆单服务",
    version=API_VERSION,
    description=(
        "板式家具参数化拆单 API：房间定位与 SVG 预览、"
        "落地柜/吊柜规划、三种背板安装、BOM、加工与孔位输出"
    ),
)
ORCHESTRATOR = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

# 静态文件服务 — 挂载 generated 目录，供访问 STEP/GLB 文件
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(OUTPUT_ROOT)), name="generated")


# ── 请求/响应模型 ──
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


class FurniturePlacementRequest(BaseModel):
    mode: Literal["wall", "free"] = Field(default="wall")
    host_wall: Literal["south", "east", "north", "west"] | None = None
    offset_mm: float | None = Field(default=None, ge=0)
    origin_x_mm: float | None = None
    origin_y_mm: float | None = None
    origin_z_mm: float = Field(default=0, ge=0)
    rotation_z_deg: float | None = None


class CabinetRequest(BaseModel):
    type: str = Field(default="floor_cabinet", description="家具类型: floor_cabinet / wall_cabinet")
    width: float = Field(..., gt=0, description="总宽 mm (X)")
    depth: float = Field(..., gt=0, description="总深 mm (Y)")
    height: float = Field(..., gt=0, description="总高 mm (Z)")
    board_thickness: float | None = Field(default=None, gt=0, description="柜体板厚 mm")
    back_thickness: float | None = Field(default=None, gt=0, description="背板厚 mm")
    door_thickness: float | None = Field(default=None, gt=0, description="门板厚 mm")
    toe_kick_height: float | None = Field(default=None, ge=0, description="踢脚线高 mm")
    back_offset: float | None = Field(default=None, ge=0, description="背板后移 mm")
    door_margin: float | None = Field(default=None, ge=0, description="门板四周间隙 mm")
    door_hinge_gap: float | None = Field(default=None, ge=0, description="门铰深度间隙 mm")
    shelf_count: int | None = Field(default=None, ge=0, description="层板数量")
    n_doors: int | None = Field(default=None, ge=0, description="门板数量")
    groove_depth: float | None = Field(default=None, gt=0, description="背板入槽深度 mm")
    groove_clearance: float | None = Field(default=None, ge=0, description="槽宽相对背板厚度的余量 mm")
    back_mount: Literal["auto", "groove", "insert", "cover"] | None = Field(
        default=None,
        description=(
            "背板安装方式；auto 按背板厚度解析为 groove 或 insert"
        ),
    )
    back_rail_height: float | None = Field(
        default=None,
        ge=0,
        description="入槽模式背拉条高度 mm；0 表示不生成背拉条",
    )
    toe_kick_reveal_front: float | None = Field(default=None, ge=0, description="前踢脚板后缩 mm")
    toe_kick_reveal_back: float | None = Field(default=None, ge=0, description="后踢脚板前移 mm")
    toe_kick_support_count: int | None = Field(default=None, ge=0, description="踢脚支撑板数量；空值为自动")
    room: RoomRequest | None = Field(
        default=None,
        description="第 2 阶段使用的房间模型",
    )
    placement: FurniturePlacementRequest | None = Field(
        default=None,
        description="家具在房间中的沿墙或自由摆放位置",
    )


class PanelResponse(BaseModel):
    label: str
    name: str
    panel_type: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    material: str
    thickness: float
    length_mm: float
    width_mm: float
    edge_banding: dict
    note: str
    back_mount: Literal["groove", "insert", "cover"]


class HardwareDrillingResponse(BaseModel):
    hole_type: str
    quantity: int


class HardwareResponse(BaseModel):
    name: str
    spec: str
    quantity: int
    unit: str
    brand: str
    model: str
    note: str
    drilling: list[HardwareDrillingResponse]


class MachiningOperationResponse(BaseModel):
    id: str
    operation_type: str
    target_panel: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    note: str


class HoleResponse(BaseModel):
    hole_type: str
    color: str
    x: float
    y: float
    z: float
    local_x: float
    local_y: float
    local_z: float
    diameter: float
    depth: float
    direction: str
    note: str


class PanelDrillingResponse(BaseModel):
    label: str
    name: str
    box: dict[str, float]
    holes: list[HoleResponse]


class BOMResponse(BaseModel):
    furniture_name: str
    dimensions: str
    readiness: Literal["preliminary", "accepted", "factory_ready"]
    back_mount: Literal["groove", "insert", "cover"]
    panel_count: int
    total_area_m2: float
    panels: list[PanelResponse]
    hardware: list[HardwareResponse]
    operations: list[MachiningOperationResponse]
    hole_color_legend: dict[str, dict[str, str]]
    drilled_holes: list[PanelDrillingResponse]


class LayoutPlanResponse(BaseModel):
    layout: dict[str, Any]
    room_placement: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None


# ── 路由 ──
@app.get("/health")
async def health():
    return {"status": "ok", "version": API_VERSION}


@app.get("/", response_class=HTMLResponse)
async def root():
    """API 入口页面"""
    return """
    <html><body style="font-family:sans-serif;padding:40px;">
    <h1>Furniture Agent API</h1>
    <p><a href="/docs">API 文档 (Swagger)</a></p>
    </body></html>
    """


@app.post("/api/plan-cabinet", response_model=BOMResponse)
async def plan_cabinet(req: CabinetRequest):
    """规划柜体、拆单、返回 BOM"""
    spec = req.model_dump(exclude_none=True)
    try:
        orchestration = ORCHESTRATOR.execute_spec(
            f"api-{req.type}",
            spec,
        )
    except (OSError, TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    if orchestration.pipeline is None:
        errors = [
            issue.message
            for validation in orchestration.revision.validations
            for issue in validation.issues
        ]
        raise HTTPException(
            status_code=400,
            detail="; ".join(errors) or "furniture orchestration failed",
        )

    report = orchestration.pipeline.bom
    drilled_holes = orchestration.drilled_holes or {
        "color_legend": {},
        "panels": [],
    }

    return BOMResponse(
        furniture_name=report.furniture_name,
        dimensions=report.dimensions,
        readiness=report.readiness,
        back_mount=orchestration.pipeline.layout.back_mount,
        panel_count=report.panel_count,
        total_area_m2=report.total_area_m2,
        panels=[
            PanelResponse(
                label=p.label,
                name=p.name,
                panel_type=p.panel_type,
                size_x=p.size_x,
                size_y=p.size_y,
                size_z=p.size_z,
                pos_x=p.pos_x,
                pos_y=p.pos_y,
                pos_z=p.pos_z,
                material=p.material,
                thickness=p.thickness,
                length_mm=p.length_mm,
                width_mm=p.width_mm,
                edge_banding=p.edge_banding,
                note=p.note,
                back_mount=p.back_mount,
            )
            for p in report.panels
        ],
        hardware=[
            HardwareResponse(
                name=h.name,
                spec=h.spec,
                quantity=h.quantity,
                unit=h.unit,
                brand=h.brand,
                model=h.model,
                note=h.note,
                drilling=h.drilling or [],
            )
            for h in report.hardware
        ],
        operations=[
            MachiningOperationResponse(
                id=operation.id,
                operation_type=operation.operation_type,
                target_panel=operation.target_panel,
                size_x=operation.size_x,
                size_y=operation.size_y,
                size_z=operation.size_z,
                pos_x=operation.pos_x,
                pos_y=operation.pos_y,
                pos_z=operation.pos_z,
                note=operation.note,
            )
            for operation in report.operations
        ],
        hole_color_legend=drilled_holes["color_legend"],
        drilled_holes=drilled_holes["panels"],
    )


@app.post("/api/plan-layout", response_model=LayoutPlanResponse)
async def plan_layout(req: CabinetRequest):
    """只运行到第 2 阶段，返回房间定位、占地和 SVG 预览。"""
    orchestration = ORCHESTRATOR.execute_spec(
        f"layout-{req.type}",
        req.model_dump(exclude_none=True),
        through_stage=WorkflowStage.LAYOUT_PLANNED,
    )
    output = orchestration.revision.stage_outputs.get(
        WorkflowStage.LAYOUT_PLANNED.value
    )
    if output is None or orchestration.revision.workflow.current == WorkflowStage.FAILED:
        errors = [
            issue.message
            for validation in orchestration.revision.validations
            for issue in validation.issues
        ]
        raise HTTPException(
            status_code=422,
            detail="; ".join(errors) or "layout planning failed",
        )
    return LayoutPlanResponse(**output)


@app.post(
    "/api/plan-layout/preview",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}},
)
async def plan_layout_preview(req: CabinetRequest) -> Response:
    """返回可直接在浏览器中显示的第 2 阶段 SVG 平面预览。"""
    result = await plan_layout(req)
    if result.preview is None:
        raise HTTPException(
            status_code=422,
            detail="room and placement are required for a layout preview",
        )
    return Response(
        content=str(result.preview["svg"]),
        media_type="image/svg+xml",
    )


# ── 启动入口 ──
def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
