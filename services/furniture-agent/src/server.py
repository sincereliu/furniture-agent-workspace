"""Furniture Agent 服务 — FastAPI 入口

启动: uvicorn services.furniture-agent.src.server:app --reload
打开: http://localhost:8000/docs 查看 Swagger API 文档
"""

from __future__ import annotations

import sys
from pathlib import Path

# 将 packages 目录加入 sys.path，确保能导入 workspace 内所有包
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_ROOT = WORKSPACE_ROOT / "packages"
OUTPUT_ROOT = WORKSPACE_ROOT / "generated"
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(PACKAGES_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from furniture.layout_pipeline import plan_cabinet
from furniture.design_spec import FurnitureSpec

app = FastAPI(
    title="Furniture Agent — 板式家具拆单服务",
    version="0.1.0",
    description="板式家具参数化拆单 API：落地柜/吊柜 规划、拆单、BOM 生成",
)

# 静态文件服务 — 挂载 generated 目录，供访问 STEP/GLB 文件
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(OUTPUT_ROOT)), name="generated")


# ── 请求/响应模型 ──
class CabinetRequest(BaseModel):
    type: str = Field(default="floor_cabinet", description="家具类型: floor_cabinet / wall_cabinet")
    width: float = Field(..., gt=0, description="总宽 mm (X)")
    depth: float = Field(..., gt=0, description="总深 mm (Y)")
    height: float = Field(..., gt=0, description="总高 mm (Z)")
    board_thickness: float = Field(default=18.0, gt=0, description="柜体板厚 mm")
    back_thickness: float = Field(default=9.0, gt=0, description="背板厚 mm")
    door_thickness: float = Field(default=18.0, gt=0, description="门板厚 mm")
    toe_kick_height: float = Field(default=50.0, ge=0, description="踢脚线高 mm")
    shelf_count: int = Field(default=4, ge=0, description="层板数量")
    n_doors: int = Field(default=2, ge=0, description="门板数量")


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
    try:
        spec = FurnitureSpec(
            furniture_type=req.type,
            width=req.width,
            height=req.height,
            depth=req.depth,
            board_thickness=req.board_thickness,
            back_thickness=req.back_thickness,
            door_thickness=req.door_thickness,
            toe_kick_height=req.toe_kick_height,
            shelf_count=req.shelf_count,
            n_doors=req.n_doors,
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        report = plan_cabinet(spec).bom
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()