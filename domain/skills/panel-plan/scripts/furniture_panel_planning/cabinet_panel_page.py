"""一台柜子的板件页：只画已保存的外形。

不读未保存的输入，不确认布局，不调用板件生成。门、层板仍由板件阶段在布局确认后写出。
"""

from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping
from urllib.parse import urlencode


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


def render_cabinet_panel_page(
    project_id: str,
    cabinet: Mapping[str, Any],
    *,
    share: bool = False,
) -> str:
    """这一台的板件页。外形三个数只显示。"""
    label = str(cabinet.get("label") or cabinet["id"])
    width = _mm(float(cabinet["width"]))
    depth = _mm(float(cabinet["depth"]))
    height = _mm(float(cabinet["height"]))
    back_query = {"room": cabinet["room_id"], "item": cabinet["id"]}
    if share:
        back_query["mode"] = "view"
    back_href = (
        f"/api/project/{escape(project_id, quote=True)}/preview?"
        f"{urlencode(back_query)}"
    )
    geometry = _json_for_script(
        {
            "width": float(cabinet["width"]),
            "depth": float(cabinet["depth"]),
            "height": float(cabinet["height"]),
        }
    )
    shutdown = "" if share else '<button type="button" id="shutdown-preview">退出</button>'
    badge = "只读分享 · 链接可转发" if share else "这一台的外形 · 尺寸在布局里改"
    title = escape(f"{label} · 板件")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'">
<title>{title}</title>
<style>
:root{{
  --ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#4f46e5;--canvas:#eef1f6;
  font-family:Inter,"Microsoft YaHei",system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--ink);
}}
*{{box-sizing:border-box}}
html,body{{height:100%;margin:0}}
body{{background:linear-gradient(180deg,#f7f9fc 0,#eef1f6 100%);padding:18px;display:flex;justify-content:center}}
.app{{width:min(1320px,100%);height:100%;display:grid;grid-template-rows:auto minmax(0,1fr);gap:14px}}
.topbar{{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}}
h1{{margin:0;font-size:21px;font-weight:700}}
.badge{{margin:7px 0 0;display:inline-block;font-size:11.5px;font-weight:600;color:#475569;background:#f1f5f9;border:1px solid var(--line);border-radius:999px;padding:3px 10px}}
.toolbar{{display:flex;gap:8px;align-items:center}}
.toolbar a,.toolbar button{{appearance:none;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:8px;padding:7px 12px;font:inherit;font-size:12.5px;font-weight:700;text-decoration:none;cursor:pointer}}
#shutdown-preview{{color:#b91c1c}}
.workspace{{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:14px}}
.stage{{position:relative;min-height:420px;background:var(--canvas);border:1px solid var(--line);border-radius:16px;overflow:hidden}}
canvas{{width:100%;height:100%;display:block}}
aside{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px}}
dl{{margin:0;display:grid;grid-template-columns:auto 1fr;gap:8px 12px;font-variant-numeric:tabular-nums}}
dt{{color:var(--muted);font-size:12.5px}}
dd{{margin:0;font-weight:700}}
p{{margin:14px 0 0;font-size:12.5px;line-height:1.6;color:var(--muted)}}
@media (max-width:800px){{.workspace{{grid-template-columns:minmax(0,1fr)}}}}
</style>
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
      <dl>
        <dt>宽</dt><dd>{width} mm</dd>
        <dt>深</dt><dd>{depth} mm</dd>
        <dt>高</dt><dd>{height} mm</dd>
      </dl>
      <p>这三个数是布局里已经保存的外形。要改，回布局页改完再进来。</p>
      <p>绿面是柜门这一面。门、层板、抽屉还没画在这个盒子上。</p>
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
new EventSource("/api/preview/presence/stream");
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
