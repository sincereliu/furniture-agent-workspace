import * as THREE from "three";
import { roomToThree } from "./layout_frame.js";
import { ROOM_AXES } from "./layout_annotations.js";
import { placeLabels } from "./layout_labels.js";

function ensureLabelLayer(canvas) {
  const host = canvas.parentElement;
  if (!host) return null;
  if (window.getComputedStyle(host).position === "static") host.style.position = "relative";
  let layer = host.querySelector(".scene-labels");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "scene-labels";
    layer.style.cssText = "position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:2";
    host.appendChild(layer);
  }
  return layer;
}

function makeLabelElement(layer, label) {
  const el = document.createElement("div");
  el.className = "scene-label";
  el.textContent = label.text;
  el.style.cssText = [
    "position:absolute",
    "left:0",
    "top:0",
    "font:700 12px/1.25 Inter,Microsoft YaHei,system-ui,sans-serif",
    "color:#f7f1e6",
    "background:rgba(16,14,26,.78)",
    "border:1px solid rgba(255,214,160,.35)",
    "border-radius:4px",
    "padding:1px 4px",
    "white-space:nowrap",
    "transform:translate(0,0)",
    "will-change:transform",
  ].join(";");
  layer.appendChild(el);
  return el;
}

function makeAxisGizmo() {
  const SIZE = 96;
  const board = document.createElement("canvas");
  board.width = SIZE;
  board.height = SIZE;
  const el = document.createElement("div");
  el.className = "scene-axis-gizmo";
  el.style.cssText = [
    "position:absolute",
    "right:10px",
    "bottom:10px",
    "width:96px",
    "height:96px",
    "pointer-events:none",
    "z-index:3",
  ].join(";");
  el.appendChild(board);
  return { el, ctx: board.getContext("2d") };
}

/** DOM 标注层（屏幕字号恒定）与右下角方位指示器。 */
export function createLabelOverlay(canvas, camera) {
  let labelLayer = null;
  let labelLeaders = null;
  let labelEntries = [];
  let axisGizmo = null;

  function clear() {
    for (const entry of labelEntries) entry.el.remove();
    labelEntries = [];
    labelLayer = labelLayer || ensureLabelLayer(canvas);
    if (!labelLeaders && labelLayer) {
      labelLeaders = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      labelLeaders.setAttribute("aria-hidden", "true");
      labelLeaders.style.cssText = "position:absolute;inset:0;width:100%;height:100%;overflow:hidden";
      labelLayer.prepend(labelLeaders);
    }
    if (labelLeaders) labelLeaders.replaceChildren();
    if (!axisGizmo && labelLayer) {
      axisGizmo = makeAxisGizmo();
      labelLayer.parentElement.appendChild(axisGizmo.el);
    }
  }

  function addLabel(label) {
    if (!labelLayer) return;
    const leader = document.createElementNS("http://www.w3.org/2000/svg", "line");
    leader.setAttribute("stroke", `#${label.color.toString(16).padStart(6, "0")}`);
    leader.setAttribute("stroke-width", "1");
    leader.setAttribute("opacity", ".65");
    labelLeaders.appendChild(leader);
    labelEntries.push({ ...label, leader, el: makeLabelElement(labelLayer, label) });
  }

  function drawAxisGizmo() {
    if (!axisGizmo) return;
    const { ctx } = axisGizmo;
    const S = 96;
    const R = 30;
    ctx.clearRect(0, 0, S, S);
    ctx.save();
    ctx.translate(S * 0.46, S * 0.60);
    ctx.beginPath();
    ctx.arc(0, 0, 42, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(8, 10, 20, 0.55)";
    ctx.fill();
    camera.updateMatrixWorld(true);
    const m = camera.matrixWorld;
    const col = (i) => new THREE.Vector3(m.elements[i * 4], m.elements[i * 4 + 1], m.elements[i * 4 + 2]).normalize();
    const right = col(0);
    const camUp = col(1);
    const toScreen = (dir) => ({ dx: dir.dot(right) * R, dy: -dir.dot(camUp) * R });
    ctx.lineWidth = 2.4;
    ctx.font = "700 11px Inter,Microsoft YaHei,sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (const [index, axis] of ROOM_AXES.entries()) {
      const { dx, dy } = toScreen(new THREE.Vector3(...roomToThree(...axis.direction)));
      const anchor = [0, 0.42, 0.82][index];
      ctx.strokeStyle = `#${axis.color.toString(16).padStart(6, "0")}`;
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(dx, dy);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(dx, dy, 3.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillText(axis.label, dx + anchor * 26 + 5, dy + anchor * 26);
    }
    ctx.fillStyle = "#f6efe4";
    ctx.beginPath();
    ctx.arc(0, 0, 2.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function refresh() {
    if (!labelLayer || !labelEntries.length) return;
    const rect = canvas.getBoundingClientRect();
    camera.updateMatrixWorld(true);
    const shown = [];
    const entries = [...labelEntries].sort((a, b) => Number(Boolean(b.key)) - Number(Boolean(a.key)));
    for (const entry of entries) {
      const projected = new THREE.Vector3(...roomToThree(...entry.anchor)).project(camera);
      const x = (projected.x * 0.5 + 0.5) * rect.width;
      const y = (-projected.y * 0.5 + 0.5) * rect.height;
      const visible = projected.z >= -1 && projected.z < 1 && x >= 0 && y >= 0 && x <= rect.width && y <= rect.height;
      entry.el.style.display = visible ? "block" : "none";
      entry.leader.style.display = "none";
      if (visible) shown.push({ entry, x, y, width: entry.el.offsetWidth, height: entry.el.offsetHeight, offset: entry.offset });
    }
    const positions = placeLabels(shown, rect.width, rect.height);
    for (const [i, position] of positions.entries()) {
      const { entry, x, y } = shown[i];
      entry.offset = position.offset;
      entry.el.style.transform = `translate(${Math.round(position.x)}px, ${Math.round(position.y)}px) translate(-50%,-50%)`;
      if (Math.hypot(...position.offset) > 6) {
        entry.leader.style.display = "block";
        entry.leader.setAttribute("x1", x);
        entry.leader.setAttribute("y1", y);
        entry.leader.setAttribute("x2", position.x);
        entry.leader.setAttribute("y2", position.y);
      }
    }
    drawAxisGizmo();
  }

  return { clear, addLabel, refresh };
}
