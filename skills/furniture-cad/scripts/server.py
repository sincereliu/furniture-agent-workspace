"""Furniture Agent 服务 — FastAPI 入口

启动: ./.venv/Scripts/python.exe skills/furniture-cad/scripts/server.py
打开: http://localhost:8000/docs 查看 Swagger API 文档
"""

from __future__ import annotations

import sys
from pathlib import Path

# skill 自带运行包，服务入口与它位于同一个 scripts 目录。
SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = WORKSPACE_ROOT / "generated"
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator

app = FastAPI(
    title="Furniture Agent — 板式家具拆单服务",
    version="0.1.0",
    description="板式家具参数化拆单 API：落地柜/吊柜 规划、拆单、BOM 生成",
)
ORCHESTRATOR = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

# 静态文件服务 — 挂载 generated 目录，供访问 STEP/GLB 文件
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(OUTPUT_ROOT)), name="generated")


# ── 请求/响应模型 ──
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


class BOMResponse(BaseModel):
    furniture_name: str
    dimensions: str
    panel_count: int
    total_area_m2: float
    panels: list[PanelResponse]
    hardware: list[dict]


# ── 路由 ──
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


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

    return BOMResponse(
        furniture_name=report.furniture_name,
        dimensions=report.dimensions,
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
            )
            for p in report.panels
        ],
        hardware=[
            {"name": h.name, "spec": h.spec, "quantity": h.quantity, "unit": h.unit}
            for h in report.hardware
        ],
    )


# ── 启动入口 ──
def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
