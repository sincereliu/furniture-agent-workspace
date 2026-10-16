"""一台柜子的板件页：有已确认冻结板件就画结构，没有就只画已保存的外形。

不读未保存的输入，不确认布局，不调用板件生成。结构取自冻结文件，
本模块只把它投影成能画的东西——不写任何状态。
"""

from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from .assembly_tree import flatten_panels_for_handoff

#: 板件角色 → 页面上的**材质**。整台柜子只有两种材料：柜体一种木纹，门板白色纯色。
#: 角色仍然逐块带在数据里、列在清单里，只是不再各画一个颜色。
MATERIAL_WOOD = "wood"
MATERIAL_WHITE = "white"

MATERIALS: tuple[tuple[str, str], ...] = (
    (MATERIAL_WOOD, "柜体木纹"),
    (MATERIAL_WHITE, "门板白色"),
)

#: 白门的角色：门板与抽屉前脸。其余一律按柜体木纹画。
#: 判据用**角色**而不是分组，所以「归哪种材料」只有这一处定义。
_WHITE_ROLES = frozenset({"door", "drawer_front"})
_WHITE_TYPES = frozenset({"door", "drawer_front"})

_ASSEMBLY_KINDS = (
    ("carcass", "柜体"),
    ("base", "底座"),
    ("fronts", "门板"),
    ("drawers", "抽屉盒"),
)


def panel_material(panel: Mapping[str, Any]) -> str:
    """这块板用哪种材料画。先认角色，再认类型，默认柜体木纹。"""
    if str(panel.get("role") or "") in _WHITE_ROLES:
        return MATERIAL_WHITE
    if str(panel.get("panel_type") or "") in _WHITE_TYPES:
        return MATERIAL_WHITE
    return MATERIAL_WOOD


def panel_structure_view(cabinet: Mapping[str, Any]) -> dict[str, Any]:
    """一台柜子冻结结构 → 页面能画的对象（尺寸、位置、分组、装配）。

    尺寸与位置就是冻结文件里的数，不在这里再算一遍几何。没有 `assemblies`
    的旧结构视为空，不猜。
    """
    if not isinstance(cabinet, Mapping):
        raise ValueError("cabinet structure must be an object")
    cabinet_id = str(cabinet.get("id") or "").strip()
    if not cabinet_id:
        raise ValueError("cabinet structure requires id")
    spec = cabinet.get("spec")
    if not isinstance(spec, Mapping):
        raise ValueError(f"{cabinet_id} requires spec")
    interior = cabinet.get("interior")
    cavity = interior.get("cavity") if isinstance(interior, Mapping) else None
    assemblies = cabinet.get("assemblies")
    if not isinstance(assemblies, Mapping):
        raise ValueError(f"{cabinet_id} requires assemblies")

    kinds = _assembly_kinds(assemblies)
    panels = [_panel_view(item, kinds) for item in flatten_panels_for_handoff(cabinet)]
    shelves = spec.get("shelves") or []
    return {
        "cabinet_id": cabinet_id,
        "envelope_mm": {
            "width": _number(spec.get("width")),
            "depth": _number(spec.get("depth")),
            "height": _number(spec.get("height")),
        },
        "cavity_mm": {
            "width": _number(cavity.get("width")) if isinstance(cavity, Mapping) else None,
            "depth": _number(cavity.get("depth")) if isinstance(cavity, Mapping) else None,
            "height": _number(cavity.get("height")) if isinstance(cavity, Mapping) else None,
        },
        "thickness_mm": {
            "board": _number(spec.get("board_thickness")),
            "back": _number(spec.get("back_thickness")),
            "door": _number(spec.get("door_thickness")),
        },
        "back_mount": _back_mount(cabinet, spec),
        "n_doors": _count(spec.get("n_doors")),
        "drawer_count": _count(spec.get("drawer_count")),
        "shelf_count": len(shelves) if isinstance(shelves, Sequence) else 0,
        "toe_kick_height_mm": _number(spec.get("toe_kick_height")),
        "panels": panels,
        "materials": _materials(panels),
        "assemblies": [
            {"kind": kind, "label": label}
            for kind, label in _ASSEMBLY_KINDS
            if any(panel["assembly"] == kind for panel in panels)
        ],
    }


