// 柜体结构视图：把板件阶段确认冻结的板件画成能转、能拆开看的盒子。
//
// 柜体坐标 = 阶段自己的坐标：X 宽（0→右）、Y 深（0→门那一面）、Z 高（0→顶）。
// three.js 是 Y 朝上，所以整组绕 X 转 -90°，组内直接用柜体坐标，不做逐块换算。
//
// 这里只画。数据由 cabinet_panel_page.py 从冻结文件投影好，页面通过 payload 递进来。

import {createPanelScene} from "../../render/panels/scene.js";
import {createPanelEditor} from "./editor.js";
import {createPanelSidebar} from "./sidebar.js";
import {triple} from "./labels.js";
export {formatMm, triple, panelCounts, materialLabel, grainLabel} from "./labels.js";

// 环顾一圈的方向（three.js 坐标，已经含 Z 朝上 → Y 朝上的那次旋转）。

export function mountCabinetStructure(options) {
  const {
    canvas,
    payload,
    hover = null,
    summary = null,
    count = null,
    rows = null,
    detail = null,
    filters = [],
    viewButtons = [],
    toggles = {},
    panelSave = {},
  } = options;

  const panelList = Array.isArray(payload.panels) ? payload.panels : [];
  const envelope = payload.envelope_mm || {};
  const width = Number(envelope.width) || 1;
  const depth = Number(envelope.depth) || 1;
  const height = Number(envelope.height) || 1;
  const state = {
    visible: true,
    doors: true,
    back: true,
    wire: false,
    explode: 0,
    // 开门角度（0–1），只作用在有铰链侧的门上。
    open: 0,
    hovered: null,
    // 鼠标压在哪一块板的哪一个面上（'px'/'nx'/'py'/'ny'/'pz'/'nz'）。只看方向，不看位置。
    hoverFace: null,
    selected: null,
  };

  // 开关作用在哪些板上：门板 / 抽屉面一组，背板 / 背拉条一组。
  const {renderer,scene,camera,root,meshes,paint,draw,pick,setView,dispose}=createPanelScene({
    canvas,panelList,width,depth,height,state,viewButtons,hingeSideOf:panel=>editor.hingeSideOf(panel)});
  const editor=createPanelEditor({panelList,meshes,state,panelSave,
    renderDetail:panel=>sidebar.renderDetail(panel),paint});
  const sidebar=createPanelSidebar({panelList,payload,width,depth,height,rows,count,detail,summary,
    state,panelSave,select,editor});
  const {renderDetail,renderRows,renderSummary}=sidebar;

  // 按钮与代码走同一条路：显示开关只有这一处实现，别在界面上再改一遍状态。
  function setDoors(on) {
    state.doors = on;
    if (toggles.doors) toggles.doors.setAttribute("aria-pressed", String(on));
    paint();
  }

  function setBack(on) {
    state.back = on;
    if (toggles.back) toggles.back.setAttribute("aria-pressed", String(on));
    paint();
  }

  function setWire(on) {
    state.wire = on;
    if (toggles.wire) toggles.wire.setAttribute("aria-pressed", String(on));
    paint();
  }

  function setExplode(percent) {
    state.explode = percent / 100;
    if (toggles.explode) toggles.explode.value = String(percent);
    paint();
  }

  function setOpen(percent) {
    state.open = percent / 100;
    if (toggles.open) toggles.open.value = String(percent);
    paint();
  }

  function toggle(what) {
    if (what === "doors") setDoors(!state.doors);
    else if (what === "back") setBack(!state.back);
    else if (what === "wire") setWire(!state.wire);
    else throw new Error(`unknown toggle: ${what}`);
  }

  function select(panelId) {
    state.selected = panelId;
    if (rows) {
      for (const row of rows.querySelectorAll("tr[data-panel]")) {
        row.setAttribute("aria-selected", String(row.dataset.panel === panelId));
      }
    }
    renderDetail(panelList.find((panel) => panel.id === panelId) || null);
    paint();
  }

  // 点选：按下和抬起在同一处才算点，拖动不算。
  let downAt = null;

  canvas.addEventListener("pointerdown", (event) => {
    downAt = { x: event.clientX, y: event.clientY };
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!downAt) return;
    const moved = Math.hypot(event.clientX - downAt.x, event.clientY - downAt.y);
    downAt = null;
    if (moved > 4) return;
    const found = pick(event);
    // 点板件**只选中**，不改任何东西。改纹理在右边「顺纹方向」那一行上——
    // 点一下就改数据太容易误伤（点选本来是最常用的动作）。
    select(found ? found.panel.id : null);
  });
  canvas.addEventListener("pointermove", (event) => {
    const found = pick(event);
    const panel = found ? found.panel : null;
    const hoveredId = panel ? panel.id : null;
    const face = found ? found.face : null;
    if (hoveredId !== state.hovered || face !== state.hoverFace) {
      state.hovered = hoveredId;
      state.hoverFace = face;
      paint();
    }
    if (hover) {
      if (panel) {
        const rect = canvas.getBoundingClientRect();
        hover.style.display = "block";
        hover.style.left = `${event.clientX - rect.left}px`;
        hover.style.top = `${event.clientY - rect.top}px`;
        hover.textContent = `${panel.name} · ${triple(panel.size_mm)} mm`;
      } else {
        hover.style.display = "none";
      }
    }
  });
  canvas.addEventListener("pointerleave", () => {
    if (state.hovered !== null || state.hoverFace !== null) {
      state.hovered = null;
      state.hoverFace = null;
      paint();
    }
    if (hover) hover.style.display = "none";
  });

  for (const button of viewButtons) {
    button.addEventListener("click", () => setView(button.dataset.view));
  }
  if (toggles.doors) {
    toggles.doors.addEventListener("click", () => toggle("doors"));
  }
  if (toggles.back) {
    toggles.back.addEventListener("click", () => toggle("back"));
  }
  if (toggles.wire) {
    toggles.wire.addEventListener("click", () => toggle("wire"));
  }
  if (toggles.explode) {
    toggles.explode.addEventListener("input", () => setExplode(toggles.explode.value));
  }
  if (toggles.open) {
    toggles.open.addEventListener("input", () => setOpen(toggles.open.value));
  }
  for (const filter of filters) {
    filter.addEventListener("change", () => {
      const active = new Set(
        [...filters].filter((item) => item.checked).map((item) => item.dataset.assembly)
      );
      state.filter = (panel) => active.has(panel.assembly);
      paint();
    });
  }

  window.addEventListener("resize", () => {
    // 尺寸在 draw() 里每帧重取，这里只负责立刻反映一次。
    renderer.setSize(canvas.clientWidth || 960, canvas.clientHeight || 640, false);
  });


  // 地址栏可以指点初始状态：`?view=front&doors=0&wire=1&explode=60&open=80`。
  // 只影响打开时看哪一面，不改数据——分享一个视角、或者截图核对都靠它。
  const query = new URLSearchParams(window.location.search);
  const requestedView = query.get("view");
  const requestedExplode = Number(query.get("explode"));
  if (query.get("doors") === "0") setDoors(false);
  if (query.get("back") === "0") setBack(false);
  if (query.get("wire") === "1") setWire(true);
  if (query.get("only")) {
    // `?only=white` 之类：只留这一类板件，用来核对某一块到底画在哪。改的是显示，不是数据。
    const groups = new Set(query.get("only").split(","));
    state.filter = (panel) => groups.has(panel.material) || groups.has(panel.assembly);
  }
  if (Number.isFinite(requestedExplode)) setExplode(Math.min(100, Math.max(0, requestedExplode)));
  const requestedOpen = Number(query.get("open"));
  if (Number.isFinite(requestedOpen) && query.get("open") !== null) {
    setOpen(Math.min(100, Math.max(0, requestedOpen)));
  }

  renderSummary();
  renderRows();
  setView(requestedView || "iso");
  paint();
  draw();

  // `?probe=1`：把每块板当前真实的材质与几何贴回页面标题，供无头浏览器读。
  // 只读画面状态，不改数据——截图核对用，正常打开不会碰它。
  if (query.get("probe") === "1") {
    const dump = meshes.map((record) => ({
      id: record.panel.id,
      material: record.panel.material,
      visible: record.mesh.visible,
      hasMap: Boolean(record.material.map),
      color: record.material.color.hex,
      size: record.mesh.scale.toArray(),
      pos: record.mesh.position.toArray(),
      // 顺纹方向与当前实际用的重复次数：核对「横纹的板有没有转 90°」靠这两个。
      grain: record.panel.grain.axis,
      mapRotation: record.material.map ? record.material.map.rotation : null,
      mapRepeat: record.material.map ? record.material.map.repeat.toArray() : null,
    }));
    document.title = `PROBE ${JSON.stringify({
      camera: camera.position.toArray().map((value) => Math.round(value)),
      size: [canvas.clientWidth, canvas.clientHeight],
      panels: dump,
    })}`;
  }

  return {
    setView,
    select,
    toggle,
    setExplode,
    /** 页面上由指针位置驱动；这里留一个入口，验收脚本才能核对变色。 */
    hover(panelId, face) {
      state.hovered = panelId || null;
      state.hoverFace = face || null;
      paint();
    },
    state,
    /** 验收钩子：样式与几何的换算在 Node 里用桩件核对，见 tests 说明。 */
    __test: { scene, camera, root, meshes },
    dispose,
  };
}