def _panel_view(panel: Mapping[str, Any], kinds: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(panel, Mapping):
        raise ValueError("each panel must be an object")
    panel_id = str(panel.get("id") or "").strip()
    if not panel_id:
        raise ValueError("each panel requires id")
    assembly_id = str(panel.get("assembly_id") or "")
    assembly = kinds.get(assembly_id)
    if assembly is None:
        assembly = "drawers" if str(panel.get("panel_type", "")).startswith("drawer") else "carcass"
    return {
        "id": panel_id,
        "name": str(panel.get("name") or panel_id),
        "role": str(panel.get("role") or ""),
        "panel_type": str(panel.get("panel_type") or ""),
        "assembly": assembly,
        "material": panel_material(panel),
        "material_role": str(panel.get("material_role") or ""),
        "size_mm": [
            _number(panel.get("size_x")),
            _number(panel.get("size_y")),
            _number(panel.get("size_z")),
        ],
        "pos_mm": [
            _number(panel.get("pos_x")),
            _number(panel.get("pos_y")),
            _number(panel.get("pos_z")),
        ],
        "inner_face": str(panel.get("inner_face") or ""),
        "outer_face": str(panel.get("outer_face") or ""),
        "depends_on": [str(item) for item in panel.get("depends_on") or []],
        "contact_count": len(panel.get("joints") or []),
    }


def _assembly_kinds(assemblies: Mapping[str, Any]) -> dict[str, str]:
    """装配 id → 种类。抽屉的盒体板件挂在抽屉自己的 id 上。"""
    kinds: dict[str, str] = {}
    for kind, label in _ASSEMBLY_KINDS:
        unit = assemblies.get(kind)
        if kind == "drawers":
            if not isinstance(unit, list):
                continue
            for drawer in unit:
                if isinstance(drawer, Mapping) and drawer.get("id"):
                    kinds[str(drawer["id"])] = kind
            continue
        if isinstance(unit, Mapping) and unit.get("id"):
            kinds[str(unit["id"])] = kind
    return kinds


def _materials(panels: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """图例：用到的材料、名字、块数。没用到的材料不出现。"""
    counted: dict[str, int] = {}
    for panel in panels:
        material = str(panel["material"])
        counted[material] = counted.get(material, 0) + 1
    return [
        {"material": material, "label": label, "count": counted[material]}
        for material, label in MATERIALS
        if counted.get(material)
    ]


def _back_mount(cabinet: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, str]:
    resolution = cabinet.get("back_mount_resolution")
    if not isinstance(resolution, Mapping):
        resolution = {}
    effective = str(resolution.get("effective") or spec.get("back_mount") or "")
    requested = str(resolution.get("requested") or effective)
    return {"requested": requested, "effective": effective}


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"panel structure requires a number, got {value!r}")
    return float(value)


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _json_for_script(payload: object) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _mm(value: float) -> str:
    number = float(value)
    rounded = round(number)
    if abs(number - rounded) < 1e-6:
        return str(int(rounded))
    return f"{number:.1f}"


_PAGE_STYLE = """
:root{
  --ink:#0f172a;--muted:#64748b;--line:#dbe2ec;--accent:#4f46e5;--canvas:#eef1f6;
  font-family:Inter,"Microsoft YaHei",system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--ink);
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{background:linear-gradient(180deg,#f7f9fc 0,#eef1f6 100%);padding:14px;display:flex;justify-content:center}
.app{width:min(1600px,100%);height:100%;display:grid;grid-template-rows:auto minmax(0,1fr);gap:12px}
.topbar{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
h1{margin:0;font-size:20px;font-weight:700}
.badge{margin:6px 0 0;display:inline-block;font-size:11.5px;font-weight:600;color:#475569;background:#f1f5f9;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
.toolbar{display:flex;gap:8px;align-items:center}
.toolbar a,.toolbar button{appearance:none;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:8px;padding:7px 12px;font:inherit;font-size:12.5px;font-weight:700;text-decoration:none;cursor:pointer}
.toolbar a:hover,.toolbar button:hover{border-color:#94a3b8}
#shutdown-preview{color:#b91c1c}
.workspace{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:12px}
.stage{position:relative;min-height:420px;background:var(--canvas);border:1px solid var(--line);border-radius:16px;overflow:hidden}
canvas{width:100%;height:100%;display:block;touch-action:none}
.overlay{position:absolute;z-index:3;display:flex;gap:8px;flex-wrap:wrap}
.tools{left:12px;top:12px;flex-direction:column;max-width:calc(100% - 24px)}
.panelbox{background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:11px;padding:7px;display:flex;gap:6px;flex-wrap:wrap;box-shadow:0 6px 18px rgba(15,23,42,.08)}
.panelbox .title{font-size:11px;font-weight:700;color:var(--muted);align-self:center;padding:0 4px}
.chip{appearance:none;border:1px solid var(--line);background:#fff;color:#334155;border-radius:8px;padding:5px 10px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
.chip:hover{border-color:#2563eb;color:#1d4ed8}
.chip[aria-pressed="true"]{background:#2563eb;border-color:#2563eb;color:#fff}
.slider{display:flex;align-items:center;gap:8px;font-size:12px;color:#334155;padding:2px 6px}
.slider input{width:120px}
.hint{left:12px;bottom:12px;background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:10px;padding:7px 11px;font-size:11.5px;color:#475569;max-width:60%}
.hint b{color:var(--ink)}
.legend{right:12px;bottom:12px;background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:10px;padding:8px 11px;font-size:11.5px;color:#475569;max-width:40%}
.legend ul{list-style:none;margin:0;padding:0;display:grid;gap:3px}
.legend li{display:flex;align-items:center;gap:6px}
.swatch{width:11px;height:11px;border-radius:3px;border:1px solid rgba(15,23,42,.25);flex:none}
.swatch.wood{background:repeating-linear-gradient(115deg,#c79a63 0 2px,#b98b52 2px 4px,#c99f6c 4px 7px)}
.swatch.white{background:linear-gradient(150deg,#ffffff,#e8eaee)}
#hover{position:absolute;pointer-events:none;z-index:4;background:#0f172a;color:#fff;font-size:11px;padding:4px 8px;border-radius:6px;display:none;white-space:nowrap;transform:translate(10px,10px)}
aside{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px;overflow-y:auto;min-height:0}
aside h2{font-size:12.5px;margin:16px 0 8px;color:#334155}
aside h2:first-child{margin-top:0}
dl.kv{margin:0;display:grid;grid-template-columns:auto 1fr;gap:7px 12px;font-size:12.5px;font-variant-numeric:tabular-nums}
dl.kv dt{color:var(--muted)}
dl.kv dd{margin:0;font-weight:600}
.filters{display:flex;flex-wrap:wrap;gap:6px}
.filters label{display:flex;align-items:center;gap:5px;font-size:12px;border:1px solid var(--line);border-radius:999px;padding:3px 9px;cursor:pointer}
.filters input{margin:0}
table.list{width:100%;border-collapse:collapse;font-size:12px}
table.list th{position:sticky;top:0;background:#fff;text-align:left;color:var(--muted);font-weight:600;padding:6px 5px;border-bottom:1px solid var(--line);z-index:1}
table.list td{padding:5px;border-bottom:1px solid #eef2f7;vertical-align:top}
table.list tbody tr{cursor:pointer}
table.list tbody tr:hover td{background:#f8fafc}
table.list tbody tr[aria-selected="true"] td{background:#eef2ff}
.dot{width:9px;height:9px;border-radius:2px;border:1px solid rgba(15,23,42,.2);flex:none;display:inline-block;margin-right:6px}
.dot.wood{background:repeating-linear-gradient(115deg,#c79a63 0 2px,#b98b52 2px 4px,#c99f6c 4px 7px)}
.dot.white{background:linear-gradient(150deg,#ffffff,#e8eaee)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.role{color:var(--muted);font-size:11px}
p{margin:12px 0 0;font-size:12.5px;line-height:1.6;color:var(--muted)}
.empty{border-left:3px solid #f59e0b;background:#fffbeb;border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.7;color:#78350f}
#detail{border:1px solid var(--line);border-radius:11px;padding:10px 12px;margin-top:10px;background:#f8fafc}
#detail strong{display:block;font-size:13px;margin-bottom:6px}
@media (max-width:1000px){.workspace{grid-template-columns:minmax(0,1fr)}}
"""


def _render_structure_page(
    *,
    project_id: str,
    label: str,
    structure: Mapping[str, Any],
    share: bool,
    back_href: str,
    shutdown: str,
    badge: str,
) -> str:
    title = escape(f"{label} · 柜体结构")
    payload = _json_for_script(structure)
    legend = "".join(
        f'<li><span class="swatch {escape(str(item["material"]), quote=True)}"></span>'
        f'{escape(str(item["label"]))} <span class="num">×{int(item["count"])}</span></li>'
        for item in structure["materials"]
    )
    filters = "".join(
        f'<label><input type="checkbox" data-assembly="{escape(str(item["kind"]), quote=True)}" checked>'
        f'{escape(str(item["label"]))}</label>'
        for item in structure["assemblies"]
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'">
<title>{title}</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<main class="app" aria-label="{title}">
  <header class="topbar">
    <div>
      <h1>{title}</h1>
      <p class="badge">{escape(badge)}</p>
    </div>
    <nav class="toolbar">
      <a href="{escape(back_href, quote=True)}">回布局</a>
      {shutdown}
    </nav>
  </header>
  <div class="workspace">
    <section class="stage">
      <canvas id="scene" aria-label="这台柜子已确认的板件结构。拖动转动，滚轮缩放，点板件看尺寸。"></canvas>
      <div class="overlay tools">
        <div class="panelbox">
          <span class="title">视角</span>
          <button type="button" class="chip" data-view="iso" aria-pressed="true">等轴</button>
          <button type="button" class="chip" data-view="front" aria-pressed="false">正面（门）</button>
          <button type="button" class="chip" data-view="back" aria-pressed="false">背面</button>
          <button type="button" class="chip" data-view="left" aria-pressed="false">左侧</button>
          <button type="button" class="chip" data-view="right" aria-pressed="false">右侧</button>
          <button type="button" class="chip" data-view="top" aria-pressed="false">顶视</button>
        </div>
        <div class="panelbox">
          <span class="title">显示</span>
          <button type="button" class="chip" id="toggle-doors" aria-pressed="true">门板/抽屉面</button>
          <button type="button" class="chip" id="toggle-back" aria-pressed="true">背板</button>
          <button type="button" class="chip" id="toggle-wire" aria-pressed="false">透视门板</button>
          <span class="slider">拆开 <input type="range" id="explode" min="0" max="100" value="0" step="1"></span>
        </div>
      </div>
      <div class="overlay hint"><b>拖动</b>转动 · <b>滚轮</b>缩放 · <b>点板件</b>看尺寸，鼠标扫过会变色。柜体一种木纹，门板白色，这里读的是已确认冻结的板件。</div>
      <div class="overlay legend"><ul>{legend}</ul></div>
      <div id="hover"></div>
    </section>
    <aside>
      <h2>外形与构造</h2>
      <dl class="kv" id="summary"></dl>
      <h2>按装配筛选</h2>
      <div class="filters">{filters}</div>
      <h2>板件（<span id="panel-count">0</span>）</h2>
      <table class="list">
        <thead><tr><th>板件</th><th class="num">尺寸 mm</th><th class="num">位置 mm</th></tr></thead>
        <tbody id="panel-rows"></tbody>
      </table>
      <div id="detail" hidden></div>
      <p>位置是板件原点（左后下角）在柜体坐标里的毫米数。颜色按角色分组，只用于看清结构。</p>
    </aside>
  </div>
</main>
<script id="cabinet-structure" type="application/json">{payload}</script>
<script type="importmap">
{{"imports":{{"three":"/vendor/three/0.186.0/three.module.js"}}}}
</script>
<script type="module">
import {{ mountCabinetStructure }} from "/layout-view/cabinet_structure.js";
mountCabinetStructure({{
  canvas: document.getElementById("scene"),
  payload: JSON.parse(document.getElementById("cabinet-structure").textContent),
  hover: document.getElementById("hover"),
  summary: document.getElementById("summary"),
  count: document.getElementById("panel-count"),
  rows: document.getElementById("panel-rows"),
  detail: document.getElementById("detail"),
  filters: document.querySelectorAll("[data-assembly]"),
  viewButtons: document.querySelectorAll("[data-view]"),
  toggles: {{
    doors: document.getElementById("toggle-doors"),
    back: document.getElementById("toggle-back"),
    wire: document.getElementById("toggle-wire"),
    explode: document.getElementById("explode"),
  }},
}});
function pulse(){{
  fetch("/api/preview/presence", {{method:"POST", cache:"no-store", keepalive:true}}).catch(()=>{{}});
}}
pulse();
setInterval(pulse, 1000);
const shutdownButton = document.getElementById("shutdown-preview");
if (shutdownButton) {{
  shutdownButton.addEventListener("click", async () => {{
    shutdownButton.disabled = true;
    try {{ await fetch("/api/preview/shutdown", {{method:"POST", cache:"no-store"}}); }} catch (error) {{}}
  }});
}}
</script>
</body>
</html>
"""


def _render_envelope_page(
    *,
    cabinet: Mapping[str, Any],
    stage_note: str = "",
    share: bool,
    back_href: str,
    shutdown: str,
) -> str:
    """还没有已确认板件：只画布局里已经保存的外形。"""
    label = str(cabinet.get("label") or cabinet["id"])
    width = _mm(float(cabinet["width"]))
    depth = _mm(float(cabinet["depth"]))
    height = _mm(float(cabinet["height"]))
    geometry = _json_for_script(
        {
            "width": float(cabinet["width"]),
            "depth": float(cabinet["depth"]),
            "height": float(cabinet["height"]),
        }
    )
    note = (
        stage_note
        or "这台柜子的板件还没确认：页上只有布局里已经保存的外形。"
        "板件阶段确认后，这里会换成能转、能拆开看的结构。"
    )
    badge = "只读分享 · 链接可转发" if share else "这一台的外形 · 尺寸在布局里改"
    title = escape(f"{label} · 板件")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'">
<title>{title}</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<main class="app" aria-label="{title}">
  <header class="topbar">
    <div>
      <h1>{title}</h1>
      <p class="badge">{escape(badge)}</p>
    </div>
    <nav class="toolbar">
      <a href="{escape(back_href, quote=True)}">回布局</a>
      {shutdown}
    </nav>
  </header>
  <div class="workspace">
    <section class="stage">
      <canvas id="scene" aria-label="这一台柜子的外形。绿面是正面。拖动可转动。"></canvas>
    </section>
    <aside>
      <h2>外形</h2>
      <dl class="kv">
        <dt>宽</dt><dd>{width} mm</dd>
        <dt>深</dt><dd>{depth} mm</dd>
        <dt>高</dt><dd>{height} mm</dd>
      </dl>
      <p class="empty">{escape(note)}</p>
      <p>这三个数是布局里已经保存的外形。要改，回布局页改完再进来。</p>
      <p>绿面是柜门这一面。</p>
    </aside>
  </div>
</main>
<script id="cabinet" type="application/json">{geometry}</script>
<script type="importmap">
{{"imports":{{"three":"/vendor/three/0.186.0/three.module.js"}}}}
</script>
<script type="module">
import * as THREE from "three";
import {{ OrbitControls }} from "/vendor/three/0.186.0/OrbitControls.js";
const cabinet = JSON.parse(document.getElementById("cabinet").textContent);
const canvas = document.getElementById("scene");
const renderer = new THREE.WebGLRenderer({{canvas, antialias:true}});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xeef1f6);
const camera = new THREE.PerspectiveCamera(40, 1, 1, 100000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
const width = cabinet.width, depth = cabinet.depth, height = cabinet.height;
const body = new THREE.Mesh(
  new THREE.BoxGeometry(width, height, depth),
  new THREE.MeshStandardMaterial({{color:0x8ea9e8, roughness:0.72}})
);
body.position.y = height / 2;
scene.add(body);
const front = new THREE.Mesh(
  new THREE.PlaneGeometry(width, height),
  new THREE.MeshBasicMaterial({{color:0x047857, transparent:true, opacity:0.45, side:THREE.DoubleSide}})
);
front.position.set(0, height / 2, depth / 2 + 1);
scene.add(front);
scene.add(new THREE.AmbientLight(0xffffff, 0.75));
const sun = new THREE.DirectionalLight(0xffffff, 1.1);
sun.position.set(width, height * 2, depth * 2);
scene.add(sun);
const radius = Math.hypot(width, height, depth);
camera.position.set(width * 0.35, height * 0.72, radius * 0.95);
controls.target.set(0, height * 0.45, 0);
controls.update();
function frame(){{
  const w = canvas.clientWidth || 960;
  const h = canvas.clientHeight || 640;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
}}
function draw(){{
  frame();
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(draw);
}}
draw();
function pulse(){{
  fetch("/api/preview/presence", {{method:"POST", cache:"no-store", keepalive:true}}).catch(()=>{{}});
}}
pulse();
setInterval(pulse, 1000);
const shutdownButton = document.getElementById("shutdown-preview");
if (shutdownButton) {{
  shutdownButton.addEventListener("click", async () => {{
    shutdownButton.disabled = true;
    try {{ await fetch("/api/preview/shutdown", {{method:"POST", cache:"no-store"}}); }} catch (error) {{}}
  }});
}}
</script>
</body>
</html>
"""


def render_cabinet_panel_page(
    project_id: str,
    cabinet: Mapping[str, Any],
    *,
    share: bool = False,
    structure: Mapping[str, Any] | None = None,
    stage_note: str = "",
) -> str:
    """这一台的板件页。

    `structure` 是已确认冻结板件的投影（`panel_structure_view()` 的结果）。给了就画结构，
    没给只画外形——**页面不自己去读冻结文件，也不替板件阶段生成**。`stage_note` 说明
    为什么没有结构（未确认 / 冻结文件缺了 / 冻结文件里没有这台柜）。
    """
    back_query = {"room": cabinet["room_id"], "item": cabinet["id"]}
    if share:
        back_query["mode"] = "view"
    back_href = (
        f"/api/project/{escape(project_id, quote=True)}/preview?"
        f"{urlencode(back_query)}"
    )
    shutdown = "" if share else '<button type="button" id="shutdown-preview">退出</button>'
    label = str(cabinet.get("label") or cabinet["id"])
    if structure is None:
        return _render_envelope_page(
            cabinet=cabinet,
            stage_note=stage_note,
            share=share,
            back_href=back_href,
            shutdown=shutdown,
        )
    badge = (
        "只读分享 · 链接可转发"
        if share
        else "已确认冻结板件 · 点板件看尺寸，透视看内部"
    )
    return _render_structure_page(
        project_id=project_id,
        label=label,
        structure=structure,
        share=share,
        back_href=back_href,
        shutdown=shutdown,
        badge=badge,
    )
